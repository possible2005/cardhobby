# -*- coding: utf-8 -*-
"""
凑套系列数据存储模块。

负责凑套系列数据的读写，使用线程锁保证并发安全。
"""

import os
import json
import threading

from app.config import COLLECTION_FILE

# 文件读写锁，保证线程安全
collection_lock = threading.Lock()


def load_collections():
    """
    加载凑套系列数据。

    Returns:
        list: 凑套系列列表
    """
    with collection_lock:
        if os.path.exists(COLLECTION_FILE):
            try:
                with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
    return []


def save_collections(data):
    """
    保存凑套系列数据。

    Args:
        data (list): 凑套系列数据列表
    """
    with collection_lock:
        with open(COLLECTION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
