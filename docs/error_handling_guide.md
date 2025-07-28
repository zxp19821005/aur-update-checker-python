# 错误处理系统使用指南

## 文件结构与功能

项目中的错误处理系统由以下几个文件组成：

1. **error_handler.py** - 原始错误处理模块
   - 提供基本的错误处理装饰器
   - 支持同步和异步函数的错误处理
   - 具有简单的重试机制

2. **enhanced_error_handler.py** - 增强版错误处理模块
   - 提供高级错误处理功能
   - 错误分类和严重程度评估
   - 智能重试策略（指数退避）
   - 错误统计和分析

3. **error_handler_integration.py** - 集成模块
   - 整合原始和增强版错误处理
   - 提供平滑过渡路径
   - 针对特定场景的专用装饰器（网络、I/O等）

4. **error_configuration.py** - 配置模块
   - 集中管理错误处理策略
   - 支持从配置文件加载设置
   - 提供全局错误处理配置

5. **error_handler_examples.py** - 示例模块
   - 演示各种错误处理用法
   - 提供最佳实践参考

## 使用方法

### 1. 在项目中引入错误处理

最简单的方法是从集成模块导入所需功能：

```python
# 推荐导入方式
from .modules.error_handler_integration import (
    network_request_error_handler,
    async_network_request_error_handler,
    file_io_error_handler
)
```

### 2. 对不同类型的操作应用错误处理

#### 网络请求

```python
@network_request_error_handler(
    retry_count=5,
    retry_delay=1.0
)
def fetch_data_from_api(url):
    # 网络请求代码...
    pass

# 异步版本
@async_network_request_error_handler(
    retry_count=5,
    retry_delay=1.0
)
async def fetch_data_async(url):
    # 异步网络请求代码...
    pass
```

#### 文件I/O操作

```python
@file_io_error_handler(
    retry_count=3,
    create_dirs=True  # 如果目录不存在，将自动创建
)
def save_data_to_file(file_path, data):
    # 文件写入代码...
    pass
```

### 3. 配置错误处理系统

在应用程序启动时初始化错误处理配置：

```python
from .modules.error_configuration import ErrorHandlerConfig

# 初始化错误处理配置
error_config = ErrorHandlerConfig(config=app_config, logger=logger)
```

### 4. 查看错误统计信息

```python
from .modules.error_handler_integration import get_error_statistics

# 获取错误统计信息
stats = get_error_statistics()
print(f"总错误数: {stats.get('total_errors', 0)}")
```

## 从原始错误处理迁移到增强版

项目中的错误处理文件组织方式允许逐步从原始错误处理迁移到增强版：

1. **阶段1**: 继续使用原始装饰器
   ```python
   from .modules.error_handler import error_handler, async_error_handler
   ```

2. **阶段2**: 使用专用装饰器，但保持原始行为
   ```python
   from .modules.error_handler_integration import network_request_error_handler
   ```

3. **阶段3**: 完全启用增强版功能
   ```python
   from .modules.error_handler_integration import use_enhanced_error_handling

   # 在应用初始化时
   use_enhanced_error_handling(enabled=True)
   ```

## 错误处理系统功能扩展

要进一步扩展错误处理系统，可以考虑：

1. 为现有检查器添加更多专用错误处理装饰器
2. 实现针对特定API的错误处理策略
3. 增加错误报告和警报功能
4. 与监控系统集成

## 常见问题解决

1. **如何处理特定类型的异常？**

   使用specific_exceptions参数：
   ```python
   @network_request_error_handler(
       specific_exceptions=[ConnectionError, TimeoutError]
   )
   ```

2. **如何禁用某些功能的错误处理？**

   可以设置retry_count=0来禁用重试机制：
   ```python
   @network_request_error_handler(retry_count=0)
   ```

3. **如何在UI中显示错误信息？**

   使用error_callback参数来注册一个回调函数：
   ```python
   def show_error_to_user(error_record):
       # 显示错误到UI

   @network_request_error_handler(error_callback=show_error_to_user)
   ```

## 错误处理最佳实践

1. 为网络请求设置适当的超时和重试次数
2. 对关键I/O操作应用错误处理和恢复机制
3. 根据错误类型定制重试策略
4. 监控和分析错误统计数据
5. 对用户友好地展示错误信息
