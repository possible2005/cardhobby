# -*- coding: utf-8 -*-
"""
应用配置模块

统一管理文件路径、端口等配置。
所有数据文件（JSON / CSV）均写入 data/ 目录。
"""

import os

# 项目根目录：app/config.py -> app/ -> 项目根
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据文件目录
DATA_DIR = os.path.join(BASE_DIR, "data")

# 监控配置文件路径
MONITOR_CONFIG_FILE = os.path.join(DATA_DIR, "monitor_config.json")

# 监控历史记录文件路径
MONITOR_HISTORY_FILE = os.path.join(DATA_DIR, "monitor_history.json")

# 凑套系列数据文件路径
COLLECTION_FILE = os.path.join(DATA_DIR, "collections.json")

# 卡片图片缓存文件路径
CARD_IMAGES_CACHE_FILE = os.path.join(DATA_DIR, "card_images_cache.json")

# 用户偏好文件路径
PREFERENCES_FILE = os.path.join(DATA_DIR, "preferences.json")

# 默认监控配置
DEFAULT_MONITOR_CONFIG = {
    "keywords": [],
    "schedule_time": "09:00",
    "enabled": False,
    "last_run": None,
    "last_run_status": None,
}

# Flask 运行配置
PORT = 5001
DEBUG = True
HOST = "0.0.0.0"


def ensure_data_dir():
    """确保 data/ 目录存在，不存在则自动创建。"""
    os.makedirs(DATA_DIR, exist_ok=True)


def get_csv_filename(keyword):
    """
    根据关键字生成 CSV 文件路径（位于 data/ 目录）。

    Args:
        keyword (str): 搜索关键字

    Returns:
        str: CSV 文件绝对路径
    """
    safe_keyword = keyword.replace(" ", "_")
    return os.path.join(DATA_DIR, f"cardhobby_prices_{safe_keyword}.csv")
