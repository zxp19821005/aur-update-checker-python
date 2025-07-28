# 依赖注入使用指南

## 背景

为了优化项目架构，减少组件间的紧耦合，我们引入了依赖注入(DI)机制。通过依赖注入，可以实现：

1. 更松散的组件耦合
2. 更容易进行单元测试
3. 代码更具可维护性
4. 更灵活的依赖管理

## 依赖注入容器

我们实现了一个轻量级但功能强大的依赖注入容器：`DependencyContainer`。它支持以下功能：

- 服务注册与获取
- 工厂方法创建服务
- 单例服务（懒加载）
- 自动依赖解析
- 装饰器注入

## 服务提供者

为了集中管理核心服务的注册，我们创建了`ServiceProvider`类，它负责初始化和注册所有核心服务。

## 使用方法

### 1. 获取已注册的服务

```python
from src.modules.dependency_container import container

# 获取日志服务
logger = container.get("logger")
logger.info("使用依赖注入获取的日志服务")

# 获取配置服务
config = container.get("config")
```

### 2. 注册新服务

```python
# 直接注册实例
my_service = MyService()
container.register("my_service", my_service)

# 注册工厂方法（单例，懒加载）
def create_service(container):
    logger = container.get("logger")
    return ComplexService(logger)

container.register_factory("complex_service", create_service)

# 注册类（自动解析构造函数依赖）
container.register_class("user_service", UserService)
```

### 3. 在类中使用依赖注入

如示例类`DICheckerExample`所示，有两种使用依赖注入的方式：

#### 方式1：构造函数中获取依赖

```python
def __init__(self, service_container=None):
    # 使用提供的容器或全局容器
    self.container = service_container or container

    # 从容器获取依赖
    self.logger = self.container.get("logger")
    self.config = self.container.get("config") if self.container.has("config") else None

    # 调用父类构造函数
    super().__init__(self.logger, self.config)
```

#### 方式2：属性懒加载

```python
@property
def db(self):
    """数据库属性，懒加载示例"""
    if self._db is None and self.container.has("db"):
        self._db = self.container.get("db")
    return self._db
```

#### 方式3：装饰器自动注入

```python
@container.inject
def process_with_injection(self, package_name, result_processor=None):
    # result_processor会自动从容器中注入（如果未提供）
    if result_processor:
        return result_processor.process_result({"name": package_name})
    return {"name": package_name}
```

## 最佳实践

1. **核心服务通过ServiceProvider注册**：所有核心系统服务应当通过ServiceProvider注册，这样可以集中管理依赖关系。

2. **避免循环依赖**：虽然容器能检测循环依赖，但应避免创建循环依赖关系。

3. **使用懒加载**：对于重量级服务，使用懒加载模式，只在实际需要时创建。

4. **为测试注入Mock**：测试时可以创建新的容器并注入模拟对象。

```python
def test_my_service():
    test_container = DependencyContainer()
    test_container.register("logger", MockLogger())

    service = MyService(test_container)
    # 进行测试...
```

## 使用依赖注入的优势

- **代码更干净**：消除了大量的依赖传递参数
- **更容易替换实现**：只需在容器中注册不同的实现
- **更好的模块化**：每个组件只依赖于抽象接口，不依赖具体实现
- **更容易测试**：可以轻松注入模拟对象

## 示例

查看`DICheckerExample`类，了解如何在实际代码中使用依赖注入。
