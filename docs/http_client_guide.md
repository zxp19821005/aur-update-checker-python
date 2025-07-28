# HTTP 客户端使用指南

## 概述

为了优化项目中的异步 HTTP 请求性能，我们实现了基于 `aiohttp.ClientSession` 的连接池功能，通过 `HttpClient` 类提供统一的接口。
这个优化可以显著减少频繁创建和销毁 HTTP 连接的开销，提高请求效率和应用性能。

## 主要优化

1. **连接池管理**：使用 `aiohttp.TCPConnector` 管理连接池，避免频繁创建连接
2. **请求限流**：通过信号量控制并发请求数，防止资源耗尽
3. **自动重试**：对特定错误和状态码进行自动重试，提高可靠性
4. **统一错误处理**：规范化错误处理和响应格式
5. **懒加载与复用**：单例模式确保连接池在整个应用生命周期中被复用

## 使用方法

### 1. 获取 HttpClient 实例

```python
from src.modules.http_client import HttpClient
from src.modules.dependency_container import container

# 方法1：从容器获取（推荐）
http_client = container.get("http_client")

# 方法2：直接获取单例（如果容器不可用）
http_client = HttpClient.get_instance(logger)
```

### 2. 发送 GET 请求

```python
# 获取 JSON 响应
result = await http_client.get(url, params={"key": "value"})
if result["success"]:
    data = result["data"]
    print(f"状态码: {result['status']}")
else:
    print(f"请求失败: {result['error']}")

# 简化方法，直接获取 JSON 数据
data = await http_client.get_json(url)

# 获取纯文本响应
text = await http_client.get_text(url)
```

### 3. 发送 POST 请求

```python
# 发送表单数据
result = await http_client.post(url, data={"key": "value"})

# 发送 JSON 数据
result = await http_client.post(url, json={"key": "value"})
```

### 4. 下载文件

```python
# 基本下载
success = await http_client.download_file(url, "path/to/save.file")

# 带进度回调的下载
async def progress(downloaded, total):
    percent = (downloaded / total) * 100 if total > 0 else 0
    print(f"下载进度: {percent:.2f}%")

success = await http_client.download_file(url, "path/to/save.file", progress_callback=progress)
```

### 5. 自定义配置

```python
# 配置 HTTP 客户端
http_client.configure(
    conn_limit=50,                # 总连接数限制
    conn_limit_per_host=10,       # 每个主机的连接数限制
    timeout=60,                   # 请求超时时间（秒）
    headers={"User-Agent": "..."}  # 自定义请求头
)
```

## 在检查器中使用

所有继承自 `ApiChecker` 和 `WebChecker` 的检查器类都已经被更新，可以自动使用 `HttpClient` 提供的连接池功能。例如：

```python
class MyApiChecker(ApiChecker):
    async def check_version(self, package_name, url, **kwargs):
        endpoint = f"api/{package_name}"
        data = await self._make_api_request(endpoint)
        # 处理响应...
```

## 高级配置

可以在项目配置文件中添加以下设置来自定义 HTTP 客户端的行为：

```yaml
upstream:
  timeout: 30                      # 请求超时时间（秒）
  user_agent: "Mozilla/5.0 ..."     # 用户代理字符串
  conn_limit: 100                  # 总连接数限制
  conn_limit_per_host: 10          # 每个主机的连接数限制
```

## 性能提示

1. 避免在短期内创建多个 `HttpClient` 实例，应尽量使用单例
2. 对于需要长时间运行的应用，可以考虑定期重新创建连接池（例如每天一次）
3. 对于批量请求，可以使用 `asyncio.gather` 结合 `HttpClient` 实现高效的并行请求

## 资源清理

`HttpClient` 在应用程序结束时会自动关闭连接池。如果需要手动关闭，可以：

```python
await http_client.close()
```

这个优化显著提高了项目中 HTTP 请求的效率，特别是在需要频繁检查多个上游源的情况下。
