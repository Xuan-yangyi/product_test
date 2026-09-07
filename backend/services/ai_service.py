"""AI 服务 — 日志分析与智能对话"""
import json
import logging
import httpx
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "cfg" / "ai_config.json"


class AiService:
    """AI 分析服务，封装 DeepSeek API 调用"""

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """从 cfg/ai_config.json 加载配置"""
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载 AI 配置失败: {e}")
        return {}

    def reload_config(self):
        """重新加载配置（热更新）"""
        self.config = self._load_config()

    async def chat(self, messages: list, test_id: str = None) -> dict:
        """发送消息到 AI，返回回复内容

        Args:
            messages: 对话历史 [{"role": "user", "content": "..."}]
            test_id: 可选，关联的测试 ID

        Returns:
            {"reply": "...", "model": "...", "usage": {...}}
        """
        endpoint = self.config.get("api_endpoint", "")
        api_key = self.config.get("api_key", "")
        model = self.config.get("model", "DeepSeek-V4-Pro-0813")
        system_prompt = self.config.get("system_prompt", "")

        if not endpoint or not api_key:
            return {"reply": "AI 服务未配置，请检查 cfg/ai_config.json", "error": "config_missing"}

        # 构建完整消息列表（添加 system prompt + 测试上下文）
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})

        # 如果关联了测试，添加测试上下文信息
        if test_id:
            test_context = self._build_test_context(test_id)
            if test_context:
                full_messages.append({"role": "system", "content": test_context})

        full_messages.extend(messages)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messages": full_messages,
                        "model": model,
                        "stream": False,
                        "max_tokens": self.config.get("max_tokens", 4096),
                        "temperature": self.config.get("temperature", 0.7),
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                choice = data.get("choices", [{}])[0]
                reply = choice.get("message", {}).get("content", "")
                return {
                    "reply": reply,
                    "model": data.get("model", model),
                    "usage": data.get("usage", {}),
                }
        except httpx.HTTPStatusError as e:
            logger.error(f"AI API HTTP 错误: {e.response.status_code} - {e.response.text[:500]}")
            return {"reply": f"AI API 请求失败: HTTP {e.response.status_code}", "error": str(e)}
        except Exception as e:
            logger.error(f"AI API 调用异常: {e}")
            return {"reply": f"AI 服务调用失败: {str(e)}", "error": str(e)}

    async def analyze_test_logs(self, test_id: str) -> dict:
        """读取本地日志文件，发送给 AI 分析

        Args:
            test_id: 测试任务 ID

        Returns:
            {"analysis": "...", "log_summary": {...}}
        """
        from ..config import Config

        log_dir = Config.LOG_DIR
        aging_log_path = log_dir / f"aging_{test_id}.log"
        syslog_path = log_dir / f"syslog_{test_id}.log"

        aging_content = ""
        syslog_content = ""

        # 读取老化日志（最后 300 行，避免 token 超限）
        if aging_log_path.exists():
            try:
                with open(aging_log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    aging_content = "".join(lines[-300:])
            except Exception as e:
                logger.error(f"读取老化日志失败: {e}")

        # 读取系统日志（最后 200 行）
        if syslog_path.exists():
            try:
                with open(syslog_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    syslog_content = "".join(lines[-200:])
            except Exception as e:
                logger.error(f"读取系统日志失败: {e}")

        log_summary = {
            "aging_log_lines": len(aging_content.split("\n")) if aging_content else 0,
            "syslog_lines": len(syslog_content.split("\n")) if syslog_content else 0,
            "aging_log_exists": aging_log_path.exists(),
            "syslog_exists": syslog_path.exists(),
        }

        if not aging_content and not syslog_content:
            return {
                "analysis": "暂无日志数据可供分析。请等待老化测试开始并产生日志。",
                "log_summary": log_summary,
            }

        # 构建分析 prompt
        prompt = self._build_analysis_prompt(aging_content, syslog_content, test_id)

        result = await self.chat([{"role": "user", "content": prompt}], test_id=test_id)

        return {
            "analysis": result.get("reply", "分析失败"),
            "log_summary": log_summary,
            "model": result.get("model"),
        }

    def _build_test_context(self, test_id: str) -> str:
        """构建测试上下文信息，让 AI 知道当前测试的日志位置和状态"""
        from ..config import Config

        log_dir = Config.LOG_DIR
        aging_log_path = log_dir / f"aging_{test_id}.log"
        syslog_path = log_dir / f"syslog_{test_id}.log"

        context_parts = [
            f"【当前测试上下文】",
            f"测试 ID: {test_id}",
            f"设备类型: SE9 嵌入式设备",
        ]

        if aging_log_path.exists():
            try:
                with open(aging_log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                context_parts.append(f"老化日志: 已就绪，共 {len(lines)} 行，存放于服务器 {aging_log_path}")
                # 提取日志的时间范围
                first_ts = ""
                last_ts = ""
                for line in lines:
                    if "current time:" in line and not first_ts:
                        first_ts = line.strip()
                    if "current time:" in line:
                        last_ts = line.strip()
                if first_ts:
                    context_parts.append(f"日志时间范围: {first_ts[:120]}")
                if last_ts and last_ts != first_ts:
                    context_parts.append(f"最后记录: {last_ts[:120]}")
            except Exception:
                context_parts.append(f"老化日志: 存在但读取失败 ({aging_log_path})")
        else:
            context_parts.append(f"老化日志: 尚未生成（等待老化测试开始）")

        if syslog_path.exists():
            try:
                with open(syslog_path, "r", encoding="utf-8", errors="ignore") as f:
                    syslog_lines = len(f.readlines())
                context_parts.append(f"系统日志 (syslog): 已就绪，共 {syslog_lines} 行")
            except Exception:
                context_parts.append(f"系统日志: 存在但读取失败")
        else:
            context_parts.append(f"系统日志: 尚未生成")

        context_parts.append("")
        context_parts.append("重要提示：当用户要求分析日志时，请告知用户点击界面上的「📊 分析日志」按钮，系统会自动读取日志内容发送给你。你也可以直接告诉用户你已了解日志位置，请用户点击按钮获取日志内容。不要要求用户手动上传或粘贴日志文件。")

        return "\n".join(context_parts)

    def _build_analysis_prompt(self, aging_log: str, syslog: str, test_id: str) -> str:
        """构建老化测试日志分析 prompt"""
        parts = [
            f"请分析以下嵌入式设备（SE9）老化测试的日志，测试 ID: {test_id}。",
            "",
            "请从以下几个方面进行分析：",
            "1. 测试执行概况（循环次数、耗时、完成状态）",
            "2. 芯片温度变化趋势与异常",
            "3. 错误和警告信息（如有）",
            "4. 性能评估（每轮耗时分布）",
            "5. 优化建议",
            "",
        ]

        if aging_log:
            parts.append("## 老化测试日志")
            parts.append("```")
            parts.append(aging_log[-8000:])  # 限制长度，避免 token 超限
            parts.append("```")
            parts.append("")

        if syslog:
            parts.append("## 系统日志")
            parts.append("```")
            parts.append(syslog[-4000:])
            parts.append("```")
            parts.append("")

        parts.append("请给出详细的分析报告。")
        return "\n".join(parts)

    async def analyze_errors(self, test_id: str) -> dict:
        """专门分析日志中的错误信息

        Args:
            test_id: 测试任务 ID

        Returns:
            {"analysis": "...", "errors_found": [...]}
        """
        from ..config import Config

        log_dir = Config.LOG_DIR
        aging_log_path = log_dir / f"aging_{test_id}.log"
        syslog_path = log_dir / f"syslog_{test_id}.log"

        log_content = ""

        if aging_log_path.exists():
            try:
                with open(aging_log_path, "r", encoding="utf-8", errors="ignore") as f:
                    log_content += f.read()
            except Exception:
                pass

        if syslog_path.exists():
            try:
                with open(syslog_path, "r", encoding="utf-8", errors="ignore") as f:
                    log_content += "\n" + f.read()
            except Exception:
                pass

        if not log_content:
            return {"analysis": "暂无日志数据", "errors_found": []}

        # 先提取错误相关行，减少 token 消耗
        error_lines = []
        for line in log_content.split("\n"):
            lower = line.lower()
            if any(kw in lower for kw in ["error", "fail", "exception", "timeout", "segfault",
                                           "panic", "oom", "killed", "abort", "traceback",
                                           "错误", "失败", "异常", "超时"]):
                error_lines.append(line.strip())

        if not error_lines:
            return {"analysis": "日志中未发现明显的错误或异常信息。", "errors_found": []}

        error_text = "\n".join(error_lines[-200:])  # 限制长度

        prompt = (
            "请分析以下老化测试日志中的错误和异常信息，测试 ID: {test_id}。\n\n"
            "请：\n"
            "1. 分类错误类型（硬件错误、软件错误、超时、配置问题等）\n"
            "2. 指出最严重的错误\n"
            "3. 给出排查建议\n\n"
            "## 错误日志\n```\n{error_text}\n```"
        ).format(test_id=test_id, error_text=error_text[-6000:])

        result = await self.chat([{"role": "user", "content": prompt}], test_id=test_id)

        return {
            "analysis": result.get("reply", "分析失败"),
            "errors_found": error_lines[-50:],
            "model": result.get("model"),
        }

    def get_config_status(self) -> dict:
        """获取配置状态（不返回 api_key）"""
        return {
            "configured": bool(self.config.get("api_key")),
            "endpoint": self.config.get("api_endpoint", ""),
            "model": self.config.get("model", ""),
            "auto_analyze_on_complete": self.config.get("auto_analyze_on_complete", True),
            "auto_analyze_on_error": self.config.get("auto_analyze_on_error", True),
        }


# 全局单例
_ai_service: Optional[AiService] = None


def get_ai_service() -> AiService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AiService()
    return _ai_service