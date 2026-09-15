"""SN 抓拍 API — 接收 SE9 上传的 SN+图片，入库并提供查询。"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException
from ..config import Config
from ..services.sn_capture_service import SnCaptureService

router = APIRouter(prefix="/api/v1", tags=["captures"])

_ALLOWED_CT = {"image/jpeg", "image/png"}
_MAX_BYTES = 20 * 1024 * 1024  # 20MB 上限


def get_service() -> SnCaptureService:
    return SnCaptureService()


def parse_ts(ts: str) -> Optional[datetime]:
    """接受 ISO 或 YYYYmmdd_HHMMSS；解析失败返回 None。"""
    if not ts:
        return None
    for fmt in ("%Y%m%d_%H%M%S",):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


@router.post("/captures")
async def upload_capture(
    sn: str = Form(""),
    score: float = Form(0.0),
    ts: str = Form(""),
    side: str = Form("front"),                       # v2.1 正/反面; SE9 uploader 带上, 旧客户端不带默认 front
    image: UploadFile = File(...),
):
    """接收 SE9 上传的 SN + 命中图，落盘 + 入库。"""
    sn = (sn or "").strip()
    if not sn:
        raise HTTPException(status_code=400, detail="sn 不能为空")
    side = (side or "front").strip().lower()
    if side not in ("front", "back"):
        side = "front"                               # 未知值兜底为 front, 不 400(容错优先)
    if image.content_type not in _ALLOWED_CT:
        raise HTTPException(status_code=400, detail=f"仅支持图片: {_ALLOWED_CT}")

    data = await image.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="空图片")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="图片过大")

    captured_at = parse_ts(ts)
    stamp = (captured_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
    ext = ".png" if image.content_type == "image/png" else ".jpg"
    rel = Path("sn_captures") / sn / f"{stamp}_{side}{ext}"   # v2.1 带 side, 正反同秒不覆盖
    abs_path = Config.DATA_DIR / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(data)

    svc = get_service()
    return svc.add(sn=sn, image_path=str(rel), score=score,
                   captured_at=captured_at, source="SE9", side=side)   # v2.1 落 side


@router.get("/captures")
async def list_captures(
    sn: Optional[str] = Query(None),
    start: Optional[str] = Query(None, description="入库时间起(含)，YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="入库时间止(含当天)，YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """按 SN（可选）+ 入库时间范围（可选）分页查询抓拍列表。"""
    start_dt = parse_ts(start) if start else None
    end_dt = parse_ts(end) if end else None
    if end_dt:
        end_dt = end_dt + timedelta(days=1)  # 含当天：转成次日 0 点作为开区间上界
    svc = get_service()
    ret = svc.list(sn=sn, limit=limit, offset=offset, start=start_dt, end=end_dt)
    for it in ret["items"]:
        it["image_url"] = f"/api/v1/captures/{it['id']}/image"
    return ret


@router.get("/captures/{cap_id}/image")
async def get_capture_image(cap_id: int):
    """返回某条抓拍的图片文件。"""
    from fastapi.responses import FileResponse
    svc = get_service()
    row = svc.get(cap_id)
    if not row:
        raise HTTPException(status_code=404, detail="抓拍不存在")
    abs_path = Config.DATA_DIR / row["image_path"]
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="图片文件缺失")
    return FileResponse(str(abs_path))
