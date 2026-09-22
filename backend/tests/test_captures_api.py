"""captures 上传/查询 API 单测 — 用 FastAPI TestClient + 临时 DATA_DIR"""
import io
from fastapi.testclient import TestClient
from backend.config import Config
from backend.main import app


def _png_bytes() -> bytes:
    # 1x1 最小 PNG，避免依赖真实图片
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def test_post_capture_writes_file_and_row(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
    client = TestClient(app)

    resp = client.post("/api/v1/captures",
                       data={"sn": "BCCC8F25062000014", "score": "0.978",
                             "ts": "20260911_093841"},
                       files={"image": ("hit.png", io.BytesIO(_png_bytes()), "image/png")})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] > 0
    assert body["sn"] == "BCCC8F25062000014"
    # 文件真的落盘
    saved = tmp_path / body["image_path"]
    assert saved.exists() and saved.stat().st_size > 0


def test_post_capture_rejects_empty_sn(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
    client = TestClient(app)
    resp = client.post("/api/v1/captures",
                       data={"sn": ""},
                       files={"image": ("x.png", io.BytesIO(_png_bytes()), "image/png")})
    assert resp.status_code == 400