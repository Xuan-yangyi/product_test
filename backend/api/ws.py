"""WebSocket 端点"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket 连接管理
active_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws/v1/tests/{test_id}")
async def websocket_test(websocket: WebSocket, test_id: str):
    """WebSocket 连接 - 测试实时状态推送

    接收消息：
    - {"type": "subscribe", "topics": ["log", "progress", "interaction"]}

    推送消息：
    - {"type": "log", "data": {"level": "INFO", "source": "chip_check", "message": "..."}}
    - {"type": "step_update", "data": {"step_index": 0, "status": "pass", ...}}
    - {"type": "status_change", "data": {"old": "running", "new": "completed"}}
    - {"type": "interaction", "data": {"step_name": "...", "message": "...", ...}}
    """
    await websocket.accept()
    active_connections[test_id] = websocket
    logger.info(f"WebSocket 连接: test_id={test_id}")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            logger.debug(f"WebSocket 收到 [{test_id}]: {msg}")

            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg.get("type") == "subscribe":
                await websocket.send_json({
                    "type": "subscribed",
                    "topics": msg.get("topics", []),
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket 断开: test_id={test_id}")
    except Exception as e:
        logger.error(f"WebSocket 异常 [{test_id}]: {e}")
    finally:
        active_connections.pop(test_id, None)


async def broadcast_to_test(test_id: str, msg_type: str, data: dict):
    """向指定测试推送消息"""
    ws = active_connections.get(test_id)
    if ws:
        try:
            await ws.send_json({"type": msg_type, "data": data})
        except Exception as e:
            logger.error(f"WebSocket 推送失败 [{test_id}]: {e}")


async def broadcast_to_all(msg_type: str, data: dict):
    """向所有连接的 WebSocket 推送消息"""
    for test_id, ws in list(active_connections.items()):
        try:
            await ws.send_json({"type": msg_type, "data": data})
        except Exception:
            active_connections.pop(test_id, None)
