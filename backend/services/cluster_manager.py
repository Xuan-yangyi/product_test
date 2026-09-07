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


class ClusterManager:
    """集群老化管理器

    管理多个设备的集群老化测试。
    每个设备独立的 SSH 连接、独立的测试步骤、独立的日志。
    """

    def __init__(self, test_manager):
        self._test_manager = test_manager
        self._clusters: Dict[str, dict] = {}
        self._load_existing_clusters()

    def _load_existing_clusters(self):
        """从磁盘加载已有的集群状态"""
        clusters_dir = Config.DATA_DIR / "clusters"
        if not clusters_dir.exists():
            return
        for f in clusters_dir.glob("*.json"):
            try:
                with open(f) as fp:
                    cluster = json.load(fp)
                self._clusters[cluster["cluster_id"]] = cluster
                logger.info(f"加载集群: {cluster['cluster_id']} ({len(cluster.get('sub_tests', []))} 节点)")
            except Exception as e:
                logger.error(f"加载集群文件失败 {f}: {e}")

    async def create_cluster(self, test_type: str, product_model: str,
                             devices: List[dict], write_oem: bool = False) -> dict:
        """创建集群老化测试

        Args:
            test_type: 测试类型（如 se9_aging_test）
            product_model: 产品型号
            devices: 设备列表 [{"ip": "10.80.40.36", "params": {"loop": 10, "reboot": 3}}]
            write_oem: 是否写入 OEM 信息

        Returns:
            cluster 信息字典
        """
        cluster_id = str(uuid.uuid4())[:12]
        sub_tests = []

        for device in devices:
            device_params = device.get("params", {})
            if write_oem:
                device_params["write_oem"] = True

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

        self._save_cluster(cluster_id)
        logger.info(f"创建集群: {cluster_id}, {len(sub_tests)} 台设备")
        return self._clusters[cluster_id]

    async def start_cluster(self, cluster_id: str):
        """启动集群中所有子测试"""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            raise ValueError(f"集群不存在: {cluster_id}")

        cluster["status"] = "running"
        self._save_cluster(cluster_id)

        for sub in cluster["sub_tests"]:
            try:
                await self._test_manager.start_test(sub["test_id"])
                logger.info(f"集群节点启动: {sub['device_ip']} -> {sub['test_id']}")
            except Exception as e:
                logger.error(f"集群节点启动失败 {sub['device_ip']}: {e}")

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
        self._save_cluster(cluster_id)

    def get_cluster(self, cluster_id: str) -> Optional[dict]:
        """获取集群信息"""
        return self._clusters.get(cluster_id)

    def get_cluster_status(self, cluster_id: str) -> dict:
        """获取集群状态，聚合所有子测试进度"""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            raise ValueError(f"集群不存在: {cluster_id}")

        nodes = []
        completed_count = 0
        failed_count = 0

        for sub in cluster["sub_tests"]:
            task = self._test_manager.get_test(sub["test_id"]) or {}
            status = task.get("status", "unknown")
            if status == "completed":
                completed_count += 1
            elif status == "failed":
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
        if completed_count == total:
            cluster["status"] = "completed"
        elif failed_count > 0 and (completed_count + failed_count) == total:
            cluster["status"] = "failed"
        self._save_cluster(cluster_id)

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
        """获取所有集群列表"""
        return [
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

    def _save_cluster(self, cluster_id: str):
        """持久化集群状态到文件"""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            return
        clusters_dir = Config.DATA_DIR / "clusters"
        clusters_dir.mkdir(parents=True, exist_ok=True)
        path = clusters_dir / f"{cluster_id}.json"
        try:
            # 不保存不可序列化的对象
            save_data = {
                "cluster_id": cluster["cluster_id"],
                "test_type": cluster["test_type"],
                "product_model": cluster["product_model"],
                "status": cluster["status"],
                "sub_tests": cluster["sub_tests"],
                "created_at": cluster["created_at"],
            }
            with open(path, "w") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"保存集群失败: {e}")