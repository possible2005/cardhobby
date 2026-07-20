# -*- coding: utf-8 -*-
"""
抓取数据 ↔ 凑套卡片 匹配服务。

负责将抓取的卡片标题与凑套系列中的卡片进行匹配。
"""

import re


def match_scraped_to_collections(card_title, all_cards):
    """
    将一条抓取记录的 Card_Title 与所有凑套卡片进行匹配。

    匹配策略（任一命中即认为匹配）：
    1. 卡片编号（如 FAN-2）出现在 Card_Title 中 —— 主匹配键
    2. 球员中文名出现在 Card_Title 中
    3. 球员英文名（大小写不敏感）出现在 Card_Title 中

    Args:
        card_title (str): 抓取的卡片标题
        all_cards (list): 所有序列的所有卡片列表，每项形如
            { cid, series_name, code, player_cn, player_en, team, collected }

    Returns:
        list: 匹配到的卡片列表（可能多条），每项附带 cid/series_name/code 等信息
    """
    if not card_title:
        return []
    title_lower = card_title.lower()
    matches = []
    for card in all_cards:
        hit = False
        match_type = ""
        # 1. 编号匹配（主键）：使用词边界避免 FAN-1 误匹配 FAN-13
        code = (card.get("code") or "").strip()
        if code:
            # 在标题中查找编号，要求编号前后是非字母数字字符（或字符串边界）
            # 转义正则特殊字符
            escaped_code = re.escape(code)
            pattern = r'(?<![A-Za-z0-9])' + escaped_code + r'(?![A-Za-z0-9])'
            if re.search(pattern, card_title):
                hit = True
                match_type = "编号"
        # 2. 球员中文名匹配
        if not hit:
            player_cn = (card.get("player_cn") or "").strip()
            if player_cn and len(player_cn) >= 2 and player_cn in card_title:
                hit = True
                match_type = "中文名"
        # 3. 球员英文名匹配（大小写不敏感）
        if not hit:
            player_en = (card.get("player_en") or "").strip()
            if player_en and len(player_en) >= 3 and player_en.lower() in title_lower:
                hit = True
                match_type = "英文名"
        if hit:
            matches.append({
                "cid": card.get("cid"),
                "series_name": card.get("series_name", ""),
                "code": code,
                "player_cn": card.get("player_cn", ""),
                "collected": card.get("collected", False),
                "match_type": match_type
            })
    return matches
