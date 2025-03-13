FROM python:3.9-slim

WORKDIR /app

COPY app/main.py .

# 创建日志目录
RUN mkdir -p /var/log/app

# 设置默认环境变量
ENV LOG_FILE_PATH=/var/log/app/app.log \
    BATCH_SIZE=1000 \
    THREADS=4 \
    ENABLE_STDOUT=true \
    ENABLE_FILE=true \
    LOGS_PER_SECOND=10

# 设置权限
RUN chown -R nobody:nogroup /var/log/app && \
    chmod -R 755 /var/log/app

# 使用非 root 用户运行
USER nobody

CMD ["python", "main.py"] 