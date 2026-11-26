"""AI 报告存储（磁盘持久化 + 内存缓存，TTL 30 分钟）

为什么落盘：服务重启/多实例时，纯内存会导致“刚生成的报告点开就 404”。
文件路径：data/ai_reports/<report_id>.json
"""
import json
import os
import threading
import time
import uuid

from ..config import Config

TTL_SECONDS = 30 * 60

REPORT_DIR = Config.DATA_DIR / "ai_reports"

_lock = threading.Lock()
_cache: dict = {}


def _path(report_id: str):
    return REPORT_DIR / f"{report_id}.json"


def _cleanup(now: float) -> None:
    """删除过期报告文件（加锁调用）"""
    try:
        if not REPORT_DIR.exists():
            return
        for f in REPORT_DIR.glob("*.json"):
            try:
                if now - f.stat().st_mtime > TTL_SECONDS:
                    f.unlink(missing_ok=True)
                    _cache.pop(f.stem, None)
            except Exception:
                pass
    except Exception:
        pass


def save(payload: dict) -> str:
    rid = uuid.uuid4().hex[:12]
    record = {**payload, "report_id": rid, "created_at": time.time()}
    with _lock:
        _cache[rid] = record
        _cleanup(time.time())
        try:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            with open(_path(rid), "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
        except Exception:
            # 落盘失败不影响主流程（内存里仍可读）
            pass
    return rid


def get(report_id: str):
    now = time.time()
    with _lock:
        item = _cache.get(report_id)
        if not item:
            p = _path(report_id)
            try:
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        item = json.load(f)
                    _cache[report_id] = item
            except Exception:
                item = None

        if not item:
            return None

        age = now - float(item.get("created_at", 0))
        if age > TTL_SECONDS:
            _cache.pop(report_id, None)
            try:
                _path(report_id).unlink(missing_ok=True)
            except Exception:
                pass
            return None

        data = dict(item)

    data["age_seconds"] = int(age)
    data["expires_in"] = max(0, int(TTL_SECONDS - age))
    return data