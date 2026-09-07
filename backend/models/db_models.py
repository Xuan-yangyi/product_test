"""SQLAlchemy 数据库模型 — SQLite 存储"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from pathlib import Path

Base = declarative_base()


class TestRecord(Base):
    """测试记录主表"""
    __tablename__ = "web_test_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(String(64), unique=True, nullable=False, index=True)
    test_type = Column(String(64), nullable=False)
    product_model = Column(String(64), nullable=False, default="")
    serial_number = Column(String(64), default="")
    board_sn = Column(String(64), default="")
    serial_port = Column(String(64), default="")
    device_ip = Column(String(32), default="")
    cluster_id = Column(String(64), default="", index=True)
    status = Column(String(16), nullable=False, default="pending")
    total_steps = Column(Integer, default=0)
    current_step = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0.0)
    params = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)
    finished_at = Column(DateTime, nullable=True)
    extra_info = Column(JSON, default=dict)


class StepResult(Base):
    """测试步骤结果表"""
    __tablename__ = "web_test_step_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(String(64), nullable=False, index=True)
    step_index = Column(Integer, nullable=False)
    step_name = Column(String(128), default="")
    step_label = Column(String(256), default="")
    result = Column(String(16), nullable=False, default="pending")
    duration_ms = Column(Integer, default=0)
    message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)


def create_db_engine():
    """创建 SQLite 数据库引擎"""
    # 从 config 获取 DATA_DIR，或使用默认路径
    try:
        from ..config import Config
        data_dir = Config.DATA_DIR
    except Exception:
        base_dir = Path(__file__).resolve().parent.parent.parent
        data_dir = base_dir / "data"

    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "results.db"
    db_url = f"sqlite:///{db_path}"
    return create_engine(db_url, echo=False, connect_args={"check_same_thread": False})


def create_session_factory():
    """创建数据库会话工厂"""
    engine = create_db_engine()
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)