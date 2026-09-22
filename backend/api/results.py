"""测试结果 API"""
import os
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import io
from ..services.result_service import ResultService
from ..config import Config

router = APIRouter(prefix="/api/v1", tags=["results"])


def get_result_service() -> ResultService:
    return ResultService()


@router.get("/results")
async def query_results(
    serial_number: Optional[str] = Query(None),
    test_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    device_ip: Optional[str] = Query(None),
    cluster_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rs: ResultService = Depends(get_result_service),
):
    """查询测试结果"""
    filters = {
        "serial_number": serial_number,
        "test_type": test_type,
        "status": status,
        "device_ip": device_ip,
        "cluster_id": cluster_id,
        "start_date": start_date,
        "end_date": end_date,
        "page": page,
        "page_size": page_size,
    }
    return rs.query_results(filters)


@router.get("/results/{test_id}/logs")
async def get_test_logs(test_id: str):
    """获取测试日志（老化日志）"""
    log_dir = Config.LOG_DIR
    # 优先查找老化日志，其次是一般测试日志
    log_file = log_dir / f"aging_{test_id}.log"
    if not log_file.exists():
        log_file = log_dir / f"{test_id}.log"

    if not log_file.exists():
        return {"test_id": test_id, "log_file": None, "lines": [], "total_lines": 0,
                "message": "日志文件尚未生成，请等待老化监控步骤开始"}

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return {
            "test_id": test_id,
            "log_file": str(log_file),
            "lines": [line.rstrip() for line in lines[-500:]],
            "total_lines": len(lines),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{test_id}/syslog")
async def get_test_syslog(test_id: str):
    """获取测试系统日志（syslog），自动过滤测试框架噪音"""
    import re
    log_dir = Config.LOG_DIR
    syslog_file = log_dir / f"syslog_{test_id}.log"

    # 噪音过滤器：排除测试框架自身的 sudo/SSH 会话日志
    _NOISE_RE = re.compile(
        r'pam_unix\((sudo|sshd):session\): session (opened|closed)'
        r'|sshd\[\d+\]: Accepted password for '
        r'|sshd\[\d+\]: pam_unix\(sshd:session\): session (opened|closed)'
        r'|systemd-logind\[\d+\]: (New|Removed) session \S+ of user'
        r'|systemd\[\d+\]: (Started|Removed) [Ss]ession \S+ of [Uu]ser'
        r'|sudo\[\d+\]:\s+\S+\s+:\s+PWD=.*;\s*USER=root\s*;\s*COMMAND='
        r'|sudo\[\d+\]:\s+pam_unix\(sudo:session\):'
    )

    if not syslog_file.exists():
        return {"test_id": test_id, "log_file": None, "lines": [], "total_lines": 0,
                "message": "系统日志文件尚未生成，请等待 SSH 连接建立后开始采集"}

    try:
        with open(syslog_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        filtered = [line.rstrip() for line in lines if not _NOISE_RE.search(line)]
        return {
            "test_id": test_id,
            "log_file": str(syslog_file),
            "lines": filtered[-500:],
            "total_lines": len(filtered),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/statistics")
async def get_statistics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    rs: ResultService = Depends(get_result_service),
):
    """获取测试结果统计"""
    filters = {}
    if start_date:
        filters["start_date"] = start_date
    if end_date:
        filters["end_date"] = end_date
    return rs.get_statistics(filters)


@router.get("/results/{test_id}")
async def get_test_result(test_id: str, rs: ResultService = Depends(get_result_service)):
    """获取单个测试结果详情（含步骤）"""
    detail = rs.get_test_detail(test_id)
    if not detail:
        raise HTTPException(status_code=404, detail="测试结果不存在")
    return detail


@router.get("/results/export/csv")
async def export_results_csv(
    test_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    rs: ResultService = Depends(get_result_service),
):
    """导出测试结果为 CSV 文件"""
    filters = {
        "test_type": test_type,
        "status": status,
        "start_date": start_date,
        "end_date": end_date,
    }
    csv_content = rs.export_csv(filters)
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=test_results.csv"},
    )
