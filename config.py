"""
config.py —— 小牛b商管系统（Web版）配置文件
"""
import os

# ===================== 基础配置 =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Flask 密钥（生产环境请通过环境变量 SECRET_KEY 设置）
SECRET_KEY = os.environ.get("SECRET_KEY", "xiaoniu-shangguan-2026-secret-key-change-me")

# ===================== 数据库配置 =====================
DB_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MYSQL_PORT", 3306)),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "adminhang"),
    "database": os.environ.get("MYSQL_DATABASE", "xiaoniu_shangguan"),
    "charset": "utf8mb4",
    "autocommit": True,
}

# 存储后端（Web版固定用 MySQL）
STORAGE_BACKEND = "mysql"

# ===================== 常量 =====================
PROJECT_OPTIONS = ["卢沟桥文化公园", "园博园", "园博大酒店", "长辛店", "凉水河"]
BUSINESS_TYPE = ["轻餐", "重餐", "茶饮", "零售", "生活服务", "亲子娱乐/教培", "创意办公", "文化体验", "住宿"]
SHOP_STATUS = ["空置", "已出租", "维修", "退场交接"]

# 支付周期 → 月数
CYCLE_MAP = {"月度": 1, "季度": 3, "半年": 6, "年度": 12}

# 用户角色
ROLES = ["集团", "子公司", "商户"]
