"""Claude CLI 分析服务 — 调用本地 Claude 进行深度日志分析"""
import logging
import subprocess
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Claude CLI 超时设置（秒），大日志文件可能需要更长时间
CLAUDE_TIMEOUT = 300

# Claude CLI 可执行文件路径
CLAUDE_BIN = "/usr/local/bin/claude"


class ClaudeAnalyzer:
    """使用本地 Claude CLI 进行日志深度分析"""

    async def analyze(self, test_id: str) -> dict:
        """调用 Claude CLI 分析指定测试的日志

        Args:
            test_id: 测试任务 ID

        Returns:
            {"analysis": "...", "success": True/False, "error": "..."}
        """
        from ..config import Config

        log_dir = Config.LOG_DIR

        # 检查日志文件是否存在
        aging_log = log_dir / f"aging_{test_id}.log"
        syslog = log_dir / f"syslog_{test_id}.log"

        if not aging_log.exists() and not syslog.exists():
            return {
                "analysis": "暂无日志文件可供分析。请等待老化测试开始并产生日志。",
                "success": False,
                "error": "no_log_files",
            }

        # 构建 Claude 分析 prompt
        prompt = self._build_prompt(test_id, aging_log, syslog)

        try:
            # 在 log 目录下运行 Claude，使其能直接读取文件
            result = await self._run_claude(prompt, str(log_dir))
            return {"analysis": result, "success": True}
        except subprocess.TimeoutExpired:
            logger.error(f"[{test_id}] Claude 分析超时 ({CLAUDE_TIMEOUT}s)")
            return {
                "analysis": f"Claude 分析超时（{CLAUDE_TIMEOUT} 秒），日志文件可能过大。请尝试使用「分析日志」按钮进行快速分析。",
                "success": False,
                "error": "timeout",
            }
        except FileNotFoundError:
            return {
                "analysis": "Claude CLI 未安装或路径不正确。请确认 claude 命令可用。",
                "success": False,
                "error": "claude_not_found",
            }
        except Exception as e:
            logger.error(f"[{test_id}] Claude 分析异常: {e}")
            return {
                "analysis": f"Claude 分析失败: {str(e)}",
                "success": False,
                "error": str(e),
            }

    def _build_prompt(self, test_id: str, aging_log: Path, syslog: Path) -> str:
        """构建 Claude 分析 prompt"""
        prompt_parts = [
            f"请对嵌入式设备 SE9 的老化测试日志进行深度分析，测试 ID: {test_id}。",
            "",
            "请直接读取以下文件进行分析：",
        ]

        if aging_log.exists():
            size_kb = aging_log.stat().st_size / 1024
            prompt_parts.append(f"1. 老化日志: {aging_log.name} ({size_kb:.1f} KB)")
        else:
            prompt_parts.append(f"1. 老化日志: 不存在")

        if syslog.exists():
            size_kb = syslog.stat().st_size / 1024
            prompt_parts.append(f"2. 系统日志: {syslog.name} ({size_kb:.1f} KB)")
        else:
            prompt_parts.append(f"2. 系统日志: 不存在")

        prompt_parts.extend([
            "",
            "请从以下维度进行分析，生成详细的分析报告：",
            "",
            "## 1. 测试执行概况",
            "- 测试起止时间、总时长",
            "- 循环次数、完成状态",
            "- 是否有中断、重启、异常退出",
            "",
            "## 2. 芯片性能分析",
            "- 温度变化趋势（起始温度、最高温度、平均温度）",
            "- 是否存在温度异常或过热",
            "- 时钟频率是否正常",
            "",
            "## 3. 模块运行状态",
            "- 各模块（CPU/DPU/JPU/TPU/VPSS/VPU）运行情况",
            "- 每轮耗时分布与趋势",
            "- 是否有模块异常",
            "",
            "## 4. 异常检测",
            "- 错误码、异常堆栈、超时",
            "- 系统日志中的警告和错误",
            "- 异常发生的时间点和频率",
            "",
            "## 5. 优化建议",
            "- 针对发现的问题提出改进方向",
            "- 测试参数优化建议",
            "",
            "请用中文回复，报告应详细、专业、可操作。",
        ])

        return "\n".join(prompt_parts)

    async def _run_claude(self, prompt: str, working_dir: str) -> str:
        """运行 Claude CLI 并返回结果

        使用 subprocess 在后台运行 claude -p --print 模式
        """
        # 设置环境变量，避免模型警告
        env = os.environ.copy()
        env.setdefault("CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT", "1")

        # 构建命令
        cmd = [
            CLAUDE_BIN,
            "-p", prompt,
            "--print",
            "--output-format", "text",
            "--max-turns", "10",
            "--permission-mode", "acceptEdits",
        ]

        logger.info(f"启动 Claude 分析, 工作目录: {working_dir}")

        # 运行 Claude CLI
        process = await _run_subprocess_async(cmd, env=env, cwd=working_dir, timeout=CLAUDE_TIMEOUT)

        stdout = process.stdout.decode("utf-8", errors="replace")
        stderr = process.stderr.decode("utf-8", errors="replace")

        if process.returncode != 0 and not stdout.strip():
            error_msg = stderr[:500] if stderr else f"退出码: {process.returncode}"
            raise RuntimeError(f"Claude CLI 执行失败: {error_msg}")

        # 清理输出：移除可能的模型警告和启动信息
        lines = stdout.split("\n")
        cleaned_lines = []
        skip_prefixes = [
            "[claude-code:",
            '"DeepSeek-V4-Pro" is not',
            'CLAUDE_CODE_DISABLE',
        ]
        for line in lines:
            if any(line.startswith(prefix) for prefix in skip_prefixes):
                continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()


async def _run_subprocess_async(cmd: list, env: dict = None, cwd: str = None,
                                 timeout: int = 180) -> subprocess.CompletedProcess:
    """异步运行子进程"""
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, capture_output=True, env=env, cwd=cwd, timeout=timeout)
    )


# 全局单例
_claude_analyzer: Optional[ClaudeAnalyzer] = None


def get_claude_analyzer() -> ClaudeAnalyzer:
    global _claude_analyzer
    if _claude_analyzer is None:
        _claude_analyzer = ClaudeAnalyzer()
    return _claude_analyzer