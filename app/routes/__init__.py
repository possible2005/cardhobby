# -*- coding: utf-8 -*-
"""
蓝图注册模块。

统一注册所有路由蓝图到 Flask 应用。
"""


def register_blueprints(app):
    """
    将所有蓝图注册到 Flask 应用。

    Args:
        app (Flask): Flask 应用实例
    """
    from app.routes.scrape import scrape_bp
    from app.routes.monitor import monitor_bp
    from app.routes.collection import collection_bp
    from app.routes.index import index_bp
    from app.routes.system import system_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(scrape_bp)
    app.register_blueprint(monitor_bp)
    app.register_blueprint(collection_bp)
    app.register_blueprint(system_bp)
