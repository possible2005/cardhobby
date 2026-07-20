# -*- coding: utf-8 -*-
"""
系统管理路由。

包含：
- /api/system/cleanup/preview  GET : 预览可清理的数据
- /api/system/cleanup/execute POST: 执行清理
- /api/system/preferences     GET : 读取用户偏好
- /api/system/preferences     POST: 保存用户偏好
"""

import os
import glob
import time
from datetime import datetime

from flask import Blueprint, request, jsonify

from app.config import DATA_DIR, MONITOR_HISTORY_FILE, ensure_data_dir
from app.models.collection import load_collections, save_collections
from app.models.cache import load_image_cache, save_image_cache, load_preferences, save_preferences

system_bp = Blueprint('system', __name__)

# 30 天阈值（秒）
_30_DAYS_SEC = 30 * 24 * 3600


@system_bp.route('/api/system/cleanup/preview', methods=['GET'])
def api_cleanup_preview():
    """
    预览可清理的数据。

    返回：
        {
            "expired_csv": [{"filename": "...", "size_kb": 12.5, "last_modified": "..."}],
            "empty_collections": [{"id": 1, "series_name": "...", "card_count": 0}],
            "old_history": {"count": N, "oldest_date": "...", "newest_date": "..."},
            "image_cache_count": N
        }
    """
    # 1. 超过 30 天未修改的 CSV
    expired_csv = []
    csv_files = glob.glob(os.path.join(DATA_DIR, "cardhobby_prices_*.csv"))
    now_ts = time.time()
    for csv_path in csv_files:
        try:
            mtime = os.path.getmtime(csv_path)
        except OSError:
            continue
        if (now_ts - mtime) > _30_DAYS_SEC:
            try:
                size_kb = round(os.path.getsize(csv_path) / 1024.0, 2)
            except OSError:
                size_kb = 0.0
            expired_csv.append({
                "filename": os.path.basename(csv_path),
                "size_kb": size_kb,
                "last_modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })

    # 2. 没有卡片的凑套系列
    empty_collections = []
    for c in load_collections():
        cards = c.get("cards", [])
        if len(cards) == 0:
            empty_collections.append({
                "id": c.get("id"),
                "series_name": c.get("series_name", ""),
                "card_count": 0,
            })

    # 3. 超过 30 天的历史记录
    old_history = {"count": 0, "oldest_date": None, "newest_date": None}
    history = _load_history()
    if history:
        cutoff_ts = now_ts - _30_DAYS_SEC
        old_records = [r for r in history if isinstance(r.get("timestamp"), (int, float)) and r["timestamp"] < cutoff_ts]
        if old_records:
            old_ts = [r["timestamp"] for r in old_records]
            old_history = {
                "count": len(old_records),
                "oldest_date": datetime.fromtimestamp(min(old_ts)).strftime("%Y-%m-%d"),
                "newest_date": datetime.fromtimestamp(max(old_ts)).strftime("%Y-%m-%d"),
            }

    # 4. 图片缓存条目数
    image_cache_count = len(load_image_cache())

    return jsonify({
        "expired_csv": expired_csv,
        "empty_collections": empty_collections,
        "old_history": old_history,
        "image_cache_count": image_cache_count,
    })


@system_bp.route('/api/system/cleanup/execute', methods=['POST'])
def api_cleanup_execute():
    """
    执行清理。

    请求体：
        {
            "clean_csv": true,
            "clean_empty_collections": true,
            "clean_old_history": true,
            "clean_image_cache": false,
            "history_keep_days": 30
        }

    返回：
        {
            "success": true,
            "deleted_csv_count": N,
            "deleted_collections_count": N,
            "deleted_history_count": N,
            "cleared_cache_count": N
        }
    """
    data = request.json or {}
    clean_csv = bool(data.get("clean_csv", False))
    clean_empty_collections = bool(data.get("clean_empty_collections", False))
    clean_old_history = bool(data.get("clean_old_history", False))
    clean_image_cache = bool(data.get("clean_image_cache", False))
    history_keep_days = int(data.get("history_keep_days", 30))

    deleted_csv_count = 0
    deleted_collections_count = 0
    deleted_history_count = 0
    cleared_cache_count = 0

    now_ts = time.time()
    cutoff_ts = now_ts - history_keep_days * 24 * 3600

    # 1. 清理过期 CSV
    if clean_csv:
        csv_files = glob.glob(os.path.join(DATA_DIR, "cardhobby_prices_*.csv"))
        for csv_path in csv_files:
            try:
                mtime = os.path.getmtime(csv_path)
                if (now_ts - mtime) > _30_DAYS_SEC:
                    os.remove(csv_path)
                    deleted_csv_count += 1
            except OSError:
                continue

    # 2. 清理没有卡片的凑套系列
    if clean_empty_collections:
        collections = load_collections()
        new_collections = []
        for c in collections:
            if len(c.get("cards", [])) == 0:
                deleted_collections_count += 1
            else:
                new_collections.append(c)
        if deleted_collections_count > 0:
            save_collections(new_collections)

    # 3. 清理超过 history_keep_days 的历史记录
    if clean_old_history:
        history = _load_history()
        new_history = [r for r in history if not (isinstance(r.get("timestamp"), (int, float)) and r["timestamp"] < cutoff_ts)]
        deleted_history_count = len(history) - len(new_history)
        if deleted_history_count > 0:
            _save_history(new_history)

    # 4. 清理图片缓存
    if clean_image_cache:
        cache = load_image_cache()
        cleared_cache_count = len(cache)
        save_image_cache({})

    return jsonify({
        "success": True,
        "deleted_csv_count": deleted_csv_count,
        "deleted_collections_count": deleted_collections_count,
        "deleted_history_count": deleted_history_count,
        "cleared_cache_count": cleared_cache_count,
    })


@system_bp.route('/api/system/preferences', methods=['GET'])
def api_preferences_get():
    """读取用户偏好。"""
    prefs = load_preferences()
    return jsonify(prefs)


@system_bp.route('/api/system/preferences', methods=['POST'])
def api_preferences_save():
    """
    保存用户偏好。

    请求体：
        {"theme": "light" | "dark"}

    返回：
        {"success": true, "preferences": {...}}
    """
    data = request.json or {}
    prefs = load_preferences()
    if "theme" in data:
        prefs["theme"] = data["theme"]
    prefs["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_preferences(prefs)
    return jsonify({"success": True, "preferences": prefs})


# ----------------------------------------------------------------------------
# 历史记录 IO 辅助（不使用 monitor_lock，避免循环依赖；操作频次低）
# ----------------------------------------------------------------------------
def _load_history():
    """读取监控历史记录列表。"""
    import json
    if not os.path.exists(MONITOR_HISTORY_FILE):
        return []
    try:
        with open(MONITOR_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _save_history(history):
    """写入监控历史记录列表。"""
    import json
    ensure_data_dir()
    with open(MONITOR_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
