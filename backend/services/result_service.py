"""结果服务

管理测试结果的 SQLite 数据库读写，支持历史数据查询和统计。
"""
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path
from ..models.db_models import TestRecord, StepResult, create_session_factory

logger = logging.getLogger(__name__)


class ResultService:
    """结果服务 — SQLite 持久化"""

    def __init__(self):
        self._session_factory = None
        self._init_db()

    def _init_db(self):
        try:
            self._session_factory = create_session_factory()
            logger.info("SQLite 数据库连接成功")
        except Exception as e:
            logger.warning(f"SQLite 数据库初始化失败: {e}")

    def save_test_result(self, task: dict):
        """保存/更新测试结果到 SQLite"""
        if not self._session_factory:
            return

        session = self._session_factory()
        try:
            test_id = task.get("test_id", "")
            record = session.query(TestRecord).filter_by(test_id=test_id).first()

            if not record:
                record = TestRecord(
                    test_id=test_id,
                    test_type=task.get("test_type", ""),
                    product_model=task.get("product_model", ""),
                    serial_number=task.get("serial_number", ""),
                    serial_port=task.get("serial_port", ""),
                    device_ip=task.get("device_ip", ""),
                    cluster_id=task.get("cluster_id", ""),
                    params=task.get("params", {}),
                    created_at=task.get("created_at", datetime.now()),
                )

            # 更新字段
            record.status = task.get("status", record.status)
            record.total_steps = task.get("total_steps", record.total_steps)
            record.current_step = task.get("current_step", record.current_step)
            record.serial_number = task.get("serial_number") or record.serial_number
            record.board_sn = task.get("board_sn") or record.board_sn
            record.device_ip = task.get("device_ip") or record.device_ip
            record.cluster_id = task.get("cluster_id") or record.cluster_id
            record.passed = task.get("passed", record.passed or 0)
            record.failed = task.get("failed", record.failed or 0)
            record.skipped = task.get("skipped", record.skipped or 0)
            if task.get("params"):
                record.params = task.get("params")
            if task.get("extra_info"):
                record.extra_info = task.get("extra_info")

            if task.get("status") in ("completed", "failed", "stopped"):
                record.finished_at = task.get("finished_at", datetime.now())

            # 计算耗时
            if record.created_at and record.finished_at:
                record.duration_seconds = (record.finished_at - record.created_at).total_seconds()

            session.add(record)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"保存测试结果失败: {e}")
        finally:
            session.close()

    def save_step_result(self, test_id: str, step_index: int, step_name: str,
                         result: str, message: str, duration_ms: int):
        """保存步骤结果到 SQLite"""
        if not self._session_factory:
            return

        session = self._session_factory()
        try:
            step = StepResult(
                test_id=test_id,
                step_index=step_index,
                step_name=step_name,
                step_label=message,
                result=result,
                duration_ms=duration_ms,
                message=message,
            )
            session.add(step)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"保存步骤结果失败: {e}")
        finally:
            session.close()

    def query_results(self, filters: dict) -> dict:
        """查询测试结果 — 支持多条件筛选和分页"""
        if not self._session_factory:
            return {"total": 0, "page": 1, "page_size": 20, "items": []}

        session = self._session_factory()
        try:
            query = session.query(TestRecord)

            if filters.get("test_id"):
                query = query.filter(TestRecord.test_id == filters["test_id"])
            if filters.get("serial_number"):
                query = query.filter(TestRecord.serial_number.like(f"%{filters['serial_number']}%"))
            if filters.get("test_type"):
                query = query.filter(TestRecord.test_type == filters["test_type"])
            if filters.get("status"):
                query = query.filter(TestRecord.status == filters["status"])
            if filters.get("product_model"):
                query = query.filter(TestRecord.product_model == filters["product_model"])
            if filters.get("device_ip"):
                query = query.filter(TestRecord.device_ip == filters["device_ip"])
            if filters.get("cluster_id"):
                query = query.filter(TestRecord.cluster_id == filters["cluster_id"])
            if filters.get("start_date"):
                query = query.filter(TestRecord.created_at >= filters["start_date"])
            if filters.get("end_date"):
                query = query.filter(TestRecord.created_at <= filters["end_date"])

            total = query.count()
            page = int(filters.get("page", 1))
            page_size = int(filters.get("page_size", 20))
            items = query.order_by(TestRecord.created_at.desc()) \
                .offset((page - 1) * page_size).limit(page_size).all()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [_record_to_dict(r) for r in items],
            }
        finally:
            session.close()

    def get_test_detail(self, test_id: str) -> Optional[dict]:
        """获取单个测试详情（含步骤）"""
        if not self._session_factory:
            return None

        session = self._session_factory()
        try:
            record = session.query(TestRecord).filter_by(test_id=test_id).first()
            if not record:
                return None
            result = _record_to_dict(record)

            # 获取步骤
            steps = session.query(StepResult).filter_by(test_id=test_id) \
                .order_by(StepResult.step_index).all()
            result["steps"] = [
                {
                    "step_index": s.step_index,
                    "step_name": s.step_name or "",
                    "step_label": s.step_label,
                    "result": s.result,
                    "duration_ms": s.duration_ms,
                    "message": s.message,
                }
                for s in steps
            ]
            return result
        finally:
            session.close()

    def get_statistics(self, filters: dict = None) -> dict:
        """获取统计信息"""
        if not self._session_factory:
            return {"total": 0, "completed": 0, "failed": 0, "running": 0}

        session = self._session_factory()
        try:
            query = session.query(TestRecord)
            if filters:
                if filters.get("start_date"):
                    query = query.filter(TestRecord.created_at >= filters["start_date"])
                if filters.get("end_date"):
                    query = query.filter(TestRecord.created_at <= filters["end_date"])

            total = query.count()
            completed = query.filter(TestRecord.status == "completed").count()
            failed = query.filter(TestRecord.status == "failed").count()
            running = query.filter(TestRecord.status == "running").count()
            stopped = query.filter(TestRecord.status == "stopped").count()

            return {
                "total": total,
                "completed": completed,
                "failed": failed,
                "running": running,
                "stopped": stopped,
                "pass_rate": round(completed / total * 100, 1) if total > 0 else 0,
            }
        finally:
            session.close()

    def export_csv(self, filters: dict = None) -> str:
        """导出测试结果为 CSV 字符串

        Args:
            filters: 同 query_results 的筛选条件

        Returns:
            CSV 格式字符串（含表头）
        """
        import csv
        import io

        # 获取全部数据（不分页）
        all_filters = dict(filters or {})
        all_filters["page"] = 1
        all_filters["page_size"] = 100000  # 大量数据
        result = self.query_results(all_filters)
        items = result.get("items", [])

        output = io.StringIO()
        writer = csv.writer(output)

        # 表头
        writer.writerow([
            "test_id", "test_type", "product_model", "serial_number",
            "board_sn", "device_ip", "status", "passed", "failed",
            "skipped", "total_steps", "duration_seconds",
            "created_at", "finished_at",
        ])

        for item in items:
            writer.writerow([
                item.get("test_id", ""),
                item.get("test_type", ""),
                item.get("product_model", ""),
                item.get("serial_number", ""),
                item.get("board_sn", ""),
                item.get("device_ip", ""),
                item.get("status", ""),
                item.get("passed", 0),
                item.get("failed", 0),
                item.get("skipped", 0),
                item.get("total_steps", 0),
                item.get("duration_seconds", 0),
                item.get("created_at", ""),
                item.get("finished_at", ""),
            ])

        return output.getvalue()

    def clean_stale_running_records(self, active_test_ids: set) -> int:
        """清理残留的 running 记录。

        后端重启后，SQLite 中可能有残留的 "running" 记录（测试已不存在于内存中）。
        将这些记录标记为 "interrupted"。
        Args:
            active_test_ids: 当前内存中存在的 test_id 集合
        Returns:
            清理的记录数
        """
        if not self._session_factory:
            return 0

        session = self._session_factory()
        try:
            from datetime import datetime
            stale = session.query(TestRecord).filter(
                TestRecord.status == "running"
            ).all()

            count = 0
            for record in stale:
                if record.test_id not in active_test_ids:
                    record.status = "interrupted"
                    record.finished_at = datetime.now()
                    count += 1

            if count > 0:
                session.commit()
                logger.info(f"清理残留记录: {count} 条 running -> interrupted")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"清理残留记录失败: {e}")
            return 0
        finally:
            session.close()


def _parse_datetime(value) -> Optional[datetime]:
    """解析日期字符串为 datetime 对象"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # 尝试常见格式: "2026-09-06 16:36:51.953727"
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    try:
        # ISO 格式: "2026-09-06T16:36:51"
        return datetime.fromisoformat(str(value)[:19])
    except ValueError:
        pass
    return None


def _record_to_dict(r: TestRecord) -> dict:
    """将 TestRecord ORM 对象转为字典"""
    return {
        "test_id": r.test_id,
        "test_type": r.test_type,
        "product_model": r.product_model,
        "serial_number": r.serial_number or "",
        "board_sn": r.board_sn or "",
        "serial_port": r.serial_port or "",
        "device_ip": r.device_ip or "",
        "cluster_id": r.cluster_id or "",
        "params": r.params or {},
        "extra_info": r.extra_info or {},
        "status": r.status,
        "total_steps": r.total_steps or 0,
        "current_step": r.current_step or 0,
        "passed": r.passed or 0,
        "failed": r.failed or 0,
        "skipped": r.skipped or 0,
        "duration_seconds": r.duration_seconds or 0.0,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "finished_at": r.finished_at.isoformat() if r.finished_at else "",
    }