"""SN 抓拍表 — 独立于同事的 db_models.TestRecord，复用同一 Base/引擎/DB。"""
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from .db_models import Base  # 复用共享 Base，靠现有 create_all 自动建表


class SnCapture(Base):
    """SE9 识别到的 SN 及其绑定设备图（本期仅展示，不与老化数据强关联）"""
    __tablename__ = "sn_captures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sn = Column(String(64), nullable=False, index=True)
    image_path = Column(String(256), nullable=False)  # 相对 DATA_DIR
    score = Column(Float, default=0.0)
    captured_at = Column(DateTime, nullable=True)      # SE9 抓拍时间
    source = Column(String(32), default="SE9")
    uploaded_at = Column(DateTime, default=datetime.now)  # 入库时间
