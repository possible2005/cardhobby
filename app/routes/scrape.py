# -*- coding: utf-8 -*-
"""
抓取相关路由。

包含：
- /api/search: 关键字搜索
- /api/mark_bid: 标记出价
- /api/scrape/match: 抓取数据与凑套卡片匹配
"""

import os

from flask import Blueprint, request, jsonify
import pandas as pd

from app.services.scraper import scrape_cardhobby
from app.services.matcher import match_scraped_to_collections
from app.config import get_csv_filename
from app.models.collection import load_collections

scrape_bp = Blueprint('scrape', __name__)


@scrape_bp.route('/api/search', methods=['POST'])
def api_search():
    """
    搜索 API，接收关键字并返回抓取结果。

    请求体：
    {"keyword": "搜索关键字"}

    返回：
    JSON 格式的抓取结果列表
    """
    # 从请求体中获取关键字
    keyword = request.json.get('keyword')
    # 如果关键字为空，返回错误
    if not keyword:
        return jsonify({"error": "关键字不能为空"}), 400
    # 调用抓取函数（返回 {"new_count": N, "total_count": M, "items": [...]}）
    result_data = scrape_cardhobby(keyword)
    # 返回完整结构给前端：{items, new_count, total_count}
    return jsonify({
        "items": result_data.get("items", []),
        "new_count": result_data.get("new_count", 0),
        "total_count": result_data.get("total_count", len(result_data.get("items", []))),
    })


@scrape_bp.route('/api/mark_bid', methods=['POST'])
def mark_bid():
    """
    标记出价 API，将指定卡片标记为已出价。

    请求体：
    {
        "keyword": "搜索关键字",
        "items": [
            {
                "Card_Title": "卡片标题",
                "Seller_Name": "卖家名称",
                "Price_CNY": 价格,
                "End_Time": "结束时间"
            }
        ]
    }

    返回：
    {"success": true} 或 {"error": "错误信息"}
    """
    # 从请求体中获取数据
    data = request.json
    keyword = data.get('keyword')
    items_to_mark = data.get('items')
    # 检查参数是否完整
    if not keyword or not items_to_mark:
        return jsonify({"error": "缺少必要参数"}), 400

    # 生成 CSV 文件路径
    csv_filename = get_csv_filename(keyword)
    # 检查文件是否存在
    if not os.path.exists(csv_filename):
        return jsonify({"error": "找不到对应的 CSV 数据文件"}), 404

    try:
        # 读取 CSV 文件
        df = pd.read_csv(csv_filename, encoding="utf-8-sig")
        # 如果文件中没有 'Is_Bid' 列，添加该列
        if 'Is_Bid' not in df.columns:
            df['Is_Bid'] = '否'

        # 遍历要标记的项目
        for item in items_to_mark:
            # 创建匹配条件
            mask = (df['Card_Title'] == item['Card_Title']) & \
                   (df['Seller_Name'] == item['Seller_Name']) & \
                   (df['Price_CNY'] == item['Price_CNY'])

            # 如果包含结束时间，添加到匹配条件
            if 'End_Time' in df.columns and 'End_Time' in item:
                mask = mask & (df['End_Time'] == item['End_Time'])

            # 将匹配到的记录标记为已出价
            df.loc[mask, 'Is_Bid'] = '是'

        # 保存修改后的文件
        df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
        # 返回成功响应
        return jsonify({"success": True})
    except Exception as e:
        # 如果出错，返回错误信息
        return jsonify({"error": str(e)}), 500


@scrape_bp.route('/api/scrape/match', methods=['POST'])
def api_scrape_match():
    """
    对给定的抓取数据列表进行凑套卡片匹配。

    请求体：
    {
        "items": [ { "Card_Title": "...", "Seller_Name": "...", ... }, ... ]
    }

    返回：
    {
        "items": [
            {
                "Card_Title": "...",
                "Seller_Name": "...",
                "Price_CNY": 100.0,
                "Matched_Collections": [
                    { "cid": 1, "series_name": "topps狂热", "code": "FAN-2", "collected": false, "match_type": "编号" }
                ],
                "Has_Uncollected_Match": true
            }
        ],
        "uncollected_summary": [
            { "cid": 1, "series_name": "topps狂热", "code": "FAN-2", "player_cn": "...", "match_count": 3, "min_price": 80.0 }
        ]
    }
    """
    data = request.json or {}
    items = data.get("items", [])
    if not items:
        return jsonify({"items": [], "uncollected_summary": []})

    # 收集所有未搜集的卡片用于匹配
    collections = load_collections()
    all_cards = []
    for c in collections:
        for card in c.get("cards", []):
            all_cards.append({
                "cid": c.get("id"),
                "series_name": c.get("series_name", ""),
                "code": card.get("code", ""),
                "player_cn": card.get("player_cn", ""),
                "player_en": card.get("player_en", ""),
                "team": card.get("team", ""),
                "collected": card.get("collected", False)
            })

    # 对每条抓取记录进行匹配
    result_items = []
    uncollected_map = {}  # key: cid|code, value: { ...info, match_count, prices: [] }

    for item in items:
        title = item.get("Card_Title", "")
        matches = match_scraped_to_collections(title, all_cards)
        has_uncollected = any(not m["collected"] for m in matches)
        result_items.append({
            **item,
            "Matched_Collections": matches,
            "Has_Uncollected_Match": has_uncollected
        })
        # 累计未搜集匹配的统计信息
        price = item.get("Price_CNY", 0)
        try:
            price = float(price)
        except Exception:
            price = 0.0
        for m in matches:
            if not m["collected"]:
                key = f"{m['cid']}|{m['code']}"
                if key not in uncollected_map:
                    uncollected_map[key] = {
                        "cid": m["cid"],
                        "series_name": m["series_name"],
                        "code": m["code"],
                        "player_cn": m["player_cn"],
                        "match_count": 0,
                        "prices": []
                    }
                uncollected_map[key]["match_count"] += 1
                uncollected_map[key]["prices"].append(price)

    # 计算每个未搜集卡片匹配到的最低价
    uncollected_summary = []
    for info in uncollected_map.values():
        prices = [p for p in info["prices"] if p > 0]
        info["min_price"] = min(prices) if prices else 0.0
        info["avg_price"] = round(sum(prices) / len(prices), 2) if prices else 0.0
        del info["prices"]
        uncollected_summary.append(info)

    return jsonify({
        "items": result_items,
        "uncollected_summary": uncollected_summary
    })
