"""SN 抓拍服务 — SQLite 读写，复用 create_session_factory（对齐 ResultService 写法）。"""
import logging
from datetime import datetime
from typing import Optional
from ..models.db_models import create_session_factory
from ..models.sn_capture import SnCapture  # 导入即注册到 Base，create_all 会建表

logger = logging.getLogger(__name__)


class SnCaptureService:
    def __init__(self):
        self._session_factory = create_session_factory()

    def add(self, sn: str, image_path: str, score: float,
            captured_at: Optional[datetime], source: str = "SE9") -> dict:
        session = self._session_factory()
        try:
            row = SnCapture(sn=sn, image_path=image_path, score=score or 0.0,
                            captured_at=captured_at, source=source)
            session.add(row)
            session.commit()
            return {"id": row.id, "sn": row.sn, "image_path": row.image_path}
        finally:
            session.close()

    def list(self, sn: Optional[str], limit: int = 50, offset: int = 0) -> dict:
        session = self._session_factory()
        try:
            q = session.query(SnCapture)
            if sn:
                q = q.filter(SnCapture.sn == sn)
            total = q.count()
            rows = (q.order_by(SnCapture.id.desc())
                     .offset(offset).limit(limit).all())
            items = [self._to_dict(r) for r in rows]
            return {"total": total, "items": items}
        finally:
            session.close()

    def get(self, cap_id: int) -> Optional[dict]:
        session = self._session_factory()
        try:
            r = session.query(SnCapture).filter(SnCapture.id == cap_id).first()
            return self._to_dict(r) if r else None
        finally:
            session.close()

    @staticmethod
    def _to_dict(r: SnCapture) -> dict:
        return {
            "id": r.id,
            "sn": r.sn,
            "score": r.score,
            "captured_at": r.captured_at.isoformat() if r.captured_at else None,
            "image_path": r.image_path,
            "source": r.source,
        }
