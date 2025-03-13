# Log Generator for Vector Testing

这是一个简单的日志生成器应用，主要用于测试 Vector 日志采集功能。应用程序会定期生成日志并写入文件中。

## 功能特点

- 定期生成不同级别的日志（INFO, WARNING, ERROR）
- 支持自定义日志输出路径
- 使用 Kubernetes 部署
- 支持 Docker 容器化

## 项目结构

```
.
├── README.md
├── app/
│   └── main.py
├── Dockerfile
└── k8s/
    ├── deployment.yaml
    └── configmap.yaml
```

## 构建和运行

### 本地运行

```bash
python app/main.py
```

### 构建 Docker 镜像

```bash
docker build -t log-generator:latest .
```

### 部署到 Kubernetes

```bash
kubectl apply -f k8s/
```

## 配置说明

日志配置可以通过环境变量进行修改：

- LOG_FILE_PATH: 日志文件路径（默认: /var/log/app.log）
- LOG_INTERVAL: 日志生成间隔，单位秒（默认: 5）

## Vector 配置建议

建议在 Vector 配置中添加以下 source 配置：

```toml
[sources.log_generator]
type = "file"
include = ["/var/log/app.log"]
```

## 监控和维护

可以通过以下命令查看应用状态：

```bash
kubectl get pods -l app=log-generator
kubectl logs -l app=log-generator
```

# Vector 日志采集实现文档

## 功能概述
使用 Vector 采集 Kubernetes 容器内的日志文件，并添加 Kubernetes 元数据。

## 实现方案

### 1. 日志采集配置
- 使用 `file` source 采集容器内的日志文件
- 路径模式：`/var/log/app/**/*.log`
- 采用 DaemonSet 方式部署 Vector

### 2. Kubernetes 元数据提取
使用 VRL (Vector Remap Language) 从文件路径中提取 Kubernetes 元数据：

```yaml
transforms:
  extract_k8s_metadata:
    type: remap
    inputs: [logfile]
    source: |
      parts = split!(.file, "/")
      .kubernetes = {
        "pod_namespace": parts[4],
        "deployment": parts[5],
        "pod_name": parts[6],
        "file_path": .file
      }
```

#### 性能优化考虑
1. 使用 `split` 而不是正则表达式：
   - 时间复杂度：O(n)
   - 内存消耗小
   - 实现简单
   - 维护成本低

2. 移除不必要的判断：
   - 文件路径一定存在
   - 格式固定
   - Source 配置已限定路径格式

### 3. 输出格式
```json
{
  "file": "/var/log/app/default/log-generator/log-generator-6bf46b577c-st9dn/app.log",
  "host": "vector-l5xrh",
  "kubernetes": {
    "pod_namespace": "default",
    "deployment": "log-generator",
    "pod_name": "log-generator-6bf46b577c-st9dn",
    "file_path": "/var/log/app/default/log-generator/log-generator-6bf46b577c-st9dn/app.log"
  },
  "message": "{\"timestamp\": \"2025-03-07T06:27:08.667005\", ...}",
  "source_type": "file",
  "timestamp": "2025-03-07T06:27:09.623323406Z"
}
```

### 4. 数据输出
1. 标准输出（用于调试）：
```yaml
stdout:
  type: console
  inputs: [extract_k8s_metadata]
  encoding:
    codec: json
```

2. Kafka 输出：
```yaml
kafka_output:
  type: kafka
  inputs: [extract_k8s_metadata]
  bootstrap_servers: "kafka-test.default.svc.cluster.local:9092"
  topic: "k8s-logs-{{ kubernetes.pod_namespace }}"
  encoding:
    codec: json
  compression: gzip
  key_field: .kubernetes.pod_name
```

### 5. 监控指标
使用 Vector 内置的指标监控：
```yaml
sources:
  internal_metrics:
    type: internal_metrics

sinks:
  prom_exporter:
    type: prometheus_exporter
    inputs: [host_metrics, internal_metrics]
    address: 0.0.0.0:9090
```

## 部署说明

### 1. 前置条件
- Kubernetes 集群
- 容器日志目录挂载到 `/var/log/app/`
- Kafka 服务可用

### 2. 配置文件
- 完整配置见 `vector-file.yaml`
- 使用 ConfigMap 方式管理配置

### 3. 权限要求
- 需要读取容器日志目录
- 需要访问 Kafka 服务

## 注意事项
1. 路径格式必须符合规范：`/var/log/app/<namespace>/<deployment>/<pod>/xxx.log`
2. 确保日志文件权限正确
3. Kafka topic 会根据 namespace 自动创建

## 性能优化建议
1. 根据实际需求调整 buffer 大小
2. 适当配置 Kafka 压缩
3. 监控 Vector 资源使用情况

## 监控指标
1. 日志处理速率
2. 错误率
3. 资源使用情况

## 故障排查
1. 检查日志文件权限
2. 验证 Kafka 连接
3. 查看 Vector 运行日志

## 维护建议
1. 定期检查日志积压情况
2. 监控磁盘使用
3. 及时更新 Vector 版本 