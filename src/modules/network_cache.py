# -*- coding: utf-8 -*-
"""
缓存模块，提供对网络请求的缓存支持
"""
import os
import json
import time
import hashlib
import threading
from datetime import datetime, timedelta
import sqlite3
from functools import lru_cache

class NetworkCacheModule:
    """网络请求缓存模块，为HTTP请求提供缓存功能"""

    def __init__(self, logger, config=None):
        """初始化缓存模块

        Args:
            logger: 日志记录器
            config: 配置对象（可选）
        """
        self.logger = logger
        self.config = config
        self.logger.debug("网络缓存模块初始化")

        # 缓存配置
        self.enable_cache = True
        self.default_ttl = 3600  # 默认缓存有效期（秒）
        self.smart_ttl_enabled = True  # 是否启用智能缓存策略

        if config:
            self.enable_cache = config.get('network_cache.enable', True)
            self.default_ttl = config.get('network_cache.default_ttl', 3600)
            self.smart_ttl_enabled = config.get('network_cache.smart_ttl_enabled', True)

        # 缓存目录
        self.cache_dir = None
        if config:
            self.cache_dir = config.get('network_cache.cache_dir')

        if not self.cache_dir:
            self.cache_dir = os.path.join(os.path.expanduser("~"),
                                        ".cache",
                                        "aur-update-checker-python",
                                        "http_cache")

        # 确保缓存目录存在
        os.makedirs(self.cache_dir, exist_ok=True)

        # 缓存数据库路径
        self.db_path = os.path.join(self.cache_dir, "cache.db")

        # 初始化缓存数据库
        self._init_cache_db()

        # 缓存锁
        self._cache_lock = threading.RLock()

        # 内存缓存 (URL->response mapping)
        self._memory_cache = {}

        # 启动清理过期缓存的线程
        self._start_cleanup_thread()

        self.logger.info(f"缓存模块初始化完成，缓存目录: {self.cache_dir}")

    def _init_cache_db(self):
        """初始化缓存数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS http_cache (
                    cache_key TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    method TEXT NOT NULL,
                    response_data BLOB,
                    response_headers TEXT,
                    status_code INTEGER,
                    created_at REAL,
                    expires_at REAL,
                    last_accessed REAL,
                    access_count INTEGER DEFAULT 0,
                    update_frequency REAL DEFAULT NULL
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_url ON http_cache(url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_expires ON http_cache(expires_at)")

            conn.commit()
            conn.close()
            self.logger.debug("缓存数据库初始化成功")
        except Exception as e:
            self.logger.error(f"初始化缓存数据库失败: {str(e)}")

    def _start_cleanup_thread(self):
        """启动清理过期缓存的线程"""
        def cleanup_task():
            while True:
                try:
                    # 每小时清理一次过期缓存
                    time.sleep(3600)
                    self.cleanup_expired()
                except Exception as e:
                    self.logger.error(f"清理过期缓存出错: {str(e)}")

        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
        self.logger.debug("缓存清理线程已启动")

    def _generate_cache_key(self, method, url, params=None, data=None, json_data=None):
        """生成缓存键

        Args:
            method: HTTP方法
            url: URL
            params: 查询参数
            data: 表单数据
            json_data: JSON数据

        Returns:
            str: 缓存键
        """
        key_parts = [method.upper(), url]

        if params:
            if isinstance(params, dict):
                # 对字典进行排序，确保相同内容生成相同的键
                key_parts.append(str(sorted(params.items())))
            else:
                key_parts.append(str(params))

        if data:
            key_parts.append(str(data))

        if json_data:
            if isinstance(json_data, dict):
                key_parts.append(json.dumps(json_data, sort_keys=True))
            else:
                key_parts.append(str(json_data))

        # 使用MD5生成缓存键
        key_string = "".join(key_parts)
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()

    def get(self, method, url, params=None, data=None, json_data=None):
        """从缓存获取响应

        Args:
            method: HTTP方法
            url: URL
            params: 查询参数
            data: 表单数据
            json_data: JSON数据

        Returns:
            dict: 缓存的响应，如果不存在则返回None
        """
        if not self.enable_cache or method.upper() not in ['GET', 'HEAD']:
            return None

        cache_key = self._generate_cache_key(method, url, params, data, json_data)

        # 首先检查内存缓存
        with self._cache_lock:
            if cache_key in self._memory_cache:
                cache_item = self._memory_cache[cache_key]
                if time.time() < cache_item.get('expires_at', 0):
                    self.logger.debug(f"从内存缓存获取: {url}")
                    # 更新访问时间和计数
                    self._update_access_stats(cache_key)
                    return cache_item['response']

        # 检查数据库缓存
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT response_data, response_headers, status_code, expires_at, created_at FROM http_cache "
                "WHERE cache_key=? AND expires_at > ?", 
                (cache_key, time.time())
            )

            row = cursor.fetchone()
            if row:
                response_data, response_headers, status_code, expires_at, created_at = row

                # 解析数据
                if response_data:
                    try:
                        response_data = json.loads(response_data)
                    except:
                        pass

                if response_headers:
                    response_headers = json.loads(response_headers)

                response = {
                    "data": response_data,
                    "headers": response_headers,
                    "status": status_code,
                    "from_cache": True,
                    "cache_age": time.time() - created_at,
                    "cache_expires": expires_at - time.time()
                }

                # 更新访问时间和计数
                self._update_access_stats(cache_key)

                # 添加到内存缓存
                with self._cache_lock:
                    self._memory_cache[cache_key] = {
                        'response': response,
                        'expires_at': expires_at
                    }

                self.logger.debug(f"从数据库缓存获取: {url}")
                conn.close()
                return response

            conn.close()
            return None

        except Exception as e:
            self.logger.error(f"从缓存获取数据失败: {str(e)}")
            return None

    def set(self, method, url, response, params=None, data=None, json_data=None, ttl=None):
        """将响应存入缓存

        Args:
            method: HTTP方法
            url: URL
            response: 响应对象
            params: 查询参数
            data: 表单数据
            json_data: JSON数据
            ttl: 缓存有效期（秒），如果为None则使用默认值

        Returns:
            bool: 如果操作成功则返回True
        """
        if not self.enable_cache or method.upper() not in ['GET', 'HEAD']:
            return False

        if not response or not response.get('success', False):
            return False

        try:
            cache_key = self._generate_cache_key(method, url, params, data, json_data)

            # 计算过期时间
            ttl = ttl or self.default_ttl

            # 智能缓存策略：根据上次更新时间动态调整TTL
            if self.smart_ttl_enabled:
                ttl = self._calculate_smart_ttl(url, ttl)

            current_time = time.time()
            expires_at = current_time + ttl

            # 准备要缓存的数据
            response_data = response.get('data')
            response_headers = response.get('headers')
            status_code = response.get('status')

            # 序列化数据
            if isinstance(response_data, (dict, list)):
                response_data = json.dumps(response_data)
            else:
                response_data = str(response_data)

            if response_headers:
                response_headers = json.dumps(response_headers)

            # 存入数据库
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO http_cache
                (cache_key, url, method, response_data, response_headers, status_code, created_at, expires_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (cache_key, url, method.upper(), response_data, response_headers, status_code, current_time, expires_at, current_time)
            )

            conn.commit()
            conn.close()

            # 存入内存缓存
            response_copy = response.copy()
            response_copy['from_cache'] = True
            response_copy['cache_age'] = 0
            response_copy['cache_expires'] = ttl

            with self._cache_lock:
                self._memory_cache[cache_key] = {
                    'response': response_copy,
                    'expires_at': expires_at
                }

            self.logger.debug(f"已缓存URL: {url}，有效期: {ttl}秒")
            return True

        except Exception as e:
            self.logger.error(f"缓存响应失败: {str(e)}")
            return False

    def _update_access_stats(self, cache_key):
        """更新缓存项的访问统计信息

        Args:
            cache_key: 缓存键
        """
        try:
            current_time = time.time()

            # 更新数据库中的访问统计
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取当前值
            cursor.execute(
                "SELECT last_accessed, access_count FROM http_cache WHERE cache_key=?", 
                (cache_key,)
            )

            row = cursor.fetchone()
            if row:
                last_accessed, access_count = row

                # 计算访问频率
                if last_accessed:
                    time_diff = current_time - last_accessed
                    if time_diff > 0:
                        # 更新访问频率（指数移动平均）
                        cursor.execute(
                            """
                            UPDATE http_cache 
                            SET last_accessed=?, access_count=?, 
                            update_frequency = CASE 
                                WHEN update_frequency IS NULL THEN ? 
                                ELSE update_frequency * 0.7 + ? * 0.3 
                            END 
                            WHERE cache_key=?
                            """,
                            (current_time, access_count + 1, 1/time_diff, 1/time_diff, cache_key)
                        )
                else:
                    # 首次访问
                    cursor.execute(
                        "UPDATE http_cache SET last_accessed=?, access_count=? WHERE cache_key=?",
                        (current_time, 1, cache_key)
                    )

            conn.commit()
            conn.close()

        except Exception as e:
            self.logger.error(f"更新缓存访问统计失败: {str(e)}")

    def _calculate_smart_ttl(self, url, default_ttl):
        """计算智能缓存TTL

        根据历史访问频率和更新频率动态调整缓存有效期

        Args:
            url: URL
            default_ttl: 默认TTL

        Returns:
            int: 计算后的TTL
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 查询该URL最近的更新频率
            cursor.execute(
                "SELECT update_frequency, access_count FROM http_cache WHERE url=? ORDER BY last_accessed DESC LIMIT 1", 
                (url,)
            )

            row = cursor.fetchone()
            conn.close()

            if not row or not row[0]:
                return default_ttl

            update_frequency, access_count = row

            # 基于更新频率调整TTL
            # 如果更新频率高（短时间内多次更新），则缩短TTL
            # 如果更新频率低（长时间未更新），则延长TTL
            if update_frequency > 0:
                # 将更新频率转换为小时
                hours_between_updates = 1 / (update_frequency * 3600)

                if hours_between_updates < 1:  # 不到1小时更新一次
                    new_ttl = max(300, default_ttl / 4)  # 最少5分钟，默认的1/4
                elif hours_between_updates < 24:  # 不到1天更新一次
                    new_ttl = default_ttl  # 使用默认TTL
                else:  # 超过1天更新一次
                    # 最多延长到3倍默认TTL，但不超过1周
                    new_ttl = min(default_ttl * 3, 7 * 24 * 3600)

                # 访问频率调整：经常访问的内容适当延长缓存时间
                if access_count and access_count > 10:
                    new_ttl = min(new_ttl * 1.5, 7 * 24 * 3600)  # 最多1周

                self.logger.debug(f"智能TTL计算: URL={url}, 更新频率={hours_between_updates:.2f}小时/次, TTL={new_ttl:.0f}秒")
                return int(new_ttl)

            return default_ttl

        except Exception as e:
            self.logger.error(f"计算智能TTL失败: {str(e)}")
            return default_ttl

    def invalidate(self, url=None, prefix=None):
        """使指定URL或URL前缀的缓存无效

        Args:
            url: 指定的URL（可选）
            prefix: URL前缀（可选）

        Returns:
            int: 清除的缓存项数量
        """
        if not self.enable_cache:
            return 0

        try:
            count = 0
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 清除内存缓存
            with self._cache_lock:
                if url:
                    # 找出所有匹配的缓存键
                    cursor.execute("SELECT cache_key FROM http_cache WHERE url=?", (url,))
                    keys = [row[0] for row in cursor.fetchall()]

                    # 从内存缓存中删除
                    for key in keys:
                        if key in self._memory_cache:
                            del self._memory_cache[key]

                    count = len(keys)
                elif prefix:
                    # 找出所有匹配前缀的缓存键
                    cursor.execute("SELECT cache_key FROM http_cache WHERE url LIKE ?", (prefix + '%',))
                    keys = [row[0] for row in cursor.fetchall()]

                    # 从内存缓存中删除
                    for key in keys:
                        if key in self._memory_cache:
                            del self._memory_cache[key]

                    count = len(keys)
                else:
                    # 清除所有内存缓存
                    count = len(self._memory_cache)
                    self._memory_cache.clear()

            # 清除数据库缓存
            if url:
                cursor.execute("DELETE FROM http_cache WHERE url=?", (url,))
            elif prefix:
                cursor.execute("DELETE FROM http_cache WHERE url LIKE ?", (prefix + '%',))
            else:
                cursor.execute("DELETE FROM http_cache")

            conn.commit()
            conn.close()

            self.logger.info(f"已清除{count}个缓存项")
            return count

        except Exception as e:
            self.logger.error(f"清除缓存失败: {str(e)}")
            return 0

    def cleanup_expired(self):
        """清理过期的缓存

        Returns:
            int: 清理的缓存项数量
        """
        if not self.enable_cache:
            return 0

        try:
            current_time = time.time()

            # 清除内存中的过期缓存
            expired_keys = []
            with self._cache_lock:
                for key, item in self._memory_cache.items():
                    if item.get('expires_at', 0) < current_time:
                        expired_keys.append(key)

                for key in expired_keys:
                    del self._memory_cache[key]

            # 清除数据库中的过期缓存
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM http_cache WHERE expires_at < ?", (current_time,))
            db_count = cursor.rowcount

            conn.commit()
            conn.close()

            total_count = len(expired_keys) + db_count
            if total_count > 0:
                self.logger.info(f"已清理{total_count}个过期缓存项 (内存: {len(expired_keys)}, 数据库: {db_count})")

            return total_count

        except Exception as e:
            self.logger.error(f"清理过期缓存失败: {str(e)}")
            return 0

    def get_stats(self):
        """获取缓存统计信息

        Returns:
            dict: 包含缓存统计信息的字典
        """
        stats = {
            "enabled": self.enable_cache,
            "memory_cache_count": len(self._memory_cache),
            "default_ttl": self.default_ttl,
            "smart_ttl_enabled": self.smart_ttl_enabled,
            "cache_dir": self.cache_dir,
            "database": self.db_path,
        }

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 总缓存项数
            cursor.execute("SELECT COUNT(*) FROM http_cache")
            stats["total_cache_items"] = cursor.fetchone()[0]

            # 活跃缓存项数
            current_time = time.time()
            cursor.execute("SELECT COUNT(*) FROM http_cache WHERE expires_at > ?", (current_time,))
            stats["active_cache_items"] = cursor.fetchone()[0]

            # 过期缓存项数
            stats["expired_cache_items"] = stats["total_cache_items"] - stats["active_cache_items"]

            # 缓存命中率
            cursor.execute("SELECT SUM(access_count) FROM http_cache")
            total_hits = cursor.fetchone()[0] or 0
            stats["cache_hits"] = total_hits

            # 缓存大小（字节）
            cursor.execute("SELECT SUM(length(response_data)) FROM http_cache")
            stats["cache_size_bytes"] = cursor.fetchone()[0] or 0
            stats["cache_size_mb"] = stats["cache_size_bytes"] / (1024 * 1024)

            conn.close()

        except Exception as e:
            self.logger.error(f"获取缓存统计信息失败: {str(e)}")

        return stats

    def clear_url(self, url):
        """清除特定URL的缓存

        Args:
            url: URL地址

        Returns:
            bool: 如果操作成功则返回True
        """
        if not self.enable_cache:
            return False

        return self.invalidate(url=url) > 0

    def clear_all(self):
        """清除所有缓存

        Returns:
            bool: 如果操作成功则返回True
        """
        if not self.enable_cache:
            return False

        return self.invalidate() > 0
