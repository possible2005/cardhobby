# 使用轻量级的 Python 3.11 镜像
FROM python:3.11-slim

# 安装 Playwright 浏览器运行所需的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 先复制依赖文件并安装，利用 Docker 缓存加速后续构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright Chromium 浏览器
RUN playwright install chromium

# 复制项目代码到容器中
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

# 声明容器内部暴露的端口（与 app/config.py 中 PORT=5001 一致）
EXPOSE 5001

# 启动命令
CMD ["python", "run.py"]
