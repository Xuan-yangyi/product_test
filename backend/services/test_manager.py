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

        # 采集设备信息（SN、主板SN、芯片类型）
        self._collect_device_info(test_id, context)

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
        # 立即持久化到 SQLite，使测试结果页面能看到运行中的测试
        self.result_service.save_test_result(self._tests[test_id])
        task = asyncio.create_task(self.executor.run(test_id, steps, context))
        self._tasks[test_id] = task

    def _start_syslog_monitor(self, test_id: str, ssh_client, device_ip: str):
        """SSH 连接建立后立即启动 syslog 后台监控线程

        syslog 在 SE9 上电后持续运行，不需要等待老化测试开始。
        使用 journalctl 读取系统日志（/var/log/syslog 可能因 journald 配置问题不更新）。
        独立 SSH 连接 + 独立线程，写入本地文件并通过 WebSocket 推送。
        自动过滤测试框架自身的 sudo/SSH 会话噪音。
        """
        # 防重复启动
        task = self._tests.get(test_id)
        if task and task.get("_syslog_monitor_started"):
            return
        if task:
            task["_syslog_monitor_started"] = True

        import threading
        import time
        import re
        import json as _json
        from ..config import Config
        from ..engine.ssh_client import SSHClient

        # 噪音过滤器：排除测试框架自身的 sudo/SSH 会话日志
        _SYSLOG_NOISE_RE = re.compile(
            r'pam_unix\((sudo|sshd):session\): session (opened|closed)'
            r'|sshd\[\d+\]: Accepted password for '
            r'|sshd\[\d+\]: pam_unix\(sshd:session\): session (opened|closed)'
            r'|systemd-logind\[\d+\]: (New|Removed) session \S+ of user'
            r'|systemd\[\d+\]: (Started|Removed) [Ss]ession \S+ of [Uu]ser'
            r'|sudo\[\d+\]:\s+\S+\s+:\s+PWD=.*;\s*USER=root\s*;\s*COMMAND='
            r'|sudo\[\d+\]:\s+pam_unix\(sudo:session\):'
        )

        def _filter_noise(lines):
            """过滤掉测试框架自身产生的 syslog 噪音"""
            return [l for l in lines if not _SYSLOG_NOISE_RE.search(l)]

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
                            # 过滤噪音并写入文件
                            lines = [l.strip() for l in stdout.split("\n") if l.strip()]
                            lines = _filter_noise(lines)
                            last_line = lines[-1] if lines else ""
                            with open(local_path, "w") as f:
                                for line in lines:
                                    f.write(line + "\n")
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
                                # 过滤框架自身噪音
                                filtered = _filter_noise(filtered)
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

    def _collect_device_info(self, test_id: str, context: dict):
        """采集设备信息（SN、主板SN、芯片类型），写入 task 字典"""
        task = self._tests.get(test_id)
        if not task:
            return

        serial_client = context.get("serial_client")
        ssh_client = context.get("ssh_client")

        # 通过 SSH 运行 show_ddr 检测芯片型号，用于老化测试 --chip_type 参数
        if ssh_client:
            try:
                stdout, _, _ = ssh_client.exec_cmd(
                    "show_ddr 2>/dev/null", timeout=10, sudo=True, sudo_password="linaro"
                )
                out_lower = stdout.strip().lower()
                detected_chip = ""
                if "cv186ah" in out_lower:
                    detected_chip = "cv186ah"
                elif "bm1688" in out_lower:
                    detected_chip = "bm1688"
                elif "cv84x6" in out_lower:
                    detected_chip = "cv84x6"
                if detected_chip:
                    context.setdefault("params", {})["chip_model"] = detected_chip
                    task.setdefault("extra_info", {})["chip_model"] = detected_chip
                    logger.info(f"[{test_id}] 检测到芯片型号: {detected_chip}")
            except Exception as e:
                logger.warning(f"[{test_id}] 芯片型号检测失败: {e}")

        if serial_client:
            try:
                from ..engine.device_ops import DeviceOps
                ops = DeviceOps(serial_client)
                sn = ops.get_device_sn()
                board_sn = ops.get_board_sn()
                chip_type = ops.get_chip_type()
                if sn:
                    task["serial_number"] = sn
                    logger.info(f"[{test_id}] 设备 SN: {sn}")
                if board_sn:
                    task["board_sn"] = board_sn
                    logger.info(f"[{test_id}] 主板 SN: {board_sn}")
                task.setdefault("extra_info", {})["chip_type"] = chip_type
            except Exception as e:
                logger.warning(f"[{test_id}] 串口采集设备信息失败: {e}")

        if ssh_client and not task.get("serial_number"):
            try:
                # 方法1: fw_printenv
                stdout, stderr, code = ssh_client.exec_cmd(
                    "fw_printenv serial_number 2>/dev/null", timeout=10,
                    sudo=True, sudo_password="linaro"
                )
                logger.info(f"[{test_id}] fw_printenv serial_number: stdout={stdout.strip()!r}, stderr={stderr.strip()!r}")
                import re
                match = re.search(r"serial_number[= ](\S+)", stdout)
                if match:
                    task["serial_number"] = match.group(1).strip()
                    logger.info(f"[{test_id}] 设备 SN (fw_printenv): {task['serial_number']}")

                # 方法2: 如果 fw_printenv 没拿到，尝试从 OEMconfig.ini 读取
                if not task.get("serial_number"):
                    stdout2, _, _ = ssh_client.exec_cmd(
                        "cat /factory/OEMconfig.ini 2>/dev/null | grep -i 'serial_number\\|SN' || echo ''",
                        timeout=10, sudo=True, sudo_password="linaro"
                    )
                    logger.info(f"[{test_id}] OEMconfig SN: {stdout2.strip()!r}")
                    match_sn = re.search(r'(?:serial_number|SN)\s*[=:]\s*(\S+)', stdout2, re.IGNORECASE)
                    if match_sn:
                        task["serial_number"] = match_sn.group(1).strip()
                        logger.info(f"[{test_id}] 设备 SN (OEMconfig): {task['serial_number']}")

                # 主板 SN
                stdout3, _, _ = ssh_client.exec_cmd(
                    "fw_printenv board_sn 2>/dev/null", timeout=10,
                    sudo=True, sudo_password="linaro"
                )
                match2 = re.search(r"board_sn[= ](\S+)", stdout3)
                if match2:
                    task["board_sn"] = match2.group(1).strip()
                    logger.info(f"[{test_id}] 主板 SN: {task['board_sn']}")

                if not task.get("serial_number"):
                    logger.warning(f"[{test_id}] 未能获取设备 SN，fw_printenv 和 OEMconfig 均未找到")
            except Exception as e:
                logger.warning(f"[{test_id}] SSH 采集设备信息失败: {e}")
            except Exception as e:
                logger.warning(f"[{test_id}] SSH 采集设备信息失败: {e}")

    async def stop_test(self, test_id: str):
        """停止测试"""
        self.executor.stop(test_id)
        if test_id in self._tests:
            self._tests[test_id]["status"] = "stopped"

    def mark_test_failed(self, test_id: str, error_message: str):
        """标记测试为失败（用于启动失败等无法进入执行器流程的场景）"""
        if test_id in self._tests:
            self._tests[test_id]["status"] = "failed"
            self._tests[test_id]["error_message"] = error_message
            self._tests[test_id]["finished_at"] = datetime.now()
            # 持久化到 SQLite，使测试结果页面可以看到
            self.result_service.save_test_result(self._tests[test_id])
            logger.info(f"测试标记为失败: {test_id}, 原因: {error_message}")

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
        """获取测试详情（返回副本，避免调用方意外修改内存状态）"""
        task = self._tests.get(test_id)
        if not task:
            return None
        # 浅拷贝，附加 executor 最新状态
        result = dict(task)
        exec_status = self.executor.get_status(test_id)
        if exec_status:
            result["current_step"] = exec_status["current_step"]
            result["status"] = exec_status["status"]
            result["steps"] = exec_status.get("results", [])
        return result

    def _clean_task(self, task: dict) -> dict:
        """过滤 task 中的内部字段，返回可序列化的副本"""
        return {k: v for k, v in task.items() if not k.startswith("_")}

    def sync_running_to_db(self):
        """将所有运行中的测试同步到 SQLite 数据库。

        用于确保在部署修复后，已存在的运行中测试也能出现在测试结果页面。
        仅在测试状态为 running 时调用 save_test_result（upsert 操作，安全幂等）。
        """
        count = 0
        for test_id, task in self._tests.items():
            if task.get("status") == "running":
                try:
                    self.result_service.save_test_result(task)
                    count += 1
                except Exception as e:
                    logger.warning(f"同步测试 {test_id} 到数据库失败: {e}")
        if count > 0:
            logger.info(f"已将 {count} 个运行中的测试同步到数据库")

    def get_all_tests(self) -> list:
        """获取所有测试"""
        return [
            self._clean_task(self.get_test(tid)) for tid in self._tests
        ]

    # === 回调处理 ===
    async def _on_step_start(self, test_id, step_index, step_name):
        from ..api.ws import broadcast_to_test
        await broadcast_to_test(test_id, "step_update", {
            "step_index": step_index,
            "step_name": step_name,
            "result": "running",
            "duration_ms": 0,
        })
        # 更新 current_step 和当前步骤名
        if test_id in self._tests:
            self._tests[test_id]["current_step"] = step_index + 1
            self._tests[test_id]["_current_step_name"] = step_name

    async def _on_step_complete(self, test_id, step_index, result, message, duration):
        # 获取步骤名
        task = self._tests.get(test_id, {})
        step_name = task.get("_current_step_name", "")
        self.result_service.save_step_result(
            test_id, step_index, step_name, result, message, duration
        )
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
        # 保存到 SQLite（running 状态也需要持久化，以便测试结果页面显示运行中的测试）
        task = self._tests.get(test_id, {})
        if task:
            self.result_service.save_test_result(task)
        if new_status in ("completed", "failed", "stopped"):
            if task:
                task["finished_at"] = datetime.now()
                # 统计 passed/failed/skipped
                status = self.executor.get_status(test_id)
                if status:
                    results = status.get("results", [])
                    task["passed"] = sum(1 for r in results if r["result"] == "pass")
                    task["failed"] = sum(1 for r in results if r["result"] == "fail")
                    task["skipped"] = sum(1 for r in results if r["result"] == "skip")
                # 记录 log 文件路径
                task.setdefault("extra_info", {})["aging_log"] = f"log/aging_{test_id}.log"
                task.setdefault("extra_info", {})["syslog_log"] = f"log/syslog_{test_id}.log"
            self.result_service.save_test_result(task)
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
