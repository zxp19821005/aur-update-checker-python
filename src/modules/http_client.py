# -*- coding: utf-8 -*-
"""
HTTP客户端模块，提供异步HTTP请求功能，使用连接池管理连接
"""
import asyncio
import aiohttp
import ssl
import time
from typing import Dict, Any, Optional, Union, List
from contextlib import asynccontextmanager
from functools import wraps

class HttpClient:
    """HTTP客户端类，封装aiohttp.ClientSession，提供连接池功能"""

    _instance = None  # 单例实例
    _session = None   # 共享的ClientSession实例

    @classmethod
    def get_instance(cls, logger=None):
        """获取HttpClient单例实例

        Args:
            logger: 日志记录器（可选）

        Returns:
            HttpClient: 单例实例
        """
        if cls._instance is None:
            cls._instance = cls(logger)
        return cls._instance

    def __init__(self, logger=None):
        """初始化HTTP客户端

        Args:
            logger: 日志记录器（可选）
        """
        self.logger = logger
        self._default_timeout = 30
        self._default_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self._concurrent_requests = 0
        self._max_concurrent_requests = 100
        self._request_semaphore = asyncio.Semaphore(self._max_concurrent_requests)

        # 连接池配置
        self._conn_limit = 100  # 最大连接数
        self._conn_limit_per_host = 10  # 每个主机的最大连接数

        # 缓存相关属性
        self._cache_module = None  # 将在set_cache_module中设置
        self._enable_cache = True
        self._default_cache_ttl = 3600  # 默认缓存时间 1小时

    def set_cache_module(self, cache_module):
        """设置缓存模块

        Args:
            cache_module: 缓存模块实例
        """
        self._cache_module = cache_module
        if self.logger:
            self.logger.debug("HTTP客户端已设置缓存模块")

    @property
    def session(self) -> aiohttp.ClientSession:
        """获取或创建共享的ClientSession实例

        Returns:
            aiohttp.ClientSession: 客户端会话
        """
        if self._session is None or self._session.closed:
            # 使用TCPConnector配置连接池
            connector = aiohttp.TCPConnector(
                limit=self._conn_limit,
                limit_per_host=self._conn_limit_per_host,
                ssl=False,  # 禁用SSL证书验证，在生产环境中应当根据需要启用
                use_dns_cache=True,
                ttl_dns_cache=300,  # DNS缓存时间，秒
            )

            # 创建共享会话
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers=self._default_headers,
                timeout=aiohttp.ClientTimeout(total=self._default_timeout)
            )

            if self.logger:
                self.logger.debug(f"创建新的HTTP会话，连接池配置: 总连接数={self._conn_limit}, 每主机连接数={self._conn_limit_per_host}")

        return self._session

    def configure(self, conn_limit=None, conn_limit_per_host=None, timeout=None, headers=None, 
                  enable_cache=None, default_cache_ttl=None):
        """配置HTTP客户端参数

        Args:
            conn_limit: 总连接数限制
            conn_limit_per_host: 每个主机的连接数限制
            timeout: 请求超时时间（秒）
            headers: 默认请求头
            enable_cache: 是否启用缓存
            default_cache_ttl: 默认缓存有效期（秒）
        """
        if conn_limit is not None:
            self._conn_limit = conn_limit

        if conn_limit_per_host is not None:
            self._conn_limit_per_host = conn_limit_per_host

        if timeout is not None:
            self._default_timeout = timeout

        if headers is not None:
            self._default_headers.update(headers)

        if enable_cache is not None:
            self._enable_cache = enable_cache

        if default_cache_ttl is not None:
            self._default_cache_ttl = default_cache_ttl

        # 配置更改后，需要关闭并重新创建会话
        self.close()

    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            if self.logger:
                self.logger.debug("关闭HTTP会话")
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口，关闭会话"""
        await self.close()

    @asynccontextmanager
    async def _request_context(self):
        """请求上下文管理器，跟踪并限制并发请求数"""
        # 获取请求信号量，限制并发请求数
        async with self._request_semaphore:
            self._concurrent_requests += 1
            if self.logger and self._concurrent_requests % 10 == 0:  # 每10个请求记录一次
                self.logger.debug(f"当前并发请求数: {self._concurrent_requests}")

            try:
                yield
            finally:
                self._concurrent_requests -= 1

    async def get(self, url: str, params=None, headers=None, timeout=None, 
                  use_cache=True, cache_ttl=None, **kwargs) -> Dict[str, Any]:
        """发送GET请求

        Args:
            url: 请求URL
            params: 查询参数
            headers: 请求头
            timeout: 超时时间
            use_cache: 是否使用缓存
            cache_ttl: 缓存时间（秒）
            **kwargs: 传递给ClientSession.get的其他参数

        Returns:
            Dict[str, Any]: 包含响应信息的字典
        """
        return await self._request('get', url, params=params, headers=headers, timeout=timeout, 
                                   use_cache=use_cache, cache_ttl=cache_ttl, **kwargs)

    async def post(self, url: str, data=None, json=None, headers=None, timeout=None, 
                   use_cache=False, cache_ttl=None, **kwargs) -> Dict[str, Any]:
        """发送POST请求

        Args:
            url: 请求URL
            data: 表单数据
            json: JSON数据
            headers: 请求头
            timeout: 超时时间
            use_cache: 是否使用缓存
            cache_ttl: 缓存时间（秒）
            **kwargs: 传递给ClientSession.post的其他参数

        Returns:
            Dict[str, Any]: 包含响应信息的字典
        """
        return await self._request('post', url, data=data, json=json, headers=headers, timeout=timeout, 
                                   use_cache=use_cache, cache_ttl=cache_ttl, **kwargs)

    async def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """执行HTTP请求

        Args:
            method: HTTP方法
            url: 请求URL
            **kwargs: 请求参数

        Returns:
            Dict[str, Any]: 包含响应信息的字典
        """
        # 缓存相关参数
        use_cache = kwargs.pop('use_cache', True)
        cache_ttl = kwargs.pop('cache_ttl', self._default_cache_ttl)

        # 检查是否可以从缓存获取
        cached_response = None
        if self._enable_cache and use_cache and self._cache_module and method.lower() in ['get', 'head']:
            params = kwargs.get('params')
            data = kwargs.get('data')
            json_data = kwargs.get('json')
            cached_response = self._cache_module.get(method, url, params, data, json_data)

            if cached_response:
                if self.logger:
                    self.logger.debug(f"从缓存获取响应: {url}")
                return cached_response

        # 合并请求头
        headers = kwargs.pop('headers', {}) or {}
        headers = {**self._default_headers, **headers}

        # 设置超时
        timeout = kwargs.pop('timeout', self._default_timeout)
        if isinstance(timeout, (int, float)):
            timeout = aiohttp.ClientTimeout(total=timeout)

        # 准备结果
        result = {
            "url": url,
            "success": False,
            "status": None,
            "data": None,
            "headers": None,
            "error": None
        }

        # 重试配置
        max_retries = kwargs.pop('retries', 3)
        retry_delay = kwargs.pop('retry_delay', 1)  # 秒

        async with self._request_context():
            for attempt in range(1, max_retries + 1):
                try:
                    if self.logger and attempt > 1:
                        self.logger.debug(f"重试请求 {url}，第 {attempt} 次尝试")

                    # 记录请求开始时间
                    start_time = time.time()

                    # 执行请求
                    async with getattr(self.session, method)(url, headers=headers, timeout=timeout, **kwargs) as response:
                        result["status"] = response.status
                        result["headers"] = dict(response.headers)

                        # 检查状态码
                        if 200 <= response.status < 300:
                            # 根据内容类型处理响应
                            content_type = response.headers.get('Content-Type', '')
                            if 'application/json' in content_type:
                                result["data"] = await response.json()
                            else:
                                result["data"] = await response.text()

                            result["success"] = True

                            # 计算请求时间
                            request_time = time.time() - start_time
                            result["request_time"] = request_time

                            # 缓存结果
                            if self._enable_cache and use_cache and self._cache_module and method.lower() in ['get', 'head']:
                                self._cache_module.set(method, url, result, 
                                                      kwargs.get('params'), kwargs.get('data'), kwargs.get('json'), 
                                                      cache_ttl)

                            return result
                        else:
                            error_text = await response.text()
                            result["error"] = f"HTTP错误: {response.status}, {error_text}"

                            # 对某些状态码进行重试
                            if response.status in (429, 500, 502, 503, 504) and attempt < max_retries:
                                retry_after = int(response.headers.get('Retry-After', retry_delay))
                                if self.logger:
                                    self.logger.debug(f"请求失败，将在 {retry_after} 秒后重试: {result['error']}")
                                await asyncio.sleep(retry_after)
                                continue

                            return result

                except asyncio.TimeoutError:
                    result["error"] = f"请求超时 ({timeout}秒)"
                    if attempt < max_retries:
                        if self.logger:
                            self.logger.debug(f"请求超时，将在 {retry_delay} 秒后重试")
                        await asyncio.sleep(retry_delay)
                        continue

                except aiohttp.ClientError as e:
                    result["error"] = f"HTTP客户端错误: {str(e)}"
                    if attempt < max_retries:
                        if self.logger:
                            self.logger.debug(f"请求出错，将在 {retry_delay} 秒后重试: {str(e)}")
                        await asyncio.sleep(retry_delay)
                        continue

                except Exception as e:
                    result["error"] = f"未知错误: {str(e)}"
                    if self.logger:
                        self.logger.error(f"请求 {url} 时发生异常: {str(e)}")
                    break

        if self.logger and not result["success"]:
            self.logger.warning(f"请求 {url} 失败: {result['error']}")

        return result

    async def get_json(self, url: str, params=None, use_cache=True, cache_ttl=None, **kwargs) -> Dict[str, Any]:
        """发送GET请求并返回JSON响应

        Args:
            url: 请求URL
            params: 查询参数
            use_cache: 是否使用缓存
            cache_ttl: 缓存时间（秒）
            **kwargs: 其他参数

        Returns:
            Dict[str, Any]: JSON响应
        """
        result = await self.get(url, params=params, use_cache=use_cache, cache_ttl=cache_ttl, **kwargs)
        return result["data"] if result["success"] else None

    async def get_text(self, url: str, params=None, use_cache=True, cache_ttl=None, **kwargs) -> str:
        """发送GET请求并返回文本响应

        Args:
            url: 请求URL
            params: 查询参数
            use_cache: 是否使用缓存
            cache_ttl: 缓存时间（秒）
            **kwargs: 其他参数

        Returns:
            str: 文本响应
        """
        result = await self.get(url, params=params, use_cache=use_cache, cache_ttl=cache_ttl, **kwargs)
        return result["data"] if result["success"] else None

    async def get_status(self, url: str, use_cache=True, cache_ttl=None, **kwargs) -> int:
        """发送HEAD请求并返回状态码

        Args:
            url: 请求URL
            use_cache: 是否使用缓存
            cache_ttl: 缓存时间（秒）
            **kwargs: 其他参数

        Returns:
            int: HTTP状态码
        """
        result = await self._request('head', url, use_cache=use_cache, cache_ttl=cache_ttl, **kwargs)
        return result["status"] if result["success"] else None

    def clear_cache(self, url=None):
        """清除缓存

        Args:
            url: 要清除的URL缓存，如果为None则清除所有缓存

        Returns:
            bool: 如果操作成功则返回True
        """
        if self._cache_module:
            if url:
                return self._cache_module.clear_url(url)
            else:
                return self._cache_module.clear_all()
        return False

    async def download_file(self, url: str, file_path: str, progress_callback=None, chunk_size=1024*64) -> bool:
        """下载文件

        Args:
            url: 文件URL
            file_path: 保存路径
            progress_callback: 进度回调函数，接收(下载字节数, 总字节数)
            chunk_size: 块大小

        Returns:
            bool: 是否成功
        """
        if self.logger:
            self.logger.debug(f"开始下载文件: {url} -> {file_path}")

        async with self._request_context():
            try:
                async with self.session.get(url, timeout=None) as response:
                    if response.status != 200:
                        if self.logger:
                            self.logger.error(f"下载失败，状态码: {response.status}")
                        return False

                    # 获取文件大小
                    total_size = int(response.headers.get('Content-Length', 0))
                    downloaded = 0

                    # 写入文件
                    with open(file_path, 'wb') as fd:
                        async for chunk in response.content.iter_chunked(chunk_size):
                            fd.write(chunk)
                            downloaded += len(chunk)

                            # 报告进度
                            if progress_callback:
                                await progress_callback(downloaded, total_size)

                if self.logger:
                    self.logger.debug(f"文件下载完成: {file_path}")
                return True

            except Exception as e:
                if self.logger:
                    self.logger.error(f"下载文件时出错: {str(e)}")
                return False

# 创建全局HTTP客户端实例
http_client = HttpClient()

def with_http_client(func):
    """装饰器，为函数提供HTTP客户端实例

    使用方法:
    @with_http_client
    async def my_function(http_client, ...):
        # 使用http_client
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 如果函数没有接收http_client参数，直接调用
        if 'http_client' in kwargs:
            return await func(*args, **kwargs)

        # 否则，注入http_client实例
        return await func(*args, http_client=http_client, **kwargs)
    return wrapper
