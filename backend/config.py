"""全局配置"""
import os
from pathlib import Path

class Config:
    # ATHENA2_ROOT: web_product_test 项目根目录（包含 cfg/, data/ 等）
    _DEFAULT_ATHENA2_ROOT = Path(__file__).resolve().parent.parent  # web_product_test/
    ATHENA2_ROOT = Path(os.environ.get("ATHENA2_ROOT", str(_DEFAULT_ATHENA2_ROOT)))
    CFG_DIR = ATHENA2_ROOT / "cfg"
    DATA_DIR = ATHENA2_ROOT / "data"
    LOG_DIR = ATHENA2_ROOT / "log"

    # 数据库（默认从 mariadb.cfg 读取）
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "sophgo-factory")

    # 服务器
    HOST = "0.0.0.0"
    PORT = 8080
