"""批量测试结果 AI 汇总分析（v2）

支持三种范围：
  scope=selected  指定 test_ids（结果页勾选）
  scope=filtered  按筛选条件（状态/SN/日期）
  scope=batch     按测试批次 cluster_id

支持按产品线（SE13 / Athena2）过滤，并在报告中分组呈现。
AI 调用策略：本地 Claude CLI 优先，失败回退 API（provider=auto|claude|api）。
生成结果保存到 report_store（30 分钟），供独立报告页读取。
"""
import json
import logging
import os
import sqlite3
from datetime import datetime

from ..config import Config
from .ai_service import get_ai_service
from .claude_analyzer import CLAUDE_BIN, get_claude_analyzer
from . import report_store

logger = logging.getLogger(__name__)

KIND_LABEL = {"interface": "整机接口测试", "aging": "老化测试", "all": "全部测试"}

# 产品线 → product_model 取值
PRODUCT_LINE_MODELS = {
    "SE13": ["SE13"],
    "Athena2": ["SE9", "EVB"],
}

MAX_LIMIT = 500
MAX_FAIL_LINES = 60
MAX_ISSUES = 20


class SummaryAnalyzer:
    # ------------------------------------------------------------------ #
    def _provider_pref(self) -> str:
        try:
            with open(Config.CFG_DIR / "ai_config.json", "r", encoding="utf-8") as f:
                return (json.load(f).get("provider") or "auto").lower()
        except Exception:
            return "auto"

    def engine_status(self) -> dict:
        return {
            "provider_pref": self._provider_pref(),
            "claude_available": os.path.exists(CLAUDE_BIN),
            "product_lines": list(PRODUCT_LINE_MODELS.keys()),
        }

    # ------------------------------------------------------------------ #
    def _build_where(self, kind: str, params: dict):
        where, args = [], []
        if kind == "interface":
            where.append("test_type LIKE '%interface_test'")
        elif kind == "aging":
            where.append("test_type LIKE '%aging_test'")

        scope = (params.get("scope") or "filtered").lower()
        if scope == "selected":
            ids = [str(i) for i in (params.get("test_ids") or []) if i]
            if not ids:
                return None, []          # 调用方处理“未选择”
            where.append("test_id IN (" + ",".join("?" for _ in ids) + ")")
            args.extend(ids)
        elif scope == "batch":
            cid = params.get("cluster_id") or ""
            if cid:
                where.append("cluster_id = ?")
                args.append(cid)

        f = params.get("filters") or {}
        if f.get("test_type"):
            where.append("test_type = ?"); args.append(f["test_type"])
        if f.get("status"):
            where.append("status = ?"); args.append(f["status"])
        if f.get("serial_number"):
            where.append("serial_number LIKE ?"); args.append(f"%{f['serial_number']}%")
        if f.get("device_ip"):
            where.append("device_ip = ?"); args.append(f["device_ip"])
        if f.get("start_date"):
            where.append("date(created_at) >= date(?)"); args.append(f["start_date"])
        if f.get("end_date"):
            where.append("date(created_at) <= date(?)"); args.append(f["end_date"])

        lines = [p for p in (params.get("product_lines") or []) if p]
        models = []
        for pl in lines:
            models.extend(PRODUCT_LINE_MODELS.get(pl, [pl]))
        if models:
            where.append("product_model IN (" + ",".join("?" for _ in models) + ")")
            args.extend(models)

        sql = (" WHERE " + " AND ".join(where)) if where else ""
        return sql, args

    # ------------------------------------------------------------------ #
    def _collect(self, kind: str, params: dict) -> dict:
        empty = {"total": 0, "stats": {}, "groups": [], "failures": [], "issues": []}
        db = Config.DATA_DIR / "results.db"
        if not db.exists():
            return empty

        where_sql, args = self._build_where(kind, params)
        if where_sql is None:
            return empty

        limit = min(int(params.get("limit") or MAX_LIMIT), MAX_LIMIT)

        con = sqlite3.connect(str(db), timeout=10)
        con.row_factory = sqlite3.Row
        try:
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

            # 产品线分组统计
            groups = []
            for g in con.execute(
                "SELECT product_model AS model, COUNT(*) AS total, "
                "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS passed, "
                "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed "
                "FROM web_test_records" + where_sql + " GROUP BY product_model",
                args,
            ).fetchall():
                g_total = g["total"] or 0
                g_pass = g["passed"] or 0
                groups.append({
                    "model": g["model"] or "-",
                    "total": g_total,
                    "passed": g_pass,
                    "failed": g["failed"] or 0,
                    "pass_rate": round(g_pass / g_total * 100, 1) if g_total else 0.0,
                })

            rows = con.execute(
                "SELECT test_id, test_type, product_model, serial_number, board_sn, "
                "device_ip, status, passed, failed, duration_seconds, created_at, cluster_id "
                "FROM web_test_records" + where_sql +
                " ORDER BY created_at DESC LIMIT ?",
                args + [limit],
            ).fetchall()
            devices = [dict(r) for r in rows]

            failed_ids = [d["test_id"] for d in devices if d["status"] == "failed"]
            failures, issues = [], []
            if failed_ids:
                marks = ",".join("?" for _ in failed_ids)
                steps = con.execute(
                    "SELECT test_id, step_index, step_name, step_label, message "
                    f"FROM web_test_step_results WHERE result='fail' AND test_id IN ({marks}) "
                    "ORDER BY test_id, step_index",
                    failed_ids,
                ).fetchall()

                dev_by_id = {d["test_id"]: d for d in devices}
                issue_map, seen = {}, set()

                for s in steps:
                    d = dev_by_id.get(s["test_id"], {})
                    label = (s["step_label"] or s["step_name"] or "").strip()
                    msg = (s["message"] or "").strip()
                    key = (d.get("product_model", "-"), label, msg[:80])
                    item = issue_map.setdefault(key, {
                        "model": d.get("product_model") or "-",
                        "step": label, "message": msg[:200], "count": 0, "sns": [],
                    })
                    item["count"] += 1
                    if d.get("serial_number") and len(item["sns"]) < 3:
                        item["sns"].append(d["serial_number"])

                    if s["test_id"] not in seen and len(failures) < MAX_FAIL_LINES:
                        seen.add(s["test_id"])
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
                    "total": total, "passed": passed, "failed": failed,
                    "abnormal": abnormal, "pass_rate": pass_rate,
                    "avg_duration": avg_duration, "analyzed": len(devices),
                    "limit": limit,
                },
                "groups": groups,
                "failures": failures,
                "issues": issues,
            }
        finally:
            con.close()

    # ------------------------------------------------------------------ #
    def _build_prompt(self, kind: str, data: dict, params: dict) -> str:
        stats = data.get("stats", {})
        groups = data.get("groups", [])
        lines = [
            f"你是产线测试分析专家。下面是一次【{KIND_LABEL.get(kind, kind)}】的批量结果，请分析后给出结论。",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 总体统计",
            f"- 总数: {stats.get('total', 0)} 台（本次分析样本 {stats.get('analyzed', 0)} 台，上限 {stats.get('limit', 0)}）",
            f"- 通过: {stats.get('passed', 0)} 台；失败: {stats.get('failed', 0)} 台；异常状态: {stats.get('abnormal', 0)} 台",
            f"- 通过率: {stats.get('pass_rate', 0)}%；平均耗时: {stats.get('avg_duration', 0)} 秒",
            "",
        ]

        if groups:
            lines.append("## 产品线分组")
            for g in groups:
                lines.append(f"- {g['model']}: 共 {g['total']} 台，通过 {g['passed']}，失败 {g['failed']}，通过率 {g['pass_rate']}%")
            lines.append("")

        if params.get("scope") == "selected":
            lines.append("说明：本次为操作员手动勾选的设备集合。\n")
        elif params.get("scope") == "batch":
            lines.append(f"说明：本次为同一测试批次（cluster_id={params.get('cluster_id', '-')}）。\n")

        issues = data.get("issues") or []
        if issues:
            lines.append("## 共性问题（按产品线+步骤+原因聚合）")
            for it in issues:
                sns = ("，示例SN: " + ", ".join(it["sns"])) if it.get("sns") else ""
                lines.append(f"- [{it['model']}] {it['step']}: {it['message']}（{it['count']} 台{sns}）")
            lines.append("")

        failures = data.get("failures") or []
        if failures:
            lines.append("## 失败设备清单（每台首个失败点）")
            for f in failures:
                lines.append(
                    f"- [{f['model']}] SN={f['sn']} | IP={f['ip']} | 步骤={f['step']} | 原因={f['message']}"
                )
            lines.append("")

        if not issues and not failures:
            lines.append("## 说明\n本次范围内没有失败记录。\n")

        lines.extend([
            "## 输出要求（中文 Markdown）",
            "1. **总体结论**：良率判断，是否可放行（1~3 句）。",
            "2. **按产品线分节**：对每个出现的产品线（如 SE13、SE9/EVB）单独成节，分别给出问题与根因；不同产品线不要混在一起。",
            "3. **重点排查清单**：列出最需要人工介入的 SN/IP（最多 10 台），标注所属产品线与原因。",
            "4. **处置建议**：返修、复测、换线/换夹具、脚本修正等具体动作。",
            "要求：结论明确、可执行；不要编造数据中没有的 SN 或原因。",
        ])
        prompt = "\n".join(lines)
        return prompt[:15000]

    # ------------------------------------------------------------------ #
    async def _call_claude(self, prompt: str) -> str:
        cwd = str(Config.LOG_DIR)
        os.makedirs(cwd, exist_ok=True)
        return await get_claude_analyzer().run_prompt(prompt, cwd)

    async def _call_api(self, prompt: str) -> str:
        result = await get_ai_service().chat([{"role": "user", "content": prompt}])
        if result.get("error"):
            raise RuntimeError(result.get("reply") or "API 调用失败")
        return result.get("reply", "")

    # ------------------------------------------------------------------ #
    async def analyze(self, kind: str, params: dict = None) -> dict:
        params = params or {}
        data = self._collect(kind, params)
        stats = data.get("stats", {})

        if not data.get("total"):
            if params.get("scope") == "selected" and (params.get("test_ids") or []):
                msg = ("所选设备在当前「产品线 / 测试类型」筛选下没有匹配记录，"
                       "请检查产品线勾选或测试类型后重试。")
            elif params.get("scope") == "selected":
                msg = "未选择任何测试记录，请先在结果表勾选设备。"
            else:
                msg = "当前选择范围内没有测试记录，无法生成汇总分析。"
            return {"analysis": msg, "provider": "none", "stats": stats,
                    "groups": [], "issues": [], "report_id": ""}

        prompt = self._build_prompt(kind, data, params)
        pref = self._provider_pref()
        claude_ok = os.path.exists(CLAUDE_BIN)
        analysis, provider = "", "none"

        if pref in ("auto", "claude") and claude_ok:
            try:
                analysis = await self._call_claude(prompt)
                if analysis and analysis.strip():
                    provider = "claude"
                else:
                    logger.warning("Claude 返回空内容，回退 API")
            except Exception as e:
                logger.warning(f"Claude 汇总分析失败，回退 API: {e}")

        if provider == "none" and pref != "claude":
            try:
                analysis = await self._call_api(prompt)
                provider = "api"
            except Exception as e:
                logger.error(f"API 汇总分析失败: {e}")
                analysis = (f"AI 分析不可用：本地 Claude CLI 不可用，且 API 调用失败（{e}）。"
                            "请检查 cfg/ai_config.json 或运行 ./setup_ai.sh 配置模型。")
                provider = "none"

        if provider == "none" and pref == "claude" and not analysis:
            analysis = ("Claude CLI 不可用或执行失败，且 provider=claude。"
                        "请检查 claude 命令，或将 provider 改为 auto/api。")

        report_id = report_store.save({
            "kind": kind,
            "kind_label": KIND_LABEL.get(kind, kind),
            "title": f"{KIND_LABEL.get(kind, kind)} AI 汇总分析报告",
            "content": analysis,
            "provider": provider,
            "stats": stats,
            "groups": data.get("groups", []),
            "params": {k: v for k, v in params.items() if k != "test_ids"} |
                      ({"selected_count": len(params.get("test_ids") or [])} if params.get("test_ids") else {}),
        })

        return {"analysis": analysis, "provider": provider, "stats": stats,
                "groups": data.get("groups", []), "issues": data.get("issues", []),
                "report_id": report_id}


_summary_analyzer = None


def get_summary_analyzer() -> SummaryAnalyzer:
    global _summary_analyzer
    if _summary_analyzer is None:
        _summary_analyzer = SummaryAnalyzer()
    return _summary_analyzer