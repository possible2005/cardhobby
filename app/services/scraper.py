# -*- coding: utf-8 -*-
"""
卡片交易信息爬虫服务。

使用 Playwright 自动化浏览器从 cardhobby.com.cn 网站抓取卡片交易信息，
并将结果保存到 CSV 文件。
"""

import os
import time
import random

import pandas as pd
from playwright.sync_api import sync_playwright

from app.config import get_csv_filename


def scrape_cardhobby(keyword):
    """
    从 cardhobby.com.cn 网站抓取卡片交易信息。

    Args:
        keyword (str): 搜索关键字

    Returns:
        dict: {"new_count": N, "total_count": M, "items": [...]}
            - new_count: 本次新增的卡片数
            - total_count: 合并后该关键字的卡片总数
            - items: 本次新增的卡片列表（旧卡片不会重复返回）
    """
    # 初始化数据列表和抓取时间戳
    data_list = []
    scrape_timestamp = int(time.time())

    # 使用 Playwright 启动浏览器
    with sync_playwright() as p:
        # 启动无头浏览器（无界面模式）
        browser = p.chromium.launch(headless=True)
        # 创建新页面
        page = browser.new_page()

        # 定义目标网站 URL
        base_url = "https://www.cardhobby.com.cn/market"
        # 访问目标网站，等待页面加载完成，超时时间 60 秒
        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)

        # 等待搜索框加载完成，超时时间 15 秒
        page.wait_for_selector("#kword", timeout=15000)
        # 填充搜索关键字
        page.fill("#kword", keyword)
        # 点击搜索按钮
        page.click("#qbtn")

        # 初始化页码
        page_num = 1
        # 循环抓取每页数据
        while True:
            try:
                # 等待卡片信息加载完成，超时时间 15 秒
                page.wait_for_selector(".card-info", timeout=15000)
                # 随机等待 2-4 秒，模拟人类操作，避免被反爬
                time.sleep(random.uniform(2, 4))
            except Exception:
                # 如果超时或出错，退出循环
                break

            # 获取所有卡片元素
            card_elements = page.query_selector_all(".card-info")
            # 如果没有卡片元素，退出循环
            if len(card_elements) == 0:
                break

            # 遍历每个卡片元素，提取信息
            for card in card_elements:
                try:
                    # 提取卡片标题
                    title_elem = card.query_selector(".ci-row.ci-tile a")
                    title = title_elem.get_attribute("title") if title_elem else "未提取到标题"

                    # 提取卡片详情页 URL
                    href = title_elem.get_attribute("href") if title_elem else ""
                    # 拼接完整域名
                    card_url = f"https://www.cardhobby.com.cn{href}" if href else ""

                    # 提取价格
                    price_elem = card.query_selector(".ci-row.price.titletext.price_size")
                    clean_price = float(price_elem.inner_text().replace("￥", "").strip()) if price_elem else 0.0

                    # 提取卖家名称
                    seller_elem = card.query_selector(".ci-row.name")
                    seller_name = seller_elem.inner_text().strip() if seller_elem else "未知卖家"

                    # 提取结束时间
                    time_elem = card.query_selector(".time")
                    end_time = time_elem.inner_text().strip() if time_elem else "未知时间"

                    # 将提取的信息添加到数据列表
                    data_list.append({
                        "Keyword": keyword,               # 搜索关键字
                        "Seller_Name": seller_name,       # 卖家名称
                        "Card_Title": title,              # 卡片标题
                        "Card_URL": card_url,             # 卡片详情页 URL
                        "Price_CNY": clean_price,         # 价格（人民币）
                        "End_Time": end_time,             # 结束时间
                        "Scrape_Time": scrape_timestamp,  # 抓取时间戳
                        "Is_Bid": "否"                    # 是否已出价（默认否）
                    })
                except Exception:
                    # 如果提取某个卡片信息出错，跳过该卡片
                    continue

            try:
                # 查找下一页按钮
                next_button = page.query_selector("button.btn-next")
                # 如果没有下一页按钮，退出循环
                if not next_button:
                    break
                # 检查下一页按钮是否可用
                is_disabled = next_button.get_attribute("disabled") is not None or "disabled" in (next_button.get_attribute("class") or "")
                # 如果按钮不可用，退出循环
                if is_disabled:
                    break

                # 点击下一页按钮
                next_button.click()
                # 页码加 1
                page_num += 1
                # 等待 2 秒，确保页面加载完成
                time.sleep(2)
            except Exception:
                # 如果点击下一页出错，退出循环
                break

        # 关闭浏览器
        browser.close()

    # 生成 CSV 文件路径（写入 data/ 目录）
    csv_filename = get_csv_filename(keyword)

    # 将本次抓取数据转换为 DataFrame
    df_new = pd.DataFrame(data_list) if data_list else pd.DataFrame(
        columns=["Keyword", "Seller_Name", "Card_Title", "Card_URL",
                 "Price_CNY", "End_Time", "Scrape_Time", "Is_Bid"]
    )

    # 兼容旧 CSV 可能没有 unique_key 列：以 Card_Title + Seller_Name 作为唯一键
    df_new["unique_key"] = df_new["Card_Title"].astype(str) + "_" + df_new["Seller_Name"].astype(str)

    # 已存在记录的唯一键集合（用于增量去重）与已出价记录集合
    existing_keys = set()
    bid_keys = set()
    df_old = None
    if os.path.exists(csv_filename):
        print(f"[后端] 发现历史数据文件，正在做增量合并...")
        try:
            df_old = pd.read_csv(csv_filename, encoding="utf-8-sig")
        except Exception as e:
            print(f"[后端] 读取旧 CSV 失败，将覆盖: {e}")
            df_old = None

    if df_old is not None and len(df_old) > 0:
        # 兼容旧 CSV 可能缺少列
        if "Card_Title" not in df_old.columns or "Seller_Name" not in df_old.columns:
            df_old = None
        else:
            df_old["unique_key"] = df_old["Card_Title"].astype(str) + "_" + df_old["Seller_Name"].astype(str)
            existing_keys = set(df_old["unique_key"].tolist())
            if "Is_Bid" in df_old.columns:
                bid_keys = set(
                    df_old.loc[df_old["Is_Bid"] == "是", "unique_key"].tolist()
                )

    # 仅保留新出现的卡片（增量）
    df_increment = df_new[~df_new["unique_key"].isin(existing_keys)].copy()

    # 保留旧卡片的 Is_Bid 状态：对新卡片如果命中 bid_keys 则标记为 "是"
    if len(bid_keys) > 0 and len(df_increment) > 0:
        df_increment.loc[df_increment["unique_key"].isin(bid_keys), "Is_Bid"] = "是"

    # 追加到 CSV（而非覆盖整个文件）
    if len(df_increment) > 0:
        # 删除辅助列，保持 CSV 列结构不变
        df_to_append = df_increment.drop(columns=["unique_key"])
        write_header = not os.path.exists(csv_filename)
        df_to_append.to_csv(
            csv_filename,
            mode="a",
            header=write_header,
            index=False,
            encoding="utf-8-sig",
        )
        print(f"[后端] 新增 {len(df_increment)} 条卡片，已追加到 {csv_filename}")

    # 计算总数（旧 + 新增）
    total_count = len(existing_keys) + len(df_increment)
    new_count = len(df_increment)
    new_items = df_increment.drop(columns=["unique_key"]).to_dict(orient="records") if len(df_increment) > 0 else []

    # 返回结构：含新增数和总数
    return {
        "new_count": new_count,
        "total_count": total_count,
        "items": new_items,
    }
