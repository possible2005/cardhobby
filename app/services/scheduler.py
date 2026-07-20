# -*- coding: utf-8 -*-
"""
监控调度服务。

后台线程定时检查当前时间是否匹配配置的 schedule_time，
若匹配且 enabled 为 true，则执行一次完整的监控抓取。
"""

import time
from datetime import datetime

from app.models.monitor import load_monitor_config
from app.services.scraper import scrape_cardhobby
from app.models.monitor import append_monitor_history, save_monitor_config


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
            # scrape_cardhobby 返回 {"new_count": N, "total_count": M, "items": [...]}
            result = scrape_cardhobby(kw)
            new_count = result.get("new_count", 0)
            record = {
                "timestamp": now_ts,
                "time_str": now_str,
                "keyword": kw,
                "total_items": new_count,
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
