# -*- coding: utf-8 -*-
"""
监控相关路由。

包含：
- /api/monitor/config GET/POST: 监控配置读取与保存
- /api/monitor/run POST: 手动触发一次监控抓取
- /api/monitor/data GET: 读取指定关键字的 CSV 数据
- /api/monitor/history GET/DELETE: 历史记录读取与批量删除
"""

import os

from flask import Blueprint, request, jsonify
import pandas as pd

from app.models.monitor import (
    load_monitor_config,
    save_monitor_config,
    load_monitor_history,
    delete_monitor_history_by_indices,
)
from app.services.scheduler import run_monitor_once
from app.config import get_csv_filename

monitor_bp = Blueprint('monitor', __name__)


@monitor_bp.route('/api/monitor/config', methods=['GET'])
def api_monitor_config_get():
    """
    获取当前监控配置。

    返回：
        JSON 格式的监控配置
    """
    config = load_monitor_config()
    return jsonify(config)


@monitor_bp.route('/api/monitor/config', methods=['POST'])
def api_monitor_config_save():
    """
    保存监控配置。

    请求体：
    {
        "keywords": ["关键字1", "关键字2"],
        "schedule_time": "09:00",
        "enabled": true
    }

    返回：
        {"success": true, "config": 保存后的配置}
    """
    data = request.json or {}
    # 读取现有配置，保留 last_run 等字段
    config = load_monitor_config()
    # 仅更新请求中提供的字段
    if 'keywords' in data:
        config['keywords'] = data['keywords']
    if 'schedule_time' in data:
        config['schedule_time'] = data['schedule_time']
    if 'enabled' in data:
        config['enabled'] = data['enabled']
    save_monitor_config(config)
    return jsonify({"success": True, "config": config})


@monitor_bp.route('/api/monitor/run', methods=['POST'])
def api_monitor_run():
    """
    手动触发一次监控抓取，遍历所有关键字逐个调用 scrape_cardhobby。

    返回：
        {"success": true, "results": [每个关键字的运行结果摘要]}
    """
    try:
        results = run_monitor_once()
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@monitor_bp.route('/api/monitor/data', methods=['GET'])
def api_monitor_data():
    """
    读取指定关键字的 CSV 数据并返回 JSON。

    请求参数：
        keyword: 搜索关键字

    返回：
        JSON 格式的数据列表
    """
    keyword = request.args.get('keyword', '').strip()
    if not keyword:
        return jsonify({"error": "关键字不能为空"}), 400
    csv_filename = get_csv_filename(keyword)
    if not os.path.exists(csv_filename):
        return jsonify({"error": "找不到对应的 CSV 数据文件"}), 404
    try:
        df = pd.read_csv(csv_filename, encoding="utf-8-sig")
        df = df.fillna("")
        data = df.to_dict(orient="records")
        # 确保数值类型正确
        for row in data:
            if "Price_CNY" in row and row["Price_CNY"] != "":
                try:
                    row["Price_CNY"] = float(row["Price_CNY"])
                except Exception:
                    row["Price_CNY"] = 0.0
            if "Scrape_Time" in row and row["Scrape_Time"] != "":
                try:
                    row["Scrape_Time"] = int(float(row["Scrape_Time"]))
                except Exception:
                    pass
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@monitor_bp.route('/api/monitor/history', methods=['GET'])
def api_monitor_history():
    """
    获取监控运行历史记录。

    返回：
        JSON 格式的历史记录列表
    """
    history = load_monitor_history()
    return jsonify(history)


@monitor_bp.route('/api/monitor/history', methods=['DELETE'])
def api_monitor_history_delete():
    """
    批量删除监控历史记录，并删除对应关键字的 CSV 文件。

    请求体：
    {
        "indices": [0, 2, 4]
    }

    返回：
        {
            "success": true,
            "deleted_count": 3,
            "deleted_csv_files": ["cardhobby_prices_欧文.csv", ...]
        }
    """
    data = request.json or {}
    indices = data.get("indices", [])

    if not isinstance(indices, list) or len(indices) == 0:
        return jsonify({"error": "未选择要删除的记录"}), 400

    # 删除历史记录并返回被删除的关键字集合
    deleted_keywords = delete_monitor_history_by_indices(indices)
    deleted_count = sum(1 for _ in deleted_keywords)  # 仅用于响应字段；实际删除条数以下方计算为准
    # 重新计算实际删除条数（按索引数）
    deleted_count = len(set(indices))

    # 删除对应关键字的 CSV 文件
    deleted_csv_files = []
    for kw in deleted_keywords:
        if not kw:
            continue
        csv_filename = get_csv_filename(kw)
        try:
            if os.path.exists(csv_filename):
                os.remove(csv_filename)
                deleted_csv_files.append(csv_filename)
        except Exception as e:
            print(f"[删除CSV] 删除 {csv_filename} 失败: {e}")

    return jsonify({
        "success": True,
        "deleted_count": deleted_count,
        "deleted_csv_files": deleted_csv_files
    })
