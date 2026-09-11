"""SnCaptureService 单测 — 复用 SQLite，落 tmp DATA_DIR"""
from datetime import datetime
from backend.config import Config
from backend.services.sn_capture_service import SnCaptureService


def test_add_then_list_and_get(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "DATA_DIR", tmp_path)  # DB 落临时目录
    svc = SnCaptureService()

    ret = svc.add(sn="BCCC8F25062000014",
                  image_path="sn_captures/BCCC8F25062000014/20260911_093841.jpg",
                  score=0.978,
                  captured_at=datetime(2026, 9, 11, 9, 38, 41),
                  source="SE9")
    assert ret["id"] > 0
    assert ret["sn"] == "BCCC8F25062000014"

    listed = svc.list(sn="BCCC8F25062000014", limit=50, offset=0)
    assert listed["total"] == 1
    assert listed["items"][0]["score"] == 0.978

    one = svc.get(ret["id"])
    assert one is not None
    assert one["image_path"].endswith(".jpg")

    # sn 过滤：查不到返回空
    assert svc.list(sn="NOPE", limit=50, offset=0)["total"] == 0
