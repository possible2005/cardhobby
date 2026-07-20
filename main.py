# -*- coding: utf-8 -*-
"""
CardHobby 卡片交易信息抓取工具

这个应用程序是一个基于 Flask 的 web 服务，用于从 cardhobby.com.cn 网站抓取卡片交易信息。
主要功能包括：
1. 接收用户的搜索关键字
2. 使用 Playwright 自动化浏览器抓取相关卡片信息
3. 将抓取的数据保存到 CSV 文件
4. 提供标记已出价卡片的功能
5. 通过 API 接口返回抓取结果

技术栈：
- Flask: Web 框架，提供 API 接口
- Playwright: 浏览器自动化工具，用于网页抓取
- Pandas: 数据处理库，用于操作 CSV 文件
"""

# 导入所需库
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import random
import os
import re
import threading
import json
from datetime import datetime

# 初始化 Flask 应用
# static_folder='.' 表示静态文件存放在当前目录
# static_url_path='' 表示静态文件的 URL 路径为空，直接访问根路径即可
app = Flask(__name__, static_folder='.', static_url_path='')

# ============================================================
# 监控功能相关常量与全局锁
# ============================================================
# 监控配置文件路径
MONITOR_CONFIG_FILE = "monitor_config.json"
# 监控历史记录文件路径
MONITOR_HISTORY_FILE = "monitor_history.json"
# 文件读写锁，保证线程安全
monitor_lock = threading.Lock()

# 默认监控配置
DEFAULT_MONITOR_CONFIG = {
    "keywords": [],
    "schedule_time": "09:00",
    "enabled": False,
    "last_run": None,
    "last_run_status": None
}


def load_monitor_config():
    """
    加载监控配置文件，如果文件不存在则返回默认配置
    
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
    保存监控配置到文件
    
    Args:
        config (dict): 监控配置字典
    """
    with monitor_lock:
        with open(MONITOR_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


def load_monitor_history():
    """
    加载监控历史记录
    
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
    追加一条监控历史记录
    
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


def run_monitor_once():
    """
    执行一次完整的监控抓取：遍历所有关键字，逐个调用 scrape_cardhobby，
    并将每个关键字的运行记录写入历史文件，同时更新配置中的 last_run 字段。
    
    Returns:
        list: 每个关键字的运行结果摘要列表
    """
    config = load_monitor_config()
    keywords = config.get("keywords", [])
    results_summary = []
    # 整体运行状态，默认 success，遇到错误则置为 error
    overall_status = "success"
    now_ts = int(time.time())
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for kw in keywords:
        try:
            data_list = scrape_cardhobby(kw)
            record = {
                "timestamp": now_ts,
                "time_str": now_str,
                "keyword": kw,
                "total_items": len(data_list),
                "status": "success",
                "error": None
            }
        except Exception as e:
            record = {
                "timestamp": now_ts,
                "time_str": now_str,
                "keyword": kw,
                "total_items": 0,
                "status": "error",
                "error": str(e)
            }
            overall_status = "error"
        results_summary.append(record)
        append_monitor_history(record)

    # 更新配置中的 last_run 与 last_run_status
    config["last_run"] = now_ts
    config["last_run_status"] = overall_status
    save_monitor_config(config)

    return results_summary


def monitor_scheduler_loop():
    """
    后台监控调度线程的主循环：
    每分钟检查一次当前时间是否匹配配置的 schedule_time，
    如果匹配且 enabled 为 true，则执行一次监控抓取。
    """
    last_triggered_date = None
    while True:
        try:
            config = load_monitor_config()
            if config.get("enabled", False):
                schedule_time = config.get("schedule_time", "09:00")
                now = datetime.now()
                current_time_str = now.strftime("%H:%M")
                today_str = now.strftime("%Y-%m-%d")
                # 当时间匹配且当天未触发过，则执行一次
                if current_time_str == schedule_time and last_triggered_date != today_str:
                    last_triggered_date = today_str
                    run_monitor_once()
        except Exception as e:
            print(f"[监控线程] 异常: {e}")
        # 每分钟检查一次
        time.sleep(60)


def scrape_cardhobby(keyword):
    """
    从 cardhobby.com.cn 网站抓取卡片交易信息
    
    Args:
        keyword: 搜索关键字
    
    Returns:
        data_list: 包含抓取结果的字典列表
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
            if len(card_elements) == 0: break
                
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
                if not next_button: break
                # 检查下一页按钮是否可用
                is_disabled = next_button.get_attribute("disabled") is not None or "disabled" in (next_button.get_attribute("class") or "")
                # 如果按钮不可用，退出循环
                if is_disabled: break
                
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
        
    # 如果有抓取到数据
    if data_list:
        # 将数据转换为 DataFrame
        df_new = pd.DataFrame(data_list)
        # 处理关键字中的空格，用于生成文件名
        safe_keyword = keyword.replace(" ", "_") 
        # 生成 CSV 文件名
        csv_filename = f"cardhobby_prices_{safe_keyword}.csv"
        
        # 如果文件已存在
        if os.path.exists(csv_filename):
            print(f"[后端] 发现历史数据文件，正在合并 '已出价' 状态...")
            # 读取历史数据
            df_old = pd.read_csv(csv_filename, encoding="utf-8-sig")
            # 如果历史数据包含 'Is_Bid' 列
            if 'Is_Bid' in df_old.columns:
                # 生成唯一键，用于匹配相同的卡片
                df_old['unique_key'] = df_old['Card_Title'] + "_" + df_old['Seller_Name']
                df_new['unique_key'] = df_new['Card_Title'] + "_" + df_new['Seller_Name']
                # 获取已标记为出价的记录
                bid_records = df_old[df_old['Is_Bid'] == '是']['unique_key'].tolist()
                # 在新数据中标记已出价的卡片
                df_new.loc[df_new['unique_key'].isin(bid_records), 'Is_Bid'] = '是'
                # 删除唯一键列
                df_new = df_new.drop(columns=['unique_key'])

        # 将数据保存到 CSV 文件
        df_new.to_csv(csv_filename, index=False, encoding="utf-8-sig")
        
    # 返回抓取的数据列表
    return data_list


@app.route('/')
def index():
    """
    首页路由，返回静态 HTML 文件
    """
    return app.send_static_file('index.html')


@app.route('/api/search', methods=['POST'])
def api_search():
    """
    搜索 API，接收关键字并返回抓取结果
    
    请求体：
    {"keyword": "搜索关键字"}
    
    返回：
    JSON 格式的抓取结果列表
    """
    # 从请求体中获取关键字
    keyword = request.json.get('keyword')
    # 如果关键字为空，返回错误
    if not keyword: return jsonify({"error": "关键字不能为空"}), 400
    # 调用抓取函数
    result_data = scrape_cardhobby(keyword)
    # 返回结果
    return jsonify(result_data)


@app.route('/api/mark_bid', methods=['POST'])
def mark_bid():
    """
    标记出价 API，将指定卡片标记为已出价
    
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
    if not keyword or not items_to_mark: return jsonify({"error": "缺少必要参数"}), 400

    # 处理关键字中的空格，用于生成文件名
    safe_keyword = keyword.replace(" ", "_")
    # 生成 CSV 文件名
    csv_filename = f"cardhobby_prices_{safe_keyword}.csv"
    # 检查文件是否存在
    if not os.path.exists(csv_filename): return jsonify({"error": "找不到对应的 CSV 数据文件"}), 404

    try:
        # 读取 CSV 文件
        df = pd.read_csv(csv_filename, encoding="utf-8-sig")
        # 如果文件中没有 'Is_Bid' 列，添加该列
        if 'Is_Bid' not in df.columns: df['Is_Bid'] = '否'

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


# ============================================================
# 监控功能 API 接口
# ============================================================
@app.route('/api/monitor/config', methods=['GET'])
def api_monitor_config_get():
    """
    获取当前监控配置
    
    返回：
        JSON 格式的监控配置
    """
    config = load_monitor_config()
    return jsonify(config)


@app.route('/api/monitor/config', methods=['POST'])
def api_monitor_config_save():
    """
    保存监控配置
    
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


@app.route('/api/monitor/run', methods=['POST'])
def api_monitor_run():
    """
    手动触发一次监控抓取，遍历所有关键字逐个调用 scrape_cardhobby
    
    返回：
        {"success": true, "results": [每个关键字的运行结果摘要]}
    """
    try:
        results = run_monitor_once()
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/monitor/data', methods=['GET'])
def api_monitor_data():
    """
    读取指定关键字的 CSV 数据并返回 JSON
    
    请求参数：
        keyword: 搜索关键字
    
    返回：
        JSON 格式的数据列表
    """
    keyword = request.args.get('keyword', '').strip()
    if not keyword:
        return jsonify({"error": "关键字不能为空"}), 400
    safe_keyword = keyword.replace(" ", "_")
    csv_filename = f"cardhobby_prices_{safe_keyword}.csv"
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
                except:
                    row["Price_CNY"] = 0.0
            if "Scrape_Time" in row and row["Scrape_Time"] != "":
                try:
                    row["Scrape_Time"] = int(float(row["Scrape_Time"]))
                except:
                    pass
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/monitor/history', methods=['GET'])
def api_monitor_history():
    """
    获取监控运行历史记录

    返回：
        JSON 格式的历史记录列表
    """
    history = load_monitor_history()
    return jsonify(history)


@app.route('/api/monitor/history', methods=['DELETE'])
def api_monitor_history_delete():
    """
    批量删除监控历史记录，并删除对应关键字的 CSV 文件

    请求体：
    {
        "indices": [0, 2, 4]   // 要删除的历史记录索引列表（基于当前历史列表）
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
        deleted_count = 0

        for idx in unique_indices:
            if isinstance(idx, int) and 0 <= idx < len(history):
                rec = history.pop(idx)
                deleted_keywords.add(rec.get("keyword", ""))
                deleted_count += 1

        # 写回历史文件
        with open(MONITOR_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    # 删除对应关键字的 CSV 文件
    deleted_csv_files = []
    for kw in deleted_keywords:
        if not kw:
            continue
        safe_keyword = kw.replace(" ", "_")
        csv_filename = f"cardhobby_prices_{safe_keyword}.csv"
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


# ============================================================
# 抓取数据 ↔ 凑套卡片 匹配
# ============================================================
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


@app.route('/api/scrape/match', methods=['POST'])
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
                "Has_Uncollected_Match": true   // 是否匹配到"未搜集"的卡片
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
        except:
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


# ============================================================
# 凑套系列管理 API
# ============================================================
COLLECTION_FILE = "collections.json"
collection_lock = threading.Lock()


def load_collections():
    """加载凑套系列数据"""
    with collection_lock:
        if os.path.exists(COLLECTION_FILE):
            try:
                with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
    return []


def save_collections(data):
    """保存凑套系列数据"""
    with collection_lock:
        with open(COLLECTION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def parse_collection_text(text):
    """
    解析用户输入的凑套系列文本，提取系列名称和卡片列表

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
    import re
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


@app.route('/api/collections', methods=['GET'])
def api_collections_list():
    """获取所有凑套系列"""
    data = load_collections()
    return jsonify(data)


@app.route('/api/collections', methods=['POST'])
def api_collections_create():
    """
    创建新的凑套系列

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


@app.route('/api/collections/<int:cid>/cards', methods=['PUT'])
def api_collections_update_cards(cid):
    """
    更新卡片状态（批量）

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


@app.route('/api/collections/<int:cid>', methods=['DELETE'])
def api_collections_delete(cid):
    """删除凑套系列"""
    collections = load_collections()
    collections = [c for c in collections if c.get("id") != cid]
    save_collections(collections)
    return jsonify({"success": True})


if __name__ == "__main__":
    """
    应用程序入口，启动 Flask 服务器
    debug=True 表示启用调试模式
    port=5000 表示服务器端口为 5000
    """
    # 启动后台监控调度线程（daemon=True 表示主进程退出时该线程自动结束）
    monitor_thread = threading.Thread(target=monitor_scheduler_loop, daemon=True)
    monitor_thread.start()
    print("[监控] 后台监控线程已启动")
    app.run(debug=True, host='0.0.0.0', port=5001)