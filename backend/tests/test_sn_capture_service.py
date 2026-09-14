"""SnCaptureService 单测 — 复用 SQLite，落 tmp DATA_DIR"""
from datetime import datetime, timedelta
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


def test_list_filter_by_uploaded_at(tmp_path, monkeypatch):
    """按入库时间 uploaded_at 做日期范围过滤（半开区间 [start, end)）"""
    monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
    svc = SnCaptureService()
    svc.add(sn="RANGE01",
            image_path="sn_captures/RANGE01/x.jpg",
            score=0.9,
            captured_at=datetime(2026, 1, 1, 0, 0, 0),  # 抓拍时间故意设很早
            source="SE9")
    now = datetime.now()  # uploaded_at 由 DB default=now 自动打，落在此刻附近

    # 返回结构带 uploaded_at
    got = svc.list(sn="RANGE01", start=now - timedelta(days=1), end=now + timedelta(days=1))
    assert got["total"] == 1
    assert got["items"][0]["uploaded_at"] is not None

    # 起点在明天 → 入库时间早于起点，查不到
    assert svc.list(sn="RANGE01", start=now + timedelta(days=1))["total"] == 0
    # 终点在昨天(开区间上界) → 入库时间晚于终点，查不到
    assert svc.list(sn="RANGE01", end=now - timedelta(days=1))["total"] == 0
