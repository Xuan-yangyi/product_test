"""批量测试结果 AI 汇总分析

用于产线一次测试几十/上百台设备后，快速定位"哪些设备有问题、问题是什么"。
AI 调用策略（ai_config.json 的 provider，默认 auto）：
  1. claude —— 本地 Claude CLI（优先）
  2. api    —— OpenAI 兼容 API（兜底）
"""
import json
import logging
import os
import sqlite3
from datetime import datetime

from ..config import Config
from .ai_service import get_ai_service
from .claude_analyzer import CLAUDE_BIN, get_claude_analyzer

logger = logging.getLogger(__name__)

KIND_LABEL = {"interface": "整机接口测试", "aging": "老化测试", "all": "全部测试"}

MAX_DEVICES = 300          # 参与分析的测试记录上限
MAX_FAIL_LINES = 60        # 逐条失败设备清单上限
MAX_ISSUES = 20            # 共性问题条目上限


class SummaryAnalyzer:
    """批量结果汇总分析"""

    # ------------------------------------------------------------------ #
    # 配置 / 引擎选择
    # ------------------------------------------------------------------ #
    def _provider_pref(self) -> str:
        try:
            with open(Config.CFG_DIR / "ai_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return (cfg.get("provider") or "auto").lower()
        except Exception:
            return "auto"

    def engine_status(self) -> dict:
        return {
            "provider_pref": self._provider_pref(),
            "claude_available": os.path.exists(CLAUDE_BIN),
        }

    # ------------------------------------------------------------------ #
    # 数据采集
    # ------------------------------------------------------------------ #
    def _build_where(self, kind: str, filters: dict):
        where, args = [], []
        if kind == "interface":
            where.append("test_type LIKE '%interface_test'")
        elif kind == "aging":
            where.append("test_type LIKE '%aging_test'")

        if filters.get("test_type"):
            where.append("test_type = ?")
            args.append(filters["test_type"])
        if filters.get("status"):
            where.append("status = ?")
            args.append(filters["status"])
        if filters.get("product_model"):
            where.append("product_model = ?")
            args.append(filters["product_model"])
        if filters.get("serial_number"):
            where.append("serial_number LIKE ?")
            args.append(f"%{filters['serial_number']}%")
        if filters.get("device_ip"):
            where.append("device_ip = ?")
            args.append(filters["device_ip"])
        if filters.get("start_date"):
            where.append("date(created_at) >= date(?)")
            args.append(filters["start_date"])
        if filters.get("end_date"):
            where.append("date(created_at) <= date(?)")
            args.append(filters["end_date"])

        sql = (" WHERE " + " AND ".join(where)) if where else ""
        return sql, args

    def _collect(self, kind: str, filters: dict) -> dict:
        db = Config.DATA_DIR / "results.db"
        if not db.exists():
            return {"total": 0, "stats": {}, "devices": [], "failures": [], "issues": []}

        con = sqlite3.connect(str(db), timeout=10)
        con.row_factory = sqlite3.Row
        try:
            where_sql, args = self._build_where(kind, filters)

            agg = con.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS passed, "
                "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed, "
                "SUM(CASE WHEN status IN ('running','interrupted','stopped') THEN 1 ELSE 0 END) AS abnormal, "
                "AVG(duration_seconds) AS avg_duration "
                "FROM web_test_records" + where_sql,
                args,
            ).fetchone()

            total = agg["total"] or 0
            passed = agg["passed"] or 0
            failed = agg["failed"] or 0
            abnormal = agg["abnormal"] or 0
            avg_duration = round(agg["avg_duration"] or 0, 1)
            pass_rate = round(passed / total * 100, 1) if total else 0.0

            rows = con.execute(
                "SELECT test_id, test_type, product_model, serial_number, board_sn, "
                "device_ip, status, passed, failed, skipped, duration_seconds, created_at, cluster_id "
                "FROM web_test_records" + where_sql +
                " ORDER BY created_at DESC LIMIT ?",
                args + [MAX_DEVICES],
            ).fetchall()

            devices = [dict(r) for r in rows]
            failed_ids = [d["test_id"] for d in devices if d["status"] == "failed"]

            failures = []
            issues = []
            if failed_ids:
                marks = ",".join("?" for _ in failed_ids)
                steps = con.execute(
                    "SELECT test_id, step_index, step_name, step_label, message "
                    f"FROM web_test_step_results WHERE result='fail' AND test_id IN ({marks}) "
                    "ORDER BY test_id, step_index",
                    failed_ids,
                ).fetchall()

                dev_by_id = {d["test_id"]: d for d in devices}
                issue_map = {}
                seen_dev = set()

                for s in steps:
                    d = dev_by_id.get(s["test_id"], {})
                    label = (s["step_label"] or s["step_name"] or "").strip()
                    msg = (s["message"] or "").strip()

                    # 共性问题聚合：按"步骤 + 原因前 80 字"归并
                    key = (label, msg[:80])
                    issue_map.setdefault(key, {"step": label, "message": msg[:200], "count": 0, "sns": []})
                    item = issue_map[key]
                    item["count"] += 1
                    if d.get("serial_number") and len(item["sns"]) < 3:
                        item["sns"].append(d["serial_number"])

                    if s["test_id"] not in seen_dev and len(failures) < MAX_FAIL_LINES:
                        seen_dev.add(s["test_id"])
                        failures.append({
                            "test_id": s["test_id"],
                            "sn": d.get("serial_number") or d.get("board_sn") or "-",
                            "model": d.get("product_model") or "-",
                            "ip": d.get("device_ip") or "-",
                            "type": d.get("test_type") or "-",
                            "step": label or "-",
                            "message": msg[:300] or "-",
                        })

                issues = sorted(issue_map.values(), key=lambda x: x["count"], reverse=True)[:MAX_ISSUES]

            return {
                "total": total,
                "stats": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "abnormal": abnormal,
                    "pass_rate": pass_rate,
                    "avg_duration": avg_duration,
                    "analyzed": len(devices),
                },
                "devices": devices,
                "failures": failures,
                "issues": issues,
            }
        finally:
            con.close()

    # ------------------------------------------------------------------ #
    # Prompt
    # ------------------------------------------------------------------ #
    def _build_prompt(self, kind: str, data: dict, filters: dict) -> str:
        stats = data.get("stats", {})
        kind_label = KIND_LABEL.get(kind, kind)

        lines = [
            f"你是产线测试分析专家。下面是一次【{kind_label}】的批量结果汇总，请分析后给出结论。",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 汇总统计",
            f"- 总数: {stats.get('total', 0)} 台",
            f"- 通过: {stats.get('passed', 0)} 台",
            f"- 失败: {stats.get('failed', 0)} 台",
            f"- 异常状态(运行中/中断/停止): {stats.get('abnormal', 0)} 台",
            f"- 通过率: {stats.get('pass_rate', 0)}%",
            f"- 平均耗时: {stats.get('avg_duration', 0)} 秒",
            "",
        ]

        if filters:
            lines.append(f"筛选条件: {json.dumps(filters, ensure_ascii=False)}")
            lines.append("")

        issues = data.get("issues") or []
        if issues:
            lines.append("## 共性问题（按出现次数排序）")
            for it in issues:
                sns = ("，示例SN: " + ", ".join(it["sns"])) if it.get("sns") else ""
                lines.append(f"- [{it['count']} 台] {it['step']}: {it['message']}{sns}")
            lines.append("")

        failures = data.get("failures") or []
        if failures:
            lines.append("## 失败设备清单（每台首个失败点）")
            for f in failures:
                lines.append(
                    f"- SN={f['sn']} | 型号={f['model']} | IP={f['ip']} | 步骤={f['step']} | 原因={f['message']}"
                )
            lines.append("")

        if not issues and not failures:
            lines.append("## 说明\n本次范围内没有失败记录。\n")

        lines.extend([
            "## 输出要求（中文，Markdown）",
            "1. **总体结论**：产线良率判断，是否可放行；1~3 句。",
            "2. **问题分类与根因**：把失败归为硬件/连接/脚本/环境等类别，给出依据。",
            "3. **重点排查清单**：列出最需要人工介入的 SN/IP（最多 10 台），说明原因。",
            "4. **处置建议**：返修、复测、换线/换夹具、脚本修正等具体动作。",
            "要求：结论明确、可执行；不要编造数据中没有的 SN 或原因。",
        ])

        prompt = "\n".join(lines)
        return prompt[:14000] if len(prompt) > 14000 else prompt

    # ------------------------------------------------------------------ #
    # 调用
    # ------------------------------------------------------------------ #
    async def _call_claude(self, prompt: str) -> str:
        analyzer = get_claude_analyzer()
        cwd = str(Config.LOG_DIR)
        os.makedirs(cwd, exist_ok=True)
        return await analyzer.run_prompt(prompt, cwd)

    async def _call_api(self, prompt: str) -> str:
        ai = get_ai_service()
        result = await ai.chat([{"role": "user", "content": prompt}])
        if result.get("error"):
            raise RuntimeError(result.get("reply") or "API 调用失败")
        return result.get("reply", "")

    async def analyze(self, kind: str, filters: dict = None) -> dict:
        filters = filters or {}
        data = self._collect(kind, filters)
        stats = data.get("stats", {})

        if not data.get("total"):
            return {
                "analysis": "当前筛选范围内没有测试记录，无法生成汇总分析。",
                "provider": "none",
                "stats": stats,
                "issues": [],
            }

        prompt = self._build_prompt(kind, data, filters)
        pref = self._provider_pref()
        claude_ok = os.path.exists(CLAUDE_BIN)

        # 1) Claude 优先
        if pref in ("auto", "claude") and claude_ok:
            try:
                text = await self._call_claude(prompt)
                if text and text.strip():
                    return {"analysis": text, "provider": "claude", "stats": stats,
                            "issues": data.get("issues", [])}
                logger.warning("Claude 返回空内容，回退到 API")
            except Exception as e:
                logger.warning(f"Claude 汇总分析失败，回退到 API: {e}")

        if pref == "claude":
            return {
                "analysis": "Claude CLI 不可用或执行失败，且配置为仅使用 Claude（provider=claude）。"
                            "请检查 claude 命令，或将 ai_config.json 的 provider 改为 auto/api。",
                "provider": "none",
                "stats": stats,
                "issues": data.get("issues", []),
            }

        # 2) API 兜底
        try:
            text = await self._call_api(prompt)
            return {"analysis": text, "provider": "api", "stats": stats,
                    "issues": data.get("issues", [])}
        except Exception as e:
            logger.error(f"API 汇总分析失败: {e}")
            return {
                "analysis": f"AI 分析不可用：本地 Claude CLI 不可用，且 API 调用失败（{e}）。"
                            "请检查 cfg/ai_config.json 或运行 ./setup_ai.sh 配置模型。",
                "provider": "none",
                "stats": stats,
                "issues": data.get("issues", []),
            }


_summary_analyzer = None


def get_summary_analyzer() -> SummaryAnalyzer:
    global _summary_analyzer
    if _summary_analyzer is None:
        _summary_analyzer = SummaryAnalyzer()
    return _summary_analyzer