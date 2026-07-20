# -*- coding: utf-8 -*-
"""
凑套系列文本解析工具。

将用户输入的文本解析为结构化的凑套系列数据。
"""

import re


def parse_collection_text(text):
    """
    解析用户输入的凑套系列文本，提取系列名称和卡片列表。

    示例输入：
    topps狂热
     - FAN-2 扬尼斯·阿德托昆博 (Giannis Antetokounmpo) - 密尔沃基雄鹿
     - FAN-13 保罗·班切罗 (Paolo Banchero) - 奥兰多魔术

    返回：
        {
            "series_name": "topps 狂热",
            "cards": [
                {"code": "FAN-2", "player_cn": "扬尼斯·阿德托昆博", "player_en": "Giannis Antetokounmpo", "team": "密尔沃基雄鹿", "collected": False},
                ...
            ]
        }
    """
    lines = text.strip().split("\n")
    series_name = ""
    cards = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 第一行非"-"开头的是系列名称
        if not line.startswith("-") and not line.startswith("•") and not line.startswith("•"):
            if not series_name:
                series_name = line
            continue

        # 去掉前导 - 或 • 或 *
        content = re.sub(r"^[-•*\s]+", "", line).strip()
        if not content:
            continue

        # 去掉开头可能的复选框符号 [ ]、[x]、[X]、☑、✔ 等
        content = re.sub(r"^\[[ xX✓✔☑]?\]\s*", "", content).strip()
        if not content:
            continue

        # 尝试匹配: CODE 中文名 (英文名) - 球队
        # 也可以没有英文或没有球队
        # 模式1: FAN-2 扬尼斯·阿德托昆博 (Giannis Antetokounmpo) - 密尔沃基雄鹿
        # 模式2: FAN-2 扬尼斯·阿德托昆博 (Giannis Antetokounmpo)
        # 模式3: FAN-2 扬尼斯·阿德托昆博 - 密尔沃基雄鹿
        # 模式4: FAN-2 扬尼斯·阿德托昆博

        card = {"code": "", "player_cn": "", "player_en": "", "team": "", "collected": False}

        # 提取编号
        code_match = re.match(r"^([A-Za-z]+[-_]?\d+[A-Za-z]*)", content)
        if code_match:
            card["code"] = code_match.group(1)
            content = content[len(card["code"]):].strip()

        # 提取英文名（括号内）
        en_match = re.search(r"\(([^)]+)\)", content)
        if en_match:
            card["player_en"] = en_match.group(1).strip()
            content = content[:en_match.start()].strip() + " " + content[en_match.end():].strip()
            content = content.strip()

        # 提取球队（最后一个 - 之后的部分）
        if " - " in content:
            parts = content.rsplit(" - ", 1)
            card["player_cn"] = parts[0].strip()
            card["team"] = parts[1].strip()
        else:
            card["player_cn"] = content.strip()

        if card["code"] or card["player_cn"]:
            cards.append(card)

    # 规范化系列名称：去除多余空格
    series_name = re.sub(r"\s+", " ", series_name).strip()

    return {"series_name": series_name, "cards": cards}
