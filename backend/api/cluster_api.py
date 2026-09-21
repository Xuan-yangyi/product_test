"""集群老化 API"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from ..models.schemas import ClusterTestRequest, ClusterDevice
from ..services.cluster_manager import ClusterManager
from ..config import Config
from .dependencies import get_test_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["cluster"])

# 全局单例
cluster_manager: ClusterManager = None


def get_cluster_manager() -> ClusterManager:
    global cluster_manager
    if cluster_manager is None:
        cluster_manager = ClusterManager(get_test_manager())
    return cluster_manager


@router.post("/tests/cluster")
async def create_cluster_test(
    req: ClusterTestRequest,
    cm: ClusterManager = Depends(get_cluster_manager),
):
    """创建集群老化测试"""
    try:
        cluster = await cm.create_cluster(
            test_type=req.test_type,
            product_model=req.product_model,
            devices=[d.model_dump() for d in req.devices],
            write_oem=req.write_oem,
            oem_profile=req.oem_profile,
        )
        return cluster
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tests/cluster/{cluster_id}/start")
async def start_cluster_test(
    cluster_id: str,
    cm: ClusterManager = Depends(get_cluster_manager),
):
    """启动集群老化测试"""
    try:
        await cm.start_cluster(cluster_id)
        return {"cluster_id": cluster_id, "status": "running"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tests/cluster/{cluster_id}/stop")
async def stop_cluster_test(
    cluster_id: str,
    cm: ClusterManager = Depends(get_cluster_manager),
):
    """停止集群老化测试"""
    try:
        await cm.stop_cluster(cluster_id)
        return {"cluster_id": cluster_id, "status": "stopped"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/tests/cluster/{cluster_id}/resume")
async def resume_cluster_test(
    cluster_id: str,
    cm: ClusterManager = Depends(get_cluster_manager),
):
    """恢复中断的集群测试（重新连接 SSH 并启动监控）"""
    try:
        await cm.resume_cluster(cluster_id)
        return {"cluster_id": cluster_id, "status": "running"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/tests/cluster/{cluster_id}")
async def delete_cluster_test(
    cluster_id: str,
    cm: ClusterManager = Depends(get_cluster_manager),
):
    """删除集群测试"""
    try:
        cm.delete_cluster(cluster_id)
        return {"cluster_id": cluster_id, "status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/tests/cluster/{cluster_id}")
async def get_cluster(
    cluster_id: str,
    cm: ClusterManager = Depends(get_cluster_manager),
):
    """获取集群状态"""
    try:
        return cm.get_cluster_status(cluster_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/tests/cluster")
async def list_clusters(
    cm: ClusterManager = Depends(get_cluster_manager),
):
    """获取所有集群列表"""
    return {"clusters": cm.get_all_clusters()}


@router.get("/tests/{test_id}/temperature")
async def get_temperature_data(test_id: str):
    """获取温度数据（从 aging log 解析）"""
    from ..services.log_parser import parse_temperature
    return parse_temperature(test_id, Config.LOG_DIR)


@router.get("/tests/{test_id}/loop-timing")
async def get_loop_timing(test_id: str):
    """获取每轮时间分布（含运行中状态和重启检测）"""
    from ..services.log_parser import parse_loop_timing
    return parse_loop_timing(test_id, Config.LOG_DIR)


MODULE_NAMES = ["cpu", "dpu", "jpu", "tpu", "vpss_convertto", "vpss_csc", "vpu_dec", "vpu_enc"]


@router.get("/tests/{test_id}/module-log/{module}")
async def get_module_log(test_id: str, module: str, tail: int = 200):
    """读取 SE9 设备上的模块老化日志

    从 /data/soc_aging/result/aging_{module}.log 读取最后 tail 行
    """
    from ..engine.ssh_client import SSHClient

    # 获取测试的 device_ip
    tm = get_test_manager()
    task = tm.get_test(test_id)
    if not task:
        return {"lines": [], "message": f"测试任务不存在: {test_id}"}

    device_ip = task.get("device_ip")
    if not device_ip:
        return {"lines": [], "message": "测试未关联设备 IP"}

    if module not in MODULE_NAMES:
        return {"lines": [], "message": f"未知模块: {module}，可用: {MODULE_NAMES}"}

    ssh = SSHClient()
    try:
        if not ssh.connect(device_ip, user="linaro", password="linaro", timeout=10):
            return {"lines": [], "message": f"SSH 连接设备 {device_ip} 失败"}

        remote_path = f"/data/soc_aging/result/aging_{module}.log"
        stdout, stderr, code = ssh.exec_cmd(
            f"tail -n {tail} {remote_path} 2>/dev/null || echo ''",
            timeout=15, sudo=True, sudo_password="linaro"
        )

        if stdout.strip():
            lines = [l.rstrip() for l in stdout.split("\n") if l.strip()]
        else:
            lines = []

        return {"lines": lines, "module": module, "count": len(lines),
                "message": None if lines else "日志文件为空或不存在"}
    finally:
        ssh.close()