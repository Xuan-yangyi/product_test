import io, base64
from fastapi.testclient import TestClient
from backend.config import Config
from backend.main import app


def _png():
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def _upload(client, sn):
    return client.post("/api/v1/captures",
                       data={"sn": sn, "score": "0.9", "ts": "20260911_093841"},
                       files={"image": ("h.png", io.BytesIO(_png()), "image/png")}).json()


def test_list_by_sn_and_get_image(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
    client = TestClient(app)
    up = _upload(client, "BCAC6C25040200956")

    listed = client.get("/api/v1/captures", params={"sn": "BCAC6C25040200956"}).json()
    assert listed["total"] == 1
    item = listed["items"][0]
    assert item["image_url"] == f"/api/v1/captures/{up['id']}/image"

    img = client.get(item["image_url"])
    assert img.status_code == 200
    assert img.headers["content-type"].startswith("image/")


def test_get_image_404(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
    client = TestClient(app)
    assert client.get("/api/v1/captures/999999/image").status_code == 404