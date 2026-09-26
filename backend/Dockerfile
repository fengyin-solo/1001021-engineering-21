FROM python:3.12-slim
WORKDIR /srv/app
# 按完整锁文件安装，镜像内依赖版本与本地一致
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
