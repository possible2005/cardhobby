# -*- coding: utf-8 -*-
"""
缓存模块。

负责卡片图片缓存与用户偏好数据的读写，使用线程锁保证并发安全。
"""

import os
import json
import threading

from app.config import (
    CARD_IMAGES_CACHE_FILE,
    PREFERENCES_FILE,
    ensure_data_dir,
)

# 图片缓存文件读写锁
_image_cache_lock = threading.Lock()
# 用户偏好文件读写锁
_preferences_lock = threading.Lock()


# ----------------------------------------------------------------------------
# 卡片图片缓存
# ----------------------------------------------------------------------------

def load_image_cache():
    """
    加载卡片图片缓存。

    Returns:
        dict: {Card_URL: image_url} 映射
    """
    with _image_cache_lock:
        if not os.path.exists(CARD_IMAGES_CACHE_FILE):
            return {}
        try:
            with open(CARD_IMAGES_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, IOError):
            return {}


def save_image_cache(data):
    """
    保存卡片图片缓存到文件。

    Args:
        data (dict): {Card_URL: image_url} 映射
    """
    ensure_data_dir()
    with _image_cache_lock:
        with open(CARD_IMAGES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def get_cached_image(url):
    """
    读取某个 Card_URL 对应的缓存图片 URL。

    Args:
        url (str): 卡片详情页 URL

    Returns:
        str or None: 图片 URL，无缓存返回 None
    """
    cache = load_image_cache()
    return cache.get(url)


def set_cached_image(url, image_url):
    """
    写入某个 Card_URL 对应的缓存图片 URL。

    Args:
        url (str): 卡片详情页 URL
        image_url (str): 图片 URL
    """
    cache = load_image_cache()
    cache[url] = image_url
    save_image_cache(cache)


# ----------------------------------------------------------------------------
# 用户偏好
# ----------------------------------------------------------------------------

def load_preferences():
    """
    加载用户偏好数据。

    Returns:
        dict: 偏好字典（如 {"theme": "light", "updated_at": "..."} ）
    """
    with _preferences_lock:
        if not os.path.exists(PREFERENCES_FILE):
            return {}
        try:
            with open(PREFERENCES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, IOError):
            return {}


def save_preferences(data):
    """
    保存用户偏好数据到文件。

    Args:
        data (dict): 偏好字典
    """
    ensure_data_dir()
    with _preferences_lock:
        with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
