# -*- coding: utf-8 -*-
"""
监控数据存储模块。

负责监控配置与历史记录的读写，使用线程锁保证并发安全。
"""

import os
import json
import threading

from app.config import (
    MONITOR_CONFIG_FILE,
    MONITOR_HISTORY_FILE,
    DEFAULT_MONITOR_CONFIG,
)

# 文件读写锁，保证线程安全
monitor_lock = threading.Lock()


def load_monitor_config():
    """
    加载监控配置文件，如果文件不存在则返回默认配置。

    Returns:
        dict: 监控配置字典
    """
    with monitor_lock:
        if not os.path.exists(MONITOR_CONFIG_FILE):
            # 文件不存在时写入默认配置
            with open(MONITOR_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_MONITOR_CONFIG, f, ensure_ascii=False, indent=2)
            return DEFAULT_MONITOR_CONFIG.copy()
        try:
            with open(MONITOR_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return DEFAULT_MONITOR_CONFIG.copy()


def save_monitor_config(config):
    """
    保存监控配置到文件。

    Args:
        config (dict): 监控配置字典
    """
    with monitor_lock:
        with open(MONITOR_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


def load_monitor_history():
    """
    加载监控历史记录。

    Returns:
        list: 历史记录列表
    """
    with monitor_lock:
        if not os.path.exists(MONITOR_HISTORY_FILE):
            return []
        try:
            with open(MONITOR_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []


def append_monitor_history(record):
    """
    追加一条监控历史记录。

    Args:
        record (dict): 单条历史记录
    """
    with monitor_lock:
        history = []
        if os.path.exists(MONITOR_HISTORY_FILE):
            try:
                with open(MONITOR_HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError):
                history = []
        history.append(record)
        with open(MONITOR_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)


def delete_monitor_history_by_indices(indices):
    """
    批量删除监控历史记录（按索引，倒序删除以避免索引错位）。

    Args:
        indices (list): 要删除的记录索引列表

    Returns:
        set: 被删除记录对应的 keyword 集合
    """
    with monitor_lock:
        history = []
        if os.path.exists(MONITOR_HISTORY_FILE):
            try:
                with open(MONITOR_HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError):
                history = []

        # 索引去重 & 倒序排序（从后往前删，避免索引错位）
        unique_indices = sorted(set(indices), reverse=True)
        deleted_keywords = set()

        for idx in unique_indices:
            if isinstance(idx, int) and 0 <= idx < len(history):
                rec = history.pop(idx)
                deleted_keywords.add(rec.get("keyword", ""))

        # 写回历史文件
        with open(MONITOR_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    return deleted_keywords
