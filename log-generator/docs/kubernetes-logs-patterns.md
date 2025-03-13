# Kubernetes Logs Source 路径模式配置

## 概述
`kubernetes_logs` source 的 `include_paths_glob_patterns` 用于指定要采集的容器日志文件路径模式。这是一个比 `file` source 更专门用于 Kubernetes 环境的配置选项。

## 配置示例

```yaml
sources:
  kubernetes_logs:
    type: kubernetes_logs
    include_paths_glob_patterns:
      - /var/log/pods/**/*.log
      - /var/log/containers/*.log
    exclude_paths_glob_patterns:
      - /var/log/pods/kube-system_*.log
```

## 路径模式说明

### 1. 默认路径模式
Kubernetes 容器日志的默认路径格式：
- containerd: `/var/log/pods/<namespace>_<pod>_<uid>/<container>/*.log`
- docker: `/var/log/containers/<pod>_<namespace>_<container>-<container_id>.log`

### 2. 常用模式
1. 所有容器日志：
```yaml
include_paths_glob_patterns:
  - /var/log/pods/**/*.log
```

2. 特定命名空间：
```yaml
include_paths_glob_patterns:
  - /var/log/pods/default_*.log
  - /var/log/pods/app_*.log
```

3. 特定 Pod：
```yaml
include_paths_glob_patterns:
  - /var/log/pods/*_nginx-*/*.log
```

### 3. 排除模式
```yaml
exclude_paths_glob_patterns:
  - /var/log/pods/kube-system_*.log
  - /var/log/pods/*_istio-proxy_*.log
```

## 与 file source 的区别

1. 元数据获取
- kubernetes_logs: 自动获取 Pod、容器等元数据
- file: 需要手动解析路径获取元数据

2. 路径格式
- kubernetes_logs: 使用 Kubernetes 标准日志路径
- file: 可以使用任意路径格式

3. 性能考虑
- kubernetes_logs: 针对 Kubernetes 环境优化
- file: 通用文件读取，需要额外处理

## 最佳实践

### 1. 路径选择
```yaml
sources:
  kubernetes_logs:
    type: kubernetes_logs
    include_paths_glob_patterns:
      # 主要应用日志
      - /var/log/pods/app-*/**/*.log
      # 系统组件日志（除了 kube-system）
      - /var/log/pods/monitoring-*/**/*.log
    exclude_paths_glob_patterns:
      # 排除系统日志
      - /var/log/pods/kube-system_*.log
      # 排除边车容器
      - /var/log/pods/**/*-sidecar/*.log
```

### 2. 性能优化
1. 避免过于宽泛的模式：
```yaml
# 不推荐
- /**/*.log

# 推荐
- /var/log/pods/**/*.log
```

2. 使用具体的路径：
```yaml
# 不推荐
- /var/log/pods/**/*

# 推荐
- /var/log/pods/**/*.log
```

3. 合理使用排除模式：
```yaml
exclude_paths_glob_patterns:
  - /var/log/pods/**/istio-proxy/*.log
  - /var/log/pods/**/linkerd-proxy/*.log
```

### 3. 监控建议
1. 监控文件数量：
   - 活跃文件数
   - 总文件数
   - 排除文件数

2. 监控读取性能：
   - 读取速率
   - 延迟情况
   - 错误率

3. 监控资源使用：
   - 文件句柄数
   - 内存使用
   - CPU 使用

## 故障排查

### 1. 常见问题
1. 日志未采集
   - 检查路径模式是否正确
   - 验证文件权限
   - 确认 Pod 标签选择器

2. 性能问题
   - 检查文件数量
   - 优化 glob 模式
   - 调整缓冲区大小

### 2. 调试技巧
1. 使用 debug 模式：
```yaml
sources:
  kubernetes_logs:
    type: kubernetes_logs
    log_level: debug
```

2. 验证路径模式：
```bash
find /var/log/pods -type f -name "*.log" | grep -v "kube-system"
```

## 注意事项
1. 路径权限
2. 文件轮转
3. 资源限制
4. 标签选择器配置
5. 多容器 Pod 处理 