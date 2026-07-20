# 使用轻量级的 Python 3.11 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 先复制依赖文件并安装，利用 Docker 缓存加速后续构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有项目代码到容器中
COPY . .

# 声明容器内部暴露的端口（根据你的应用实际端口修改）
EXPOSE 8000

# 启动命令（需根据你的实际入口文件修改）
# Flask 示例: CMD ["python", "app.py"]
# FastAPI 示例: CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "app.py"]