# -*- coding: utf-8 -*-
"""
Flask 应用工厂模块。

使用应用工厂模式创建 Flask 应用实例，注册所有蓝图，
并启动后台监控调度线程。
"""

import threading
import os

from flask import Flask

from app.config import HOST, PORT, DEBUG, ensure_data_dir


def create_app():
    """
    创建并配置 Flask 应用实例。

    Returns:
        Flask: 配置完成的 Flask 应用实例
    """
    # 静态文件目录指向项目根目录，便于访问 index.html
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(__name__, static_folder=base_dir, static_url_path='')

    # 确保 data/ 目录存在
    ensure_data_dir()

    # 注册蓝图
    from app.routes import register_blueprints
    register_blueprints(app)

    # 启动后台监控调度线程
    from app.services.scheduler import monitor_scheduler_loop
    monitor_thread = threading.Thread(target=monitor_scheduler_loop, daemon=True)
    monitor_thread.start()
    print("[监控] 后台监控线程已启动")

    return app


def run():
    """启动 Flask 开发服务器。"""
    app = create_app()
    app.run(debug=DEBUG, host=HOST, port=PORT)
