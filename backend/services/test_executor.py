"""测试执行引擎

负责按序执行 TestStep 序列，管理阻塞操作在线程池中运行，
支持暂停/停止/交互，并通过回调通知上层状态变化。
"""
import asyncio
import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Callable, Any
from ..models.test_case import TestStep
from ..models.schemas import StepResult as StepResultEnum

logger = logging.getLogger(__name__)


class TestExecutor:
    """测试执行引擎

    按序执行 TestStep 序列。
    阻塞操作（串口、SSH、SCP）在线程池中运行，避免阻塞事件循环。
    通过回调通知上层状态变化（用于 WebSocket 推送）。
    """

    def __init__(self, max_workers: int = 10):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running: Dict[str, asyncio.Task] = {}
        self._status: Dict[str, dict] = {}
        self._callbacks: Dict[str, dict] = {}
        self._stop_flags: Dict[str, bool] = {}
        self._pause_events: Dict[str, asyncio.Event] = {}
        self._interaction_futures: Dict[str, asyncio.Future] = {}

    def register_callbacks(self, test_id: str, callbacks: dict):
        """注册回调

        callbacks: {
            "on_step_start": async fn(test_id, step_index, step_name),
            "on_step_complete": async fn(test_id, step_index, result, message, duration),
            "on_status_change": async fn(test_id, old_status, new_status),
            "on_log": async fn(test_id, level, source, message),
            "on_interaction_required": async fn(test_id, step_name, message, dialog_type, timeout) -> dict,
        }
        """
        self._callbacks[test_id] = callbacks

    async def run(self, test_id: str, steps: list, context: dict):
        """执行测试

        Args:
            test_id: 测试任务 ID
            steps: TestStep 列表
            context: 执行上下文（串口、SSH 客户端等）
        """
        self._stop_flags[test_id] = False
        self._pause_events[test_id] = asyncio.Event()
        self._pause_events[test_id].set()  # 初始不暂停

        self._status[test_id] = {
            "status": "running",
            "current_step": 0,
            "total_steps": len(steps),
            "results": [],
            "start_time": time.time(),
        }

        await self._notify("on_status_change", test_id, "pending", "running")

        try:
            for i, step in enumerate(steps):
                # 检查停止标志
                if self._stop_flags.get(test_id):
                    self._status[test_id]["status"] = "stopped"
                    await self._notify("on_status_change", test_id, "running", "stopped")
                    return

                # 等待暂停解除
                await self._pause_events[test_id].wait()

                self._status[test_id]["current_step"] = i + 1
                await self._notify("on_step_start", test_id, i, step.name)
                await self._notify("on_log", test_id, "INFO", step.name,
                                   f"[{i+1}/{len(steps)}] 开始执行: {step.label}")

                step_start = time.time()
                try:
                    # 在线程池中执行阻塞步骤
                    result = await self._execute_step(step, context, test_id)
                    duration = int((time.time() - step_start) * 1000)
                except Exception as e:
                    result = False
                    duration = int((time.time() - step_start) * 1000)
                    error_msg = f"{type(e).__name__}: {e}"
                    logger.error(f"步骤 [{step.name}] 执行异常: {error_msg}")
                    await self._notify("on_log", test_id, "ERROR", step.name, error_msg)

                step_result = StepResultEnum.pass_ if result else StepResultEnum.fail
                message = f"步骤 {step.label} {'通过' if result else '失败'}"

                self._status[test_id]["results"].append({
                    "step_index": i,
                    "step_name": step.name,
                    "step_label": step.label,
                    "result": step_result.value,
                    "duration_ms": duration,
                    "message": message,
                })

                await self._notify("on_step_complete", test_id, i, step_result.value, message, duration)
                log_level = "INFO" if result else "ERROR"
                await self._notify("on_log", test_id, log_level, step.name,
                                   f"[{i+1}/{len(steps)}] {message} (耗时 {duration}ms)")

                if step.required and not result:
                    self._status[test_id]["status"] = "failed"
                    await self._notify("on_status_change", test_id, "running", "failed")
                    return

            # 检查是否有失败步骤，决定最终状态
            results = self._status[test_id].get("results", [])
            has_failure = any(r and r.get("result") == "fail" for r in results if isinstance(r, dict))
            self._status[test_id]["status"] = "failed" if has_failure else "completed"
            await self._notify("on_status_change", test_id, "running",
                               "failed" if has_failure else "completed")

        except Exception as e:
            logger.error(f"测试执行异常 [{test_id}]: {e}")
            self._status[test_id]["status"] = "failed"
            await self._notify("on_status_change", test_id, "running", "failed")

    async def _execute_step(self, step: TestStep, context: dict, test_id: str) -> bool:
        """在线程池中执行单个步骤"""
        loop = asyncio.get_event_loop()

        # 检查是否需要交互
        if hasattr(step, 'interaction') and step.interaction:
            interaction_result = await self._request_interaction(
                test_id, step.name, step.interaction["message"],
                step.interaction.get("dialog_type", "confirm"),
                step.interaction.get("timeout", 300),
            )
            if interaction_result["action"] == "cancel":
                return False
            if interaction_result["action"] == "skip":
                return True  # 跳过但标记为通过
            context["interaction_value"] = interaction_result.get("value")

        return await loop.run_in_executor(
            self._executor,
            step.execute,
            context,
        )

    async def _request_interaction(self, test_id: str, step_name: str,
                                   message: str, dialog_type: str, timeout: int) -> dict:
        """请求人工交互"""
        future = asyncio.get_event_loop().create_future()
        self._interaction_futures[test_id] = future

        await self._notify(
            "on_interaction_required",
            test_id, step_name, message, dialog_type, timeout,
        )

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return {"action": "cancel", "value": None}

    def resolve_interaction(self, test_id: str, response: dict):
        """解析交互响应"""
        if test_id in self._interaction_futures:
            future = self._interaction_futures[test_id]
            if not future.done():
                future.set_result(response)

    def stop(self, test_id: str):
        """停止测试"""
        self._stop_flags[test_id] = True

    def pause(self, test_id: str):
        """暂停测试"""
        self._pause_events[test_id].clear()

    def resume(self, test_id: str):
        """恢复测试"""
        self._pause_events[test_id].set()

    def get_status(self, test_id: str) -> Optional[dict]:
        """获取测试状态"""
        return self._status.get(test_id)

    def get_all_status(self) -> Dict[str, dict]:
        """获取所有测试状态"""
        return dict(self._status)

    async def _notify(self, callback_name: str, *args, **kwargs):
        """通知回调"""
        callbacks = self._callbacks.get(args[0] if args else "")
        if callbacks and callback_name in callbacks:
            try:
                await callbacks[callback_name](*args, **kwargs)
            except Exception as e:
                logger.error(f"回调 {callback_name} 异常: {e}\n{traceback.format_exc()}")
                test_id = args[0] if args else None
                if test_id and test_id in self._status:
                    self._status[test_id]["status"] = "failed"

    def shutdown(self):
        """关闭执行器"""
        self._executor.shutdown(wait=True)
