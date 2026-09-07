"""测试任务管理器

管理测试任务的创建、启动、停止和状态查询。
支持多任务并行调度。
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional
from .test_executor import TestExecutor
from .resource_pool import ResourcePool
from .config_service import ConfigService
from .result_service import ResultService

logger = logging.getLogger(__name__)


class TestManager:
    """测试任务管理器"""

    def __init__(self, resource_pool: ResourcePool, config_service: ConfigService,
                 result_service: ResultService):
        self.executor = TestExecutor()
        self.resource_pool = resource_pool
        self.config_service = config_service
        self.result_service = result_service
        self._tests: Dict[str, dict] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._loop = None  # 主事件循环引用，由 start_test 延迟设置
        self._load_existing_tests()

    async def create_test(self, test_type: str, product_model: str,
                          serial_port: str = None, device_ip: str = None,
                          device_count: int = 1, params: dict = None,
                          cluster_id: str = None) -> dict:
        """创建测试任务"""
        test_id = str(uuid.uuid4())[:12]

        task = {
            "test_id": test_id,
            "test_type": test_type,
            "product_model": product_model,
            "serial_port": serial_port,
            "device_ip": device_ip,
            "device_count": device_count,
            "params": params or {},
            "cluster_id": cluster_id or "",
            "status": "pending",
            "created_at": datetime.now(),
            "current_step": 0,
            "total_steps": 0,
        }

        self._tests[test_id] = task
        self._save_test(test_id)  # 持久化
        logger.info(f"测试任务已创建: {test_id} ({test_type})")
        return task

    async def start_test(self, test_id: str):
        """启动测试任务"""
        task = self._tests.get(test_id)
        if not task:
            raise ValueError(f"测试任务不存在: {test_id}")

        # 保存主事件循环引用（供线程中的日志回调使用）
        import asyncio
        self._loop = asyncio.get_running_loop()

        test_type = task["test_type"]
        product_model = task["product_model"]

        # 构建测试步骤
        steps = self.config_service.build_test_steps(test_type, product_model, task)
        task["total_steps"] = len(steps)

        # 构建执行上下文
        context = {
            "test_id": test_id,
            "test_type": test_type,
            "product_model": product_model,
            "serial_port": task["serial_port"],
            "device_ip": task["device_ip"],
            "params": task["params"],
            "resource_pool": self.resource_pool,
            "_on_log_callback": self._on_log_sync_helper,
            "_start_syslog_monitor": self._start_syslog_monitor,
        }

        # 设置 SSH 连接（网络测试，如老化测试）
        if task["device_ip"]:
            from ..engine.ssh_client import SSHClient
            ssh_client = SSHClient()
            # SE9 设备使用 linaro 用户
            if ssh_client.connect(task["device_ip"], user="linaro", password="linaro", timeout=10):
                logger.info(f"SSH 连接成功: {task['device_ip']}")
                context["ssh_client"] = ssh_client
                # SSH 连接建立后立即启动 syslog 监控（独立于测试步骤）
                self._start_syslog_monitor(test_id, ssh_client, task["device_ip"])
            else:
                logger.error(f"SSH 连接失败: {task['device_ip']}")
                raise ValueError(f"无法连接到设备 {task['device_ip']}")

        # 设置串口连接（串口测试）
        if task["serial_port"]:
            serial_client = await self.resource_pool.acquire_serial(task["serial_port"])
            if serial_client:
                context["serial_client"] = serial_client
            else:
                raise ValueError(f"无法获取串口 {task['serial_port']}")

        # 注册回调
        self.executor.register_callbacks(test_id, {
            "on_step_start": self._on_step_start,
            "on_step_complete": self._on_step_complete,
            "on_status_change": self._on_status_change,
            "on_log": self._on_log,
            "on_interaction_required": self._on_interaction,
        })

        # 异步执行
        self._tests[test_id]["status"] = "running"
        self._tests[test_id]["_context"] = context  # 保存上下文用于清理
        self._save_test(test_id)  # 持久化状态
        task = asyncio.create_task(self.executor.run(test_id, steps, context))
        self._tasks[test_id] = task

    def _start_syslog_monitor(self, test_id: str, ssh_client, device_ip: str):
        """SSH 连接建立后立即启动 syslog 后台监控线程

        syslog 在 SE9 上电后持续运行，不需要等待老化测试开始。
        使用 journalctl 读取系统日志（/var/log/syslog 可能因 journald 配置问题不更新）。
        独立 SSH 连接 + 独立线程，写入本地文件并通过 WebSocket 推送。
        """
        # 防重复启动
        task = self._tests.get(test_id)
        if task and task.get("_syslog_monitor_started"):
            return
        if task:
            task["_syslog_monitor_started"] = True

        import threading
        import time
        import json as _json
        from ..config import Config
        from ..engine.ssh_client import SSHClient

        # 在主线程中创建独立的 SSH 连接（避免线程中 connect 挂起）
        monitor_ssh = SSHClient()
        if not monitor_ssh.connect(device_ip, user="linaro", password="linaro", timeout=10):
            logger.error(f"[{test_id}] syslog 监控: 无法建立独立 SSH 连接")
            return

        logger.info(f"[{test_id}] syslog 监控线程启动 (journalctl), 设备: {device_ip}")

        log_dir = Config.LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)
        local_path = log_dir / f"syslog_{test_id}.log"
        last_ts = 0.0       # 最后一条日志的 __REALTIME_TIMESTAMP (秒)
        last_line = ""      # 最后一条日志的原文，用于去重
        initialized = False

        def _monitor_loop():
            nonlocal last_ts, last_line, initialized
            while True:
                task = self._tests.get(test_id)
                if not task or task.get("status") in ("completed", "failed", "stopped"):
                    logger.info(f"[{test_id}] syslog 监控线程退出")
                    break

                try:
                    if not initialized:
                        # 首次：读取最后 100 条 journal 日志
                        stdout, stderr, code = monitor_ssh.exec_cmd(
                            "journalctl -n 100 --no-pager 2>/dev/null || echo ''",
                            timeout=30, sudo=True, sudo_password="linaro"
                        )
                        if stdout.strip():
                            with open(local_path, "w") as f:
                                f.write(stdout)
                                if not stdout.endswith("\n"):
                                    f.write("\n")
                            # 获取最后一条的时间戳（微秒精度）
                            json_out, _, _ = monitor_ssh.exec_cmd(
                                "journalctl -n 1 -o json --no-pager 2>/dev/null || echo ''",
                                timeout=10, sudo=True, sudo_password="linaro"
                            )
                            try:
                                entry = _json.loads(json_out.strip().split("\n")[-1])
                                last_ts = int(entry.get("__REALTIME_TIMESTAMP", 0)) / 1_000_000.0
                            except Exception:
                                last_ts = time.time()
                            # 保存最后一行用于去重
                            lines = [l.strip() for l in stdout.split("\n") if l.strip()]
                            last_line = lines[-1] if lines else ""
                            initialized = True
                            logger.info(f"[{test_id}] syslog 初始加载完成: {len(lines)} 条, ts={last_ts}")
                            # 推送初始日志
                            for line in lines:
                                self._on_log_sync_helper(test_id, "INFO", "syslog", line)
                        else:
                            initialized = True
                            last_ts = time.time()
                    else:
                        # 后续：用 --since 追踪增量（秒级精度 + 行去重）
                        since_sec = int(last_ts)
                        stdout, stderr, code = monitor_ssh.exec_cmd(
                            f"journalctl --since=@{since_sec} --no-pager 2>/dev/null || echo ''",
                            timeout=30, sudo=True, sudo_password="linaro"
                        )
                        new_content = stdout.strip()
                        if new_content:
                            new_lines = [l.strip() for l in new_content.split("\n") if l.strip()]
                            # 去重：跳过 last_line 及其之前的行
                            filtered = []
                            found_last = False
                            for line in new_lines:
                                if not found_last:
                                    if line == last_line:
                                        found_last = True
                                    continue
                                filtered.append(line)

                            if filtered:
                                with open(local_path, "a") as f:
                                    for line in filtered:
                                        f.write(line + "\n")
                                last_line = filtered[-1]
                                # 更新 last_ts：从最后一条新日志获取时间戳
                                json_out, _, _ = monitor_ssh.exec_cmd(
                                    "journalctl -n 1 -o json --no-pager 2>/dev/null || echo ''",
                                    timeout=10, sudo=True, sudo_password="linaro"
                                )
                                try:
                                    entry = _json.loads(json_out.strip().split("\n")[-1])
                                    last_ts = int(entry.get("__REALTIME_TIMESTAMP", 0)) / 1_000_000.0
                                except Exception:
                                    last_ts = time.time()
                                for line in filtered:
                                    self._on_log_sync_helper(test_id, "INFO", "syslog", line)

                    time.sleep(2)
                except Exception as e:
                    logger.error(f"[{test_id}] syslog 监控读取异常: {e}")
                    time.sleep(5)

            monitor_ssh.close()

        thread = threading.Thread(target=_monitor_loop, daemon=True, name=f"syslog-monitor-{test_id}")
        thread.start()
        if test_id in self._tests:
            self._tests[test_id].setdefault("_monitor_threads", []).append(thread)

    async def stop_test(self, test_id: str):
        """停止测试"""
        self.executor.stop(test_id)
        if test_id in self._tests:
            self._tests[test_id]["status"] = "stopped"

    async def pause_test(self, test_id: str):
        """暂停测试"""
        self.executor.pause(test_id)
        if test_id in self._tests:
            self._tests[test_id]["status"] = "paused"

    async def resume_test(self, test_id: str):
        """恢复测试"""
        self.executor.resume(test_id)

    async def resolve_interaction(self, test_id: str, response: dict):
        """解析交互响应"""
        self.executor.resolve_interaction(test_id, response)

    def get_test(self, test_id: str) -> Optional[dict]:
        """获取测试详情"""
        task = self._tests.get(test_id)
        if not task:
            return None
        status = self.executor.get_status(test_id)
        if status:
            task["current_step"] = status["current_step"]
            task["status"] = status["status"]
            task["steps"] = status.get("results", [])
        return task

    def get_all_tests(self) -> list:
        """获取所有测试"""
        return [
            self.get_test(tid) for tid in self._tests
        ]

    def _save_test(self, test_id: str):
        """持久化测试状态到文件"""
        task = self._tests.get(test_id)
        if not task:
            return
        import json
        from ..config import Config
        tests_dir = Config.DATA_DIR / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        path = tests_dir / f"{test_id}.json"
        try:
            # 不序列化不可序列化的对象（ssh_client 等）
            save_data = {k: v for k, v in task.items()
                         if k not in ("_context",)}
            with open(path, "w") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"保存测试状态失败: {e}")

    def _load_existing_tests(self):
        """从磁盘加载已有的测试状态"""
        import json
        from ..config import Config
        tests_dir = Config.DATA_DIR / "tests"
        if not tests_dir.exists():
            return
        for f in tests_dir.glob("*.json"):
            try:
                with open(f) as fp:
                    task = json.load(fp)
                self._tests[task["test_id"]] = task
                logger.info(f"加载已有测试: {task['test_id']} ({task.get('status', 'unknown')})")
            except Exception as e:
                logger.error(f"加载测试文件失败 {f}: {e}")

    # === 回调处理 ===
    async def _on_step_start(self, test_id, step_index, step_name):
        from ..api.ws import broadcast_to_test
        await broadcast_to_test(test_id, "step_update", {
            "step_index": step_index,
            "step_name": step_name,
            "result": "running",
            "duration_ms": 0,
        })
        # 也更新 current_step
        if test_id in self._tests:
            self._tests[test_id]["current_step"] = step_index + 1

    async def _on_step_complete(self, test_id, step_index, result, message, duration):
        self.result_service.save_step_result(test_id, step_index, result, message, duration)
        from ..api.ws import broadcast_to_test
        await broadcast_to_test(test_id, "step_update", {
            "step_index": step_index,
            "result": result,
            "step_label": message,
            "duration_ms": duration,
        })
        # 更新 current_step
        if test_id in self._tests:
            task = self._tests[test_id]
            task["current_step"] = step_index + 1
            # 同步 steps 列表
            status = self.executor.get_status(test_id)
            if status:
                task["steps"] = status.get("results", [])

    async def _on_status_change(self, test_id, old_status, new_status):
        if test_id in self._tests:
            self._tests[test_id]["status"] = new_status
        from ..api.ws import broadcast_to_test
        await broadcast_to_test(test_id, "status_change", {
            "old": old_status,
            "new": new_status,
        })
        if new_status in ("completed", "failed", "stopped"):
            task = self._tests.get(test_id, {})
            if task:
                task["finished_at"] = datetime.now()
            self.result_service.save_test_result(task)
            self._save_test(test_id)  # 持久化最终状态
            # 清理 SSH/串口连接
            task = self._tests.get(test_id, {})
            context = task.get("_context", {})
            ssh_client = context.get("ssh_client")
            if ssh_client:
                ssh_client.close()
            if task.get("serial_port"):
                self.resource_pool.release_serial(task["serial_port"])

    async def _on_log(self, test_id, level, source, message):
        from ..api.ws import broadcast_to_test
        await broadcast_to_test(test_id, "log", {
            "level": level,
            "source": source,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        })

    def _on_log_sync_helper(self, test_id, level, source, message):
        """同步版本的日志回调（供线程池中的阻塞步骤使用）

        使用 asyncio.run_coroutine_threadsafe 将日志推送到 WebSocket，
        确保从任意线程都能安全地调度到主事件循环。
        """
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._on_log(test_id, level, source, message), self._loop
        )

    async def _on_interaction(self, test_id, step_name, message, dialog_type, timeout):
        # 存储交互请求，等待前端通过 HTTP 响应
        pass
