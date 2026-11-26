"""AI 分析 API"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..services.ai_service import get_ai_service
from ..services.claude_analyzer import get_claude_analyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


class AiChatRequest(BaseModel):
    messages: list  # [{"role": "user", "content": "..."}]
    test_id: str = None


class AiChatResponse(BaseModel):
    reply: str
    model: str = ""
    usage: dict = None


@router.post("/chat", response_model=AiChatResponse)
async def ai_chat(req: AiChatRequest):
    """AI 对话接口"""
    ai = get_ai_service()
    result = await ai.chat(req.messages, test_id=req.test_id)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result.get("reply", "AI 服务错误"))
    return AiChatResponse(
        reply=result.get("reply", ""),
        model=result.get("model", ""),
        usage=result.get("usage"),
    )


@router.post("/analyze/{test_id}")
async def analyze_test_logs(test_id: str):
    """分析指定测试的日志"""
    ai = get_ai_service()
    result = await ai.analyze_test_logs(test_id)
    return result


@router.post("/analyze/{test_id}/errors")
async def analyze_test_errors(test_id: str):
    """分析指定测试日志中的错误"""
    ai = get_ai_service()
    result = await ai.analyze_errors(test_id)
    return result


@router.get("/config")
async def get_ai_config():
    """获取 AI 配置状态（不返回 api_key）"""
    ai = get_ai_service()
    return ai.get_config_status()


@router.post("/config/reload")
async def reload_ai_config():
    """重新加载 AI 配置（热更新）"""
    ai = get_ai_service()
    ai.reload_config()
    return {"status": "ok", "config": ai.get_config_status()}


@router.post("/claude-analyze/{test_id}")
async def claude_analyze(test_id: str):
    """使用本地 Claude CLI 进行深度日志分析"""
    analyzer = get_claude_analyzer()
    result = await analyzer.analyze(test_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("analysis", "分析失败"))
    return result

class SummaryRequest(BaseModel):
    filters: dict = {}


@router.get("/summary/engine")
async def ai_summary_engine():
    """批量汇总分析引擎状态（Claude 是否可用 / provider 偏好）"""
    from ..services.summary_analyzer import get_summary_analyzer
    return get_summary_analyzer().engine_status()


@router.post("/summary/{kind}")
async def ai_summary(kind: str, req: SummaryRequest | None = None):
    """批量结果汇总分析

    kind: interface（接口测试）/ aging（老化测试）/ all（全部）
    引擎策略：本地 Claude CLI 优先，失败回退到 API Key
    """
    if kind not in ("interface", "aging", "all"):
        raise HTTPException(status_code=400, detail="kind 必须为 interface/aging/all")
    from ..services.summary_analyzer import get_summary_analyzer
    filters = (req.filters if req else {}) or {}
    return await get_summary_analyzer().analyze(kind, filters)
