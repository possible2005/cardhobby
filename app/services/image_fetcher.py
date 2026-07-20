# -*- coding: utf-8 -*-
"""
卡片图片抓取服务。

使用 Playwright 在一个浏览器 session 内批量抓取多个卡淘详情页的图片 URL，
并通过 app.models.cache 持久化到 data/card_images_cache.json。
"""

import os
import glob

import pandas as pd
from playwright.sync_api import sync_playwright

from app.config import DATA_DIR
from app.models.cache import load_image_cache, save_image_cache
from app.services.matcher import match_scraped_to_collections


def _extract_image_from_page(page):
    """
    从一个已加载完成的 Playwright Page 中提取主图 URL。

    尝试的选择器顺序：
        1. .product-img img
        2. .swiper-slide img
        3. img.main-pic
    """
    selectors = [".product-img img", ".swiper-slide img", "img.main-pic"]
    for sel in selectors:
        try:
            elem = page.query_selector(sel)
            if elem:
                src = elem.get_attribute("src")
                if src:
                    return src
        except Exception:
            continue
    return None


def fetch_images_for_collection(cid, cards):
    """
    为一个凑套系列中的卡片抓取图片 URL。

    Args:
        cid (int): 系列 ID
        cards (list): 该系列的卡片列表，每项形如
            {"code": "FAN-2", "player_cn": "...", "player_en": "...", "team": "...", "collected": ...}

    Returns:
        dict: {卡片编号 code: image_url}
    """
    if not cards:
        return {}

    # 1. 在所有 CSV 中匹配出每个 code 对应的 Card_URL
    code_to_url = _find_card_urls_for_collection(cards)
    if not code_to_url:
        return {}

    # 2. 加载缓存，区分需要抓取的 URL
    cache = load_image_cache()
    result = {}
    urls_to_fetch = []
    url_to_codes = {}  # 一个 URL 可能对应多个 code
    for code, url in code_to_url.items():
        if not url:
            continue
        if url in cache:
            result[code] = cache[url]
        else:
            urls_to_fetch.append(url)
            url_to_codes.setdefault(url, []).append(code)

    # 3. 用一个 Playwright session 批量抓取
    if urls_to_fetch:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                for url in urls_to_fetch:
                    image_url = None
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=10000)
                        image_url = _extract_image_from_page(page)
                    except Exception as e:
                        print(f"[图片抓取] {url} 失败: {e}")
                        image_url = None
                    # 写入缓存与结果
                    cache[url] = image_url
                    for code in url_to_codes.get(url, []):
                        result[code] = image_url
                browser.close()
            # 持久化缓存
            save_image_cache(cache)
        except Exception as e:
            print(f"[图片抓取] Playwright 启动失败: {e}")

    return result


def _find_card_urls_for_collection(cards):
    """
    遍历 data/ 下所有 CSV，使用 matcher 的逻辑匹配 Card_Title，
    返回该系列每张卡片对应的 Card_URL。

    Args:
        cards (list): 卡片列表

    Returns:
        dict: {code: Card_URL}
    """
    # 构造 all_cards 结构（仅当前系列的卡片，matcher 只需这些字段）
    all_cards_for_match = [
        {
            "cid": None,
            "series_name": "",
            "code": c.get("code", ""),
            "player_cn": c.get("player_cn", ""),
            "player_en": c.get("player_en", ""),
            "team": c.get("team", ""),
            "collected": c.get("collected", False),
        }
        for c in cards
    ]

    code_to_url = {}
    csv_files = glob.glob(os.path.join(DATA_DIR, "cardhobby_prices_*.csv"))
    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
        except Exception:
            continue
        if "Card_Title" not in df.columns or "Card_URL" not in df.columns:
            continue
        for _, row in df.iterrows():
            title = str(row.get("Card_Title", ""))
            url = str(row.get("Card_URL", ""))
            if not title or not url:
                continue
            matches = match_scraped_to_collections(title, all_cards_for_match)
            if matches:
                for m in matches:
                    code = m.get("code", "")
                    if code and code not in code_to_url:
                        code_to_url[code] = url

    return code_to_url
