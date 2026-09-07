"""结果服务

管理测试结果的 SQLite 数据库读写，支持历史数据查询和统计。
"""
import json
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
            # 自动迁移历史 JSON 数据
            self._migrate_json_to_db()
        except Exception as e:
            logger.warning(f"SQLite 数据库初始化失败: {e}")

    def _migrate_json_to_db(self):
        """将 data/tests/*.json 的历史数据导入 SQLite（仅导入一次）"""
        from ..config import Config
        tests_dir = Config.DATA_DIR / "tests"
        if not tests_dir.exists():
            return

        sessions = self._session_factory
        if not sessions:
            return

        session = sessions()
        try:
            imported_count = 0
            for f in tests_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        task = json.load(fp)

                    test_id = task.get("test_id", "")
                    if not test_id:
                        continue

                    # 检查是否已导入
                    existing = session.query(TestRecord).filter_by(test_id=test_id).first()
                    if existing:
                        continue

                    # 解析日期字段（JSON 中存储为字符串）
                    created_at = _parse_datetime(task.get("created_at"))
                    finished_at = _parse_datetime(task.get("finished_at"))

                    record = TestRecord(
                        test_id=test_id,
                        test_type=task.get("test_type", ""),
                        product_model=task.get("product_model", ""),
                        serial_number=task.get("serial_number", task.get("serial_number", "")),
                        serial_port=task.get("serial_port", ""),
                        device_ip=task.get("device_ip", ""),
                        cluster_id=task.get("cluster_id", ""),
                        status=task.get("status", "completed"),
                        total_steps=task.get("total_steps", 0),
                        current_step=task.get("current_step", 0),
                        params=task.get("params", {}),
                        created_at=created_at or datetime.now(),
                        finished_at=finished_at,
                    )
                    session.add(record)
                    imported_count += 1
                except Exception:
                    session.rollback()

            if imported_count > 0:
                session.commit()
                logger.info(f"已从 JSON 文件迁移 {imported_count} 条历史测试记录到 SQLite")
        except Exception as e:
            session.rollback()
            logger.warning(f"JSON 数据迁移失败: {e}")
        finally:
            session.close()

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
            record.device_ip = task.get("device_ip") or record.device_ip
            record.cluster_id = task.get("cluster_id") or record.cluster_id
            if task.get("params"):
                record.params = task.get("params")

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

    def save_step_result(self, test_id: str, step_index: int, result: str,
                         message: str, duration_ms: int):
        """保存步骤结果到 SQLite"""
        if not self._session_factory:
            return

        session = self._session_factory()
        try:
            step = StepResult(
                test_id=test_id,
                step_index=step_index,
                step_name="",
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
        "status": r.status,
        "total_steps": r.total_steps or 0,
        "current_step": r.current_step or 0,
        "duration_seconds": r.duration_seconds or 0.0,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "finished_at": r.finished_at.isoformat() if r.finished_at else "",
    }