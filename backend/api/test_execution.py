"""测试执行 API"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from ..services.test_manager import TestManager
from ..models.schemas import (
    TestRunRequest, TestRunResponse, TestInfo,
    InteractionResponse, InteractionRequest,
)
from .dependencies import get_test_manager

router = APIRouter(prefix="/api/v1", tags=["tests"])


@router.post("/tests", response_model=TestRunResponse)
async def create_test(req: TestRunRequest, tm: TestManager = Depends(get_test_manager)):
    """创建测试任务"""
    task = await tm.create_test(
        test_type=req.test_type,
        product_model=req.product_model,
        serial_port=req.serial_port,
        device_ip=req.device_ip,
        device_count=req.device_count,
        params=req.params,
    )
    return TestRunResponse(
        test_id=task["test_id"],
        status=task["status"],
        created_at=task["created_at"],
    )


@router.post("/tests/{test_id}/start")
async def start_test(test_id: str, tm: TestManager = Depends(get_test_manager)):
    """启动测试"""
    try:
        await tm.start_test(test_id)
        return {"test_id": test_id, "status": "running"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/tests/{test_id}/stop")
async def stop_test(test_id: str, tm: TestManager = Depends(get_test_manager)):
    """停止测试"""
    await tm.stop_test(test_id)
    return {"test_id": test_id, "status": "stopped"}


@router.post("/tests/{test_id}/pause")
async def pause_test(test_id: str, tm: TestManager = Depends(get_test_manager)):
    """暂停测试"""
    await tm.pause_test(test_id)
    return {"test_id": test_id, "status": "paused"}


@router.post("/tests/{test_id}/resume")
async def resume_test(test_id: str, tm: TestManager = Depends(get_test_manager)):
    """恢复测试"""
    await tm.resume_test(test_id)
    return {"test_id": test_id, "status": "running"}


@router.post("/tests/{test_id}/interact")
async def resolve_interaction(test_id: str, resp: InteractionResponse,
                              tm: TestManager = Depends(get_test_manager)):
    """响应交互请求"""
    await tm.resolve_interaction(test_id, resp.dict())
    return {"status": "ok"}


@router.get("/tests/{test_id}", response_model=TestInfo)
async def get_test(test_id: str, tm: TestManager = Depends(get_test_manager)):
    """获取测试详情"""
    task = tm.get_test(test_id)
    if not task:
        raise HTTPException(status_code=404, detail="测试任务不存在")
    return tm._clean_task(task)


@router.get("/tests")
async def list_tests(tm: TestManager = Depends(get_test_manager)):
    """获取所有测试任务"""
    return {"tests": tm.get_all_tests()}


@router.get("/tests/{test_id}/loop-timing")
async def get_loop_timing(test_id: str):
    """获取老化测试每轮耗时数据"""
    from ..services.log_parser import parse_loop_timing
    from ..config import Config
    return parse_loop_timing(test_id, Config.LOG_DIR)


@router.get("/tests/{test_id}/temperature")
async def get_temperature(test_id: str):
    """获取老化测试温度变化数据"""
    from ..services.log_parser import parse_temperature
    from ..config import Config
    return parse_temperature(test_id, Config.LOG_DIR)


@router.get("/tests/{test_id}/module-log/{module}")
async def get_module_log(test_id: str, module: str):
    """获取老化测试指定模块的日志"""
    from ..services.log_parser import filter_module_log
    from ..config import Config
    return filter_module_log(test_id, module, Config.LOG_DIR)
