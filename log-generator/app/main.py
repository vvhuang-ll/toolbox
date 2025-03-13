import logging
import os
import random
import time
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
import queue
import threading
import signal

# 配置环境变量
LOG_FILE_PATH = os.getenv('LOG_FILE_PATH', '/var/log/app.log')
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '1000'))  # 每批次日志数
THREADS = int(os.getenv('THREADS', '4'))  # 生成线程数
ENABLE_STDOUT = os.getenv('ENABLE_STDOUT', 'false').lower() == 'true'  # 是否输出到标准输出
ENABLE_FILE = os.getenv('ENABLE_FILE', 'true').lower() == 'true'  # 是否输出到文件
LOGS_PER_SECOND = float(os.getenv('LOGS_PER_SECOND', '10'))  # 每秒生成的日志数量

# 全局运行标志和速率控制
running = True
log_interval = 1.0 / LOGS_PER_SECOND  # 计算日志生成间隔
rate_limiter = threading.Lock()
last_log_time = time.time()

# 信号处理
def signal_handler(signum, frame):
    global running
    print("接收到停止信号，正在优雅关闭...")
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# 确保日志目录存在（仅在启用文件输出时创建）
if ENABLE_FILE:
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

class JsonFormatter(logging.Formatter):
    """自定义JSON格式的日志格式化器"""
    def format(self, record):
        # 基础字段 - 减少字段数量以提高性能
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "trace_id": str(uuid.uuid4()),
            "host": os.uname().nodename,
            "pid": os.getpid()
        }
        
        # 添加额外字段
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
            
        return json.dumps(log_data, ensure_ascii=False)

class AsyncQueueHandler(logging.Handler):
    """异步队列处理器"""
    def __init__(self, file_path):
        super().__init__()
        self.queue = queue.Queue(maxsize=100000)  # 队列大小限制
        self.file_path = file_path
        self.batch = []
        self.batch_lock = threading.Lock()
        self.running = True
        self.last_write_time = time.time()
        self.writer_thread = threading.Thread(target=self._writer)
        self.writer_thread.daemon = True
        self.writer_thread.start()

    def emit(self, record):
        try:
            self.queue.put_nowait(self.format(record))
        except queue.Full:
            pass  # 队列满时丢弃日志

    def _writer(self):
        with open(self.file_path, 'a', buffering=1024*1024) as f:  # 1MB buffer
            while self.running:
                try:
                    current_time = time.time()
                    # 批量获取日志
                    while len(self.batch) < BATCH_SIZE:
                        try:
                            log = self.queue.get_nowait()
                            self.batch.append(log + '\n')
                        except queue.Empty:
                            break

                    # 当达到批量大小或距离上次写入超过1秒时写入
                    if self.batch and (len(self.batch) >= BATCH_SIZE or 
                                     current_time - self.last_write_time >= 1.0):
                        with self.batch_lock:
                            f.writelines(self.batch)
                            f.flush()  # 确保写入磁盘
                            self.batch = []
                            self.last_write_time = current_time
                    else:
                        time.sleep(0.1)  # 避免空转
                except Exception as e:
                    print(f"写入日志时发生错误: {e}")
                    continue

    def close(self):
        self.running = False
        self.writer_thread.join()
        super().close()

# 配置日志
logger = logging.getLogger("log-generator")
logger.setLevel(logging.INFO)

# 添加文件处理器（如果启用）
if ENABLE_FILE:
    file_handler = AsyncQueueHandler(LOG_FILE_PATH)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

# 添加标准输出处理器（如果启用）
if ENABLE_STDOUT:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JsonFormatter())
    logger.addHandler(console_handler)

# 确保至少启用了一种输出方式
if not (ENABLE_FILE or ENABLE_STDOUT):
    raise ValueError("至少需要启用一种日志输出方式（文件或标准输出）")

# 预生成一些固定数据以提高性能
USERS = ["user_" + str(i) for i in range(100, 999)]
ENDPOINTS = ["/api/v1/users", "/api/v1/products", "/api/v1/orders", "/api/v1/analytics", "/api/v1/reports"]
HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
HTTP_STATUS = [200, 201, 202, 204, 301, 302, 400, 401, 403, 404, 500, 502, 503]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
]
LOCATIONS = [
    {"city": "北京", "district": "朝阳区", "isp": "联通", "ip": "123.123.123.123", "coordinates": {"lat": 39.9042, "lon": 116.4074}},
    {"city": "上海", "district": "浦东新区", "isp": "电信", "ip": "124.124.124.124", "coordinates": {"lat": 31.2304, "lon": 121.4737}},
    {"city": "广州", "district": "天河区", "isp": "移动", "ip": "125.125.125.125", "coordinates": {"lat": 23.1291, "lon": 113.2644}},
    {"city": "深圳", "district": "南山区", "isp": "联通", "ip": "126.126.126.126", "coordinates": {"lat": 22.5431, "lon": 114.0579}}
]
DEVICE_INFO = [
    {"os": "Windows", "version": "10", "browser": "Chrome", "device_type": "Desktop"},
    {"os": "MacOS", "version": "11.4", "browser": "Safari", "device_type": "Laptop"},
    {"os": "iOS", "version": "14.6", "browser": "Safari", "device_type": "Mobile"},
    {"os": "Android", "version": "11", "browser": "Chrome", "device_type": "Mobile"}
]
ERROR_DETAILS = {
    400: {"type": "ValidationError", "details": "请求参数验证失败", "solution": "检查请求参数格式"},
    401: {"type": "AuthenticationError", "details": "用户未认证", "solution": "请先登录"},
    403: {"type": "AuthorizationError", "details": "权限不足", "solution": "申请相应权限"},
    404: {"type": "NotFoundError", "details": "资源不存在", "solution": "检查资源标识符"},
    500: {"type": "InternalError", "details": "服务器内部错误", "solution": "请联系技术支持"}
}

def generate_performance_metrics() -> Dict[str, Any]:
    """生成更详细的性能指标"""
    return {
        "system": {
            "cpu": {
                "usage_percent": round(random.uniform(0, 100), 2),
                "load_average": [round(random.uniform(0, 5), 2) for _ in range(3)],
                "core_count": 8,
                "process_count": random.randint(100, 500)
            },
            "memory": {
                "total_gb": 32,
                "used_gb": round(random.uniform(0, 32), 2),
                "used_percent": round(random.uniform(0, 100), 2),
                "swap_used_percent": round(random.uniform(0, 50), 2)
            },
            "disk": {
                "total_gb": 512,
                "used_gb": round(random.uniform(0, 512), 2),
                "used_percent": round(random.uniform(0, 100), 2),
                "io_util_percent": round(random.uniform(0, 100), 2),
                "read_mbps": round(random.uniform(0, 1000), 2),
                "write_mbps": round(random.uniform(0, 1000), 2)
            },
            "network": {
                "rx_mbps": round(random.uniform(0, 1000), 2),
                "tx_mbps": round(random.uniform(0, 1000), 2),
                "established_connections": random.randint(1000, 5000),
                "interface_stats": {
                    "eth0": {
                        "status": "up",
                        "speed": "1000Mbps",
                        "duplex": "full"
                    }
                }
            }
        }
    }

def generate_log():
    """生成包含更多信息的随机日志"""
    global last_log_time
    
    # 速率控制
    with rate_limiter:
        current_time = time.time()
        time_since_last = current_time - last_log_time
        if time_since_last < log_interval:
            time.sleep(log_interval - time_since_last)
        last_log_time = time.time()
    
    metrics = generate_performance_metrics()
    location = random.choice(LOCATIONS)
    device = random.choice(DEVICE_INFO)
    status = random.choice(HTTP_STATUS)
    
    # 生成请求ID和跟踪ID
    request_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    span_id = str(uuid.uuid4())[:16]
    
    # 生成时间相关信息
    current_time = datetime.now()
    
    extra_fields = {
        # 基础请求信息
        "request": {
            "id": request_id,
            "method": random.choice(HTTP_METHODS),
            "endpoint": random.choice(ENDPOINTS),
            "status": status,
            "duration_ms": round(random.uniform(10, 2000), 2),
            "size_bytes": random.randint(500, 15000),
            "protocol": "HTTP/2.0",
            "user_agent": random.choice(USER_AGENTS)
        },
        # 用户信息
        "user": {
            "id": random.choice(USERS),
            "type": random.choice(["free", "premium", "enterprise"]),
            "registration_date": (current_time - timedelta(days=random.randint(1, 365))).isoformat(),
            "last_login": current_time.isoformat()
        },
        # 错误信息（如果状态码是错误）
        "error": ERROR_DETAILS.get(status, {}),
        # 位置信息
        "location": location,
        # 设备信息
        "device": device,
        # 性能指标
        "metrics": metrics,
        # 链路追踪
        "trace": {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": str(uuid.uuid4())[:16],
            "sampled": True,
            "flags": 1
        },
        # 业务指标
        "business_metrics": {
            "queue_size": random.randint(0, 1000),
            "cache_hit_ratio": round(random.uniform(0.5, 1.0), 2),
            "active_users": random.randint(1000, 10000),
            "transaction_count": random.randint(100, 1000)
        }
    }
    
    # 生成详细的日志消息
    message = (
        f"[{extra_fields['request']['method']}] {extra_fields['request']['endpoint']} - "
        f"Status: {status} - Duration: {extra_fields['request']['duration_ms']}ms - "
        f"User: {extra_fields['user']['id']} - "
        f"Location: {location['city']}/{location['district']} - "
        f"Device: {device['os']}/{device['browser']} - "
        f"CPU: {metrics['system']['cpu']['usage_percent']}% - "
        f"Memory: {metrics['system']['memory']['used_percent']}% - "
        f"Network: ↓{metrics['system']['network']['rx_mbps']}Mbps ↑{metrics['system']['network']['tx_mbps']}Mbps"
    )
    
    logger.info(message, extra={"extra_fields": extra_fields})

def log_generator_worker():
    """日志生成工作线程"""
    while running:
        generate_log()

def main():
    """主函数"""
    # 输出启动配置信息
    logger.info("日志生成器启动", extra={
        "extra_fields": {
            "version": "1.0.0",
            "config": {
                "batch_size": BATCH_SIZE,
                "threads": THREADS,
                "enable_stdout": ENABLE_STDOUT,
                "enable_file": ENABLE_FILE,
                "log_file_path": LOG_FILE_PATH if ENABLE_FILE else None,
                "logs_per_second": LOGS_PER_SECOND,
                "log_interval": log_interval
            }
        }
    })
    
    try:
        # 使用线程池并发生成日志
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = [executor.submit(log_generator_worker) for _ in range(THREADS)]
            
            # 等待所有线程完成或收到停止信号
            for future in futures:
                try:
                    future.result()
                except KeyboardInterrupt:
                    break
    finally:
        # 关闭处理器
        for handler in logger.handlers:
            handler.close()
        
        print("日志生成器已停止")

if __name__ == "__main__":
    main() 