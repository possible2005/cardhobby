# -*- coding: utf-8 -*-
"""
首页路由。
"""

from flask import Blueprint, current_app

index_bp = Blueprint('index', __name__)


@index_bp.route('/')
def index():
    """
    首页路由，返回静态 HTML 文件。
    """
    return current_app.send_static_file('index.html')
