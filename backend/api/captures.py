"""SN 抓拍 API — 接收 SE9 上传的 SN+图片，入库并提供查询。"""
from datetime import datetime
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
    image: UploadFile = File(...),
):
    """接收 SE9 上传的 SN + 命中图，落盘 + 入库。"""
    sn = (sn or "").strip()
    if not sn:
        raise HTTPException(status_code=400, detail="sn 不能为空")
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
    rel = Path("sn_captures") / sn / f"{stamp}{ext}"
    abs_path = Config.DATA_DIR / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(data)

    svc = get_service()
    return svc.add(sn=sn, image_path=str(rel), score=score,
                   captured_at=captured_at, source="SE9")