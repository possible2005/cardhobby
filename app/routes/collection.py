# -*- coding: utf-8 -*-
"""
凑套系列管理路由。

包含：
- /api/collections GET: 获取所有凑套系列
- /api/collections POST: 创建/合并凑套系列
- /api/collections/<cid>/cards PUT: 批量更新卡片状态
- /api/collections/<cid> DELETE: 删除凑套系列
"""

import time
from datetime import datetime

from flask import Blueprint, request, jsonify

from app.models.collection import load_collections, save_collections
from app.services.parser import parse_collection_text
from app.services.image_fetcher import fetch_images_for_collection

collection_bp = Blueprint('collection', __name__)


@collection_bp.route('/api/collections', methods=['GET'])
def api_collections_list():
    """获取所有凑套系列。"""
    data = load_collections()
    return jsonify(data)


@collection_bp.route('/api/collections', methods=['POST'])
def api_collections_create():
    """
    创建新的凑套系列。

    请求体：
    {
        "text": "topps狂热\n - FAN-2 扬尼斯..."
    }

    返回：
        {"success": true, "collection": {...}}
    """
    text = (request.json or {}).get("text", "")
    if not text.strip():
        return jsonify({"error": "内容不能为空"}), 400

    parsed = parse_collection_text(text)
    if not parsed["series_name"]:
        return jsonify({"error": "无法解析系列名称，请检查格式"}), 400
    if not parsed["cards"]:
        return jsonify({"error": "未解析到任何卡片信息"}), 400

    collections = load_collections()

    # 检查是否已存在同名系列
    existing = None
    for c in collections:
        if c["series_name"] == parsed["series_name"]:
            existing = c
            break

    if existing:
        # 合并卡片（去重，按 code 判断）
        existing_codes = {card["code"] for card in existing["cards"] if card["code"]}
        for new_card in parsed["cards"]:
            if new_card["code"] not in existing_codes:
                existing["cards"].append(new_card)
        result = existing
    else:
        result = {
            "id": int(time.time() * 1000),
            "series_name": parsed["series_name"],
            "cards": parsed["cards"],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        collections.append(result)

    save_collections(collections)
    return jsonify({"success": True, "collection": result})


@collection_bp.route('/api/collections/<int:cid>/cards', methods=['PUT'])
def api_collections_update_cards(cid):
    """
    更新卡片状态（批量）。

    请求体（两种二选一，推荐使用 card_indices）：
    {
        "card_indices": [0, 2, 4],
        "collected": true
    }
    或
    {
        "card_codes": ["FAN-2", "FAN-13"],
        "collected": true
    }
    """
    data = request.json or {}
    collected = data.get("collected", True)
    card_indices = data.get("card_indices")
    card_codes = data.get("card_codes", [])

    # 优先使用索引模式，避免 code 为空或重复时匹配错乱
    if card_indices is None:
        if not card_codes:
            return jsonify({"error": "未选择卡片"}), 400
        use_indices = False
    else:
        if not isinstance(card_indices, list) or len(card_indices) == 0:
            return jsonify({"error": "未选择卡片"}), 400
        use_indices = True

    collections = load_collections()
    for c in collections:
        if c.get("id") == cid:
            cards = c.get("cards", [])
            if use_indices:
                # 索引模式：直接按下标更新，索引越界自动跳过
                for i in card_indices:
                    if isinstance(i, int) and 0 <= i < len(cards):
                        cards[i]["collected"] = collected
            else:
                # code 模式：向后兼容
                for card in cards:
                    if card.get("code") in card_codes:
                        card["collected"] = collected
            save_collections(collections)
            return jsonify({"success": True, "collection": c})

    return jsonify({"error": "系列不存在"}), 404


@collection_bp.route('/api/collections/<int:cid>', methods=['DELETE'])
def api_collections_delete(cid):
    """删除凑套系列。"""
    collections = load_collections()
    collections = [c for c in collections if c.get("id") != cid]
    save_collections(collections)
    return jsonify({"success": True})


@collection_bp.route('/api/collections/<int:cid>/card-images', methods=['GET'])
def api_collection_card_images(cid):
    """
    获取一个凑套系列中每张卡片的图片 URL。

    流程：
        1. 加载该系列的卡片列表
        2. 遍历 data/ 下所有 CSV，用 matcher 逻辑匹配 Card_Title，提取 Card_URL
        3. 从 Card_URL 对应的详情页抓取图片 URL（缓存于 data/card_images_cache.json）
        4. 返回 {images: {卡片编号: image_url}}

    返回：
        {"images": {"FAN-2": "https://...", "FAN-13": "https://..."}}
    """
    collections = load_collections()
    target = None
    for c in collections:
        if c.get("id") == cid:
            target = c
            break
    if target is None:
        return jsonify({"error": "系列不存在"}), 404

    cards = target.get("cards", [])
    try:
        images = fetch_images_for_collection(cid, cards)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"images": images})
