"""集群老化管理器

管理集群老化测试：一个集群包含多台设备，每台设备独立的子测试。
支持创建、启动、停止、查询集群状态，以及持久化。
"""
import asyncio
import json
import logging
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from ..config import Config

logger = logging.getLogger(__name__)

# 持久化文件路径
RUNTIME_DIR = Config.CFG_DIR / "runtime"


class ClusterManager:
    """集群老化管理器

    管理多个设备的集群老化测试。
    每个设备独立的 SSH 连接、独立的测试步骤、独立的日志。
    支持持久化到磁盘，后端重启后可恢复。
    """

    def __init__(self, test_manager):
        self._test_manager = test_manager
        self._clusters: Dict[str, dict] = {}
        self._load_from_disk()
        # 将内存中已有的运行中测试同步到 SQLite（确保测试结果页面能看到）
        self._test_manager.sync_running_to_db()
        # 清理 SQLite 中残留的 running 记录（测试已不在内存中 → 标记为 interrupted）
        active_ids = set(self._test_manager._tests.keys())
        self._test_manager.result_service.clean_stale_running_records(active_ids)

    async def create_cluster(self, test_type: str, product_model: str,
                             devices: List[dict], write_oem: bool = False,
                             oem_profile: str = None) -> dict:
        """创建集群老化测试

        Args:
            test_type: 测试类型（如 se9_aging_test）
            product_model: 产品型号
            devices: 设备列表 [{"ip": "10.80.40.36", "params": {"loop": 10, "reboot": 3}}]
            write_oem: 是否写入 OEM 信息

        Returns:
            cluster 信息字典
        """
        # 重复检测：检查是否有设备已在运行中或中断的集群中
        new_ips = {d["ip"] for d in devices}
        conflicts = self._find_conflicts(new_ips)
        if conflicts:
            conflict_ips = [c[0] for c in conflicts]
            raise ValueError(f"以下设备已有进行中的测试，请先停止或删除: {', '.join(conflict_ips)}")

        cluster_id = str(uuid.uuid4())[:12]
        sub_tests = []

        for device in devices:
            device_params = device.get("params", {})
            logger.info(f"创建集群节点: ip={device.get('ip')}, params={device_params}")
            if write_oem:
                device_params["write_oem"] = True
            if oem_profile:
                device_params["oem_profile"] = oem_profile

            task = await self._test_manager.create_test(
                test_type=test_type,
                product_model=product_model,
                device_ip=device["ip"],
                device_count=1,
                params=device_params,
                cluster_id=cluster_id,
            )
            sub_tests.append({
                "test_id": task["test_id"],
                "device_ip": device["ip"],
                "params": device_params,
            })

        self._clusters[cluster_id] = {
            "cluster_id": cluster_id,
            "test_type": test_type,
            "product_model": product_model,
            "status": "pending",
            "sub_tests": sub_tests,
            "created_at": datetime.now().isoformat(),
        }

        logger.info(f"创建集群: {cluster_id}, {len(sub_tests)} 台设备")
        self._save_to_disk()
        return self._clusters[cluster_id]

    async def start_cluster(self, cluster_id: str):
        """启动集群中所有子测试"""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            raise ValueError(f"集群不存在: {cluster_id}")

        cluster["status"] = "running"
        self._save_to_disk()

        for sub in cluster["sub_tests"]:
            try:
                await self._test_manager.start_test(sub["test_id"])
                logger.info(f"集群节点启动: {sub['device_ip']} -> {sub['test_id']}")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"集群节点启动失败 {sub['device_ip']}: {error_msg}")
                # 标记子测试为失败，并持久化到 SQLite，让用户能看到失败原因
                sub["status"] = "failed"
                sub["error_message"] = error_msg
                self._test_manager.mark_test_failed(sub["test_id"], error_msg)

        # 如果所有子测试都启动失败，标记集群为失败
        if all(sub.get("status") == "failed" for sub in cluster["sub_tests"]):
            cluster["status"] = "failed"
            self._save_to_disk()

    async def stop_cluster(self, cluster_id: str):
        """停止集群中所有子测试"""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            raise ValueError(f"集群不存在: {cluster_id}")

        for sub in cluster["sub_tests"]:
            try:
                await self._test_manager.stop_test(sub["test_id"])
            except Exception as e:
                logger.error(f"停止节点失败 {sub['device_ip']}: {e}")

        cluster["status"] = "stopped"
        self._save_to_disk()

    def get_cluster(self, cluster_id: str) -> Optional[dict]:
        """获取集群信息"""
        return self._clusters.get(cluster_id)

    def delete_cluster(self, cluster_id: str):
        """删除集群及其所有子测试"""
        cluster = self._clusters.pop(cluster_id, None)
        if not cluster:
            raise ValueError(f"集群不存在: {cluster_id}")
        for sub in cluster.get("sub_tests", []):
            try:
                self._test_manager.stop_test(sub["test_id"])
            except Exception:
                pass
        logger.info(f"集群已删除: {cluster_id}")
        self._save_to_disk()

    def get_cluster_status(self, cluster_id: str) -> dict:
        """获取集群状态，聚合所有子测试进度"""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            raise ValueError(f"集群不存在: {cluster_id}")

        nodes = []
        completed_count = 0
        failed_count = 0
        running_count = 0

        for sub in cluster["sub_tests"]:
            task = self._test_manager.get_test(sub["test_id"]) or {}
            status = task.get("status", None)
            # 测试不在内存中（如后端重启后）则回退到 sub 记录的状态
            if status is None:
                status = sub.get("status", "unknown")

            if status == "running":
                running_count += 1
            elif status == "completed":
                completed_count += 1
            elif status in ("failed", "unknown", "stopped"):
                failed_count += 1

            # 解析 loop 进度
            loop_progress = 0
            loop_completed = 0
            total_loop = sub.get("params", {}).get("loop", 0)
            if total_loop > 0 and task.get("steps"):
                # 从 monitor_aging 步骤的日志中解析 loop 进度
                for step in task.get("steps", []):
                    if step.get("step_name") == "monitor_aging":
                        continue

            # 解析当前温度
            current_temp = None
            if task.get("steps"):
                log_file = Config.LOG_DIR / f"aging_{sub['test_id']}.log"
                if log_file.exists():
                    try:
                        with open(log_file) as f:
                            lines = f.readlines()
                            for line in reversed(lines):
                                match = __import__("re").search(r"chip temp: (\d+)", line)
                                if match:
                                    current_temp = round(int(match.group(1)) / 1000.0, 1)
                                    break
                    except Exception:
                        pass

            nodes.append({
                "test_id": sub["test_id"],
                "device_ip": sub["device_ip"],
                "status": status,
                "error_message": sub.get("error_message", "") or task.get("error_message", ""),
                "current_step": task.get("current_step", 0),
                "total_steps": task.get("total_steps", 0),
                "params": sub.get("params", {}),
                "steps": task.get("steps", []),
                "loop_progress": loop_progress,
                "loop_completed": loop_completed,
                "current_temp": current_temp,
            })

        # 更新集群整体状态
        total = len(cluster["sub_tests"])
        old_status = cluster.get("status")
        if running_count > 0:
            # 有节点正在运行，集群保持 running（防止因 unknown 节点误判为终端）
            if cluster.get("status") != "running":
                cluster["status"] = "running"
        elif completed_count == total:
            cluster["status"] = "completed"
        elif failed_count > 0 and (completed_count + failed_count) >= total:
            cluster["status"] = "failed"

        # 状态变更时持久化并记录日志
        if cluster["status"] != old_status:
            logger.info(
                f"集群状态变更: {cluster_id} {old_status} -> {cluster['status']} "
                f"(运行:{running_count} 完成:{completed_count} 失败:{failed_count}/{total})"
            )
            if cluster["status"] in ("completed", "failed"):
                logger.info(f"集群已结束: {cluster_id} -> {cluster['status']}")
            self._save_to_disk()

        return {
            "cluster_id": cluster_id,
            "test_type": cluster["test_type"],
            "product_model": cluster["product_model"],
            "status": cluster["status"],
            "created_at": cluster["created_at"],
            "nodes": nodes,
            "summary": {
                "total": total,
                "completed": completed_count,
                "failed": failed_count,
                "running": total - completed_count - failed_count,
            },
        }

    def get_all_clusters(self) -> list:
        """获取所有集群列表（按创建时间倒序）"""
        clusters = [
            {
                "cluster_id": cid,
                "test_type": c["test_type"],
                "product_model": c["product_model"],
                "status": c["status"],
                "node_count": len(c.get("sub_tests", [])),
                "created_at": c["created_at"],
            }
            for cid, c in self._clusters.items()
        ]
        clusters.sort(key=lambda x: x["created_at"], reverse=True)
        return clusters

    async def resume_cluster(self, cluster_id: str):
        """恢复中断的集群测试

        重新建立 SSH 连接，用原有参数重建测试并启动监控。
        设备上的老化程序可能仍在运行，monitor_aging 步骤会检测并继续监控。
        """
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            raise ValueError(f"集群不存在: {cluster_id}")
        if cluster["status"] != "interrupted":
            raise ValueError(f"只能恢复「中断」状态的集群，当前状态: {cluster['status']}")

        logger.info(f"恢复集群: {cluster_id}, test_type={cluster['test_type']}, {len(cluster['sub_tests'])} 台设备")

        for sub in cluster["sub_tests"]:
            device_ip = sub["device_ip"]
            params = sub.get("params", {})
            try:
                # 用原有的 params 创建新测试（会分配新的 test_id）
                task = await self._test_manager.create_test(
                    test_type=cluster["test_type"],
                    product_model=cluster["product_model"],
                    device_ip=device_ip,
                    device_count=1,
                    params=params,
                    cluster_id=cluster_id,
                )
                # 启动测试（SSH 重连 + 重建 steps + 启动 executor）
                await self._test_manager.start_test(task["test_id"])
                # 更新 sub_tests 中的 test_id
                sub["test_id"] = task["test_id"]
                logger.info(f"集群节点恢复: {device_ip} -> {task['test_id']}")
            except Exception as e:
                logger.error(f"集群节点恢复失败 {device_ip}: {e}")

        cluster["status"] = "running"
        self._save_to_disk()
        logger.info(f"集群恢复完成: {cluster_id}")

    def _find_conflicts(self, new_ips: set) -> list:
        """查找与给定 IP 冲突的正在运行/中断的集群设备"""
        conflicts = []
        for cid, c in self._clusters.items():
            if c["status"] in ("running", "interrupted", "pending"):
                for sub in c.get("sub_tests", []):
                    ip = sub.get("device_ip", "")
                    if ip and ip in new_ips:
                        conflicts.append((ip, cid, c["status"]))
        return conflicts

    def _save_to_disk(self):
        """将集群状态持久化到磁盘"""
        try:
            os.makedirs(RUNTIME_DIR, exist_ok=True)
            persistable = []
            for cid, c in self._clusters.items():
                # 只持久化 running 和 interrupted 状态的集群
                if c["status"] in ("running", "interrupted", "pending"):
                    persistable.append({
                        "cluster_id": cid,
                        "test_type": c["test_type"],
                        "product_model": c["product_model"],
                        "status": c["status"],
                        "sub_tests": c.get("sub_tests", []),
                        "created_at": c["created_at"],
                    })
            file_path = RUNTIME_DIR / "clusters.json"
            if persistable:
                with open(file_path, "w") as f:
                    json.dump(persistable, f, indent=2, ensure_ascii=False)
                logger.debug(f"集群状态已持久化: {len(persistable)} 个集群")
            else:
                # 无活跃集群时删除文件
                if file_path.exists():
                    file_path.unlink()
        except Exception as e:
            logger.error(f"集群持久化失败: {e}")

    def _load_from_disk(self):
        """从磁盘恢复集群状态（后端重启时调用）"""
        file_path = RUNTIME_DIR / "clusters.json"
        if not file_path.exists():
            return

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            for c in data:
                # SSH 连接和 executor 线程已随进程终止而断开，标记为 interrupted
                c["status"] = "interrupted"
                self._clusters[c["cluster_id"]] = c
            logger.info(f"从磁盘恢复 {len(data)} 个集群（状态已标记为 interrupted）")
        except Exception as e:
            logger.warning(f"集群恢复失败: {e}")