# -*- coding: utf-8 -*-
import os
import sqlite3
import json
import threading
import time
from datetime import datetime
import shutil
from functools import lru_cache

class DatabaseModule:
    """数据库模块，负责数据库操作和软件包数据管理"""

    def __init__(self, logger, config):
        """初始化数据库模块

        Args:
            logger: 日志模块实例
            config: 配置模块实例
        """
        self.logger = logger
        self.config = config
        self.logger.debug("数据库模块初始化")

        # 初始化线程本地存储
        self._thread_local = threading.local()
        
        # 初始化连接池
        self._connection_pool = []
        self._pool_lock = threading.RLock()
        self._max_pool_size = self.config.get('database.max_pool_size', 5)
        self._connection_timeout = self.config.get('database.connection_timeout', 30)  # 连接超时时间（秒）
        
        # 查询缓存设置
        self._enable_cache = self.config.get('database.enable_cache', True)
        self._cache_ttl = self.config.get('database.cache_ttl', 60)  # 缓存有效期（秒）
        self._query_cache = {}  # 查询缓存
        self._cache_lock = threading.RLock()

        # 获取数据库文件路径
        self.db_file_path = self.config.get('database.path', 
                                           os.path.join(os.path.expanduser("~"), 
                                                      ".config", 
                                                      "aur-update-checker-python", 
                                                      "packages.db"))

        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.db_file_path), exist_ok=True)

        # 初始化数据库结构 - 只在模块初始化时调用一次
        self.initialize_database()
        
        # 启动缓存清理线程
        if self._enable_cache:
            self._start_cache_cleanup_thread()

    def _start_cache_cleanup_thread(self):
        """启动缓存清理线程"""
        def cleanup_cache():
            while True:
                time.sleep(self._cache_ttl)
                try:
                    self._cleanup_expired_cache()
                except Exception as e:
                    self.logger.error(f"清理缓存时出错: {str(e)}")
                    
        cleanup_thread = threading.Thread(target=cleanup_cache, daemon=True)
        cleanup_thread.start()
        self.logger.debug("缓存清理线程已启动")
        
    def _cleanup_expired_cache(self):
        """清理过期的缓存项"""
        current_time = time.time()
        with self._cache_lock:
            expired_keys = []
            for key, (value, timestamp) in self._query_cache.items():
                if current_time - timestamp > self._cache_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._query_cache[key]
                
            if expired_keys:
                self.logger.debug(f"已清理 {len(expired_keys)} 个过期缓存项")

    def get_connection(self):
        """获取数据库连接，优先从连接池获取

        Returns:
            sqlite3.Connection: 数据库连接
        """
        # 首先检查当前线程是否已有连接
        if hasattr(self._thread_local, "connection"):
            return self._thread_local.connection
            
        # 尝试从连接池获取连接
        with self._pool_lock:
            if self._connection_pool:
                conn = self._connection_pool.pop()
                self.logger.debug(f"从连接池获取连接，当前池大小: {len(self._connection_pool)}")
                self._thread_local.connection = conn
                return conn
                
        # 如果没有可用连接，创建新连接
        try:
            conn = sqlite3.connect(self.db_file_path)
            conn.row_factory = sqlite3.Row
            self._thread_local.connection = conn
            self.logger.debug(f"为线程 {threading.current_thread().name} 创建了新的数据库连接")
            
            # 优化：启用WAL模式提高并发性能
            conn.execute("PRAGMA journal_mode=WAL")
            # 优化：设置同步模式为NORMAL，提高写入性能
            conn.execute("PRAGMA synchronous=NORMAL")
            # 优化：启用内存映射
            conn.execute("PRAGMA mmap_size=67108864")  # 64MB
            
            return conn
        except Exception as e:
            self.logger.error(f"创建数据库连接失败: {str(e)}")
            raise e

    def release_connection(self, conn=None):
        """释放连接到连接池

        Args:
            conn: 要释放的连接，如果为None则释放当前线程的连接
        """
        if conn is None and hasattr(self._thread_local, "connection"):
            conn = self._thread_local.connection
            delattr(self._thread_local, "connection")
            
        if conn:
            with self._pool_lock:
                # 如果连接池未满，将连接放回池中
                if len(self._connection_pool) < self._max_pool_size:
                    self._connection_pool.append(conn)
                    self.logger.debug(f"连接已放回连接池，当前池大小: {len(self._connection_pool)}")
                else:
                    # 如果连接池已满，关闭连接
                    conn.close()
                    self.logger.debug("连接池已满，连接已关闭")

    def close(self):
        """关闭当前线程的数据库连接

        Returns:
            bool: 如果操作成功则返回True
        """
        if hasattr(self._thread_local, "connection"):
            try:
                self.release_connection()
                self.logger.debug(f"关闭线程 {threading.current_thread().name} 的数据库连接")
                return True
            except Exception as e:
                self.logger.error(f"关闭数据库连接时出错: {str(e)}")
                return False
        return True

    def initialize_database(self):
        """初始化数据库

        Returns:
            bool: 如果操作成功则返回True
        """
        try:
            self.logger.info(f"初始化数据库: {self.db_file_path}")

            # 获取连接
            conn = self.get_connection()
            cursor = conn.cursor()

            # 创建packages表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS packages (
                    name TEXT PRIMARY KEY,
                    aur_version TEXT,
                    aur_update_date TEXT,
                    upstream_version TEXT,
                    upstream_update_date TEXT,
                    upstream_url TEXT,
                    checker_type TEXT,
                    version_extract_key TEXT,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            self.logger.debug("软件表创建成功")

            # 添加索引以提高查询性能
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_packages_checker_type ON packages(checker_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_packages_aur_update_date ON packages(aur_update_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_packages_upstream_update_date ON packages(upstream_update_date)")
            self.logger.debug("索引创建成功")

            conn.commit()
            self.logger.info("数据库初始化完成")
            return True
        except Exception as e:
            self.logger.error(f"初始化数据库出错: {str(e)}")
            return False

    def execute(self, query, params=None):
        """执行SQL查询

        Args:
            query: SQL查询语句
            params: 查询参数（可选）

        Returns:
            cursor: 数据库游标
        """
        try:
            # 获取当前线程的连接
            conn = self.get_connection()
            cursor = conn.cursor()

            # 执行查询
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # 提交更改
            conn.commit()
            return cursor
        except Exception as e:
            self.logger.error(f"执行SQL查询失败: {str(e)}")
            # 如果发生错误，回滚
            if conn:
                conn.rollback()
            raise e
            
    def execute_many(self, query, params_list):
        """批量执行SQL查询

        Args:
            query: SQL查询语句
            params_list: 查询参数列表

        Returns:
            cursor: 数据库游标
        """
        if not params_list:
            return None
            
        try:
            # 获取当前线程的连接
            conn = self.get_connection()
            cursor = conn.cursor()

            # 批量执行查询
            cursor.executemany(query, params_list)

            # 提交更改
            conn.commit()
            return cursor
        except Exception as e:
            self.logger.error(f"批量执行SQL查询失败: {str(e)}")
            # 如果发生错误，回滚
            if conn:
                conn.rollback()
            raise e
            
    def _cache_key(self, query, params=None):
        """生成查询缓存的键

        Args:
            query: SQL查询语句
            params: 查询参数（可选）

        Returns:
            str: 缓存键
        """
        if params:
            # 确保参数可哈希
            if isinstance(params, list):
                params = tuple(params)
            return f"{query}:{str(params)}"
        return query
        
    def execute_cached(self, query, params=None):
        """执行带缓存的SQL查询（只用于SELECT查询）

        Args:
            query: SQL查询语句
            params: 查询参数（可选）

        Returns:
            cursor: 数据库游标
        """
        if not self._enable_cache or not query.strip().upper().startswith("SELECT"):
            return self.execute(query, params)
            
        cache_key = self._cache_key(query, params)
        
        # 检查缓存
        with self._cache_lock:
            if cache_key in self._query_cache:
                result, timestamp = self._query_cache[cache_key]
                if time.time() - timestamp <= self._cache_ttl:
                    self.logger.debug(f"使用缓存结果: {cache_key[:50]}...")
                    return result
        
        # 执行查询
        cursor = self.execute(query, params)
        result = cursor.fetchall()
        
        # 缓存结果
        with self._cache_lock:
            self._query_cache[cache_key] = (result, time.time())
            
        return result

    def get_all_packages(self):
        """获取所有软件包

        Returns:
            list: 软件包列表，每个元素为一个字典
        """
        try:
            # 使用缓存查询
            rows = self.execute_cached("SELECT * FROM packages ORDER BY name")

            # 将sqlite3.Row对象转换为字典列表
            packages = []
            for row in rows:
                packages.append({key: row[key] for key in row.keys()})

            return packages
        except Exception as e:
            self.logger.error(f"获取所有软件包失败: {str(e)}")
            return []

    def get_packages_by_names(self, names):
        """批量获取多个软件包的信息

        Args:
            names: 软件包名称列表

        Returns:
            dict: 以软件包名称为键的字典，值为软件包信息
        """
        if not names:
            return {}

        try:
            placeholders = ', '.join('?' for _ in names)
            query = f"SELECT * FROM packages WHERE name IN ({placeholders})"

            # 使用缓存查询
            rows = self.execute_cached(query, tuple(names))

            # 将结果转换为以名称为键的字典
            result = {}
            for row in rows:
                package = {key: row[key] for key in row.keys()}
                result[package['name']] = package

            return result
        except Exception as e:
            self.logger.error(f"批量获取软件包失败: {str(e)}")
            return {}

    def get_package_by_name(self, name):
        """根据名称获取软件包

        Args:
            name: 软件包名称

        Returns:
            dict: 软件包信息，如果不存在则返回None
        """
        try:
            # 使用缓存查询
            rows = self.execute_cached("SELECT * FROM packages WHERE name = ?", (name,))
            
            if not rows:
                return None
                
            row = rows[0]

            # 将sqlite3.Row对象转换为字典
            package = {key: row[key] for key in row.keys()}
            return package
        except Exception as e:
            self.logger.error(f"获取软件包 {name} 失败: {str(e)}")
            return None

    def add_package(self, package_info):
        """添加新软件包

        Args:
            package_info: 包含软件包信息的字典

        Returns:
            dict: 添加的软件包信息，如果失败则返回None
        """
        name = package_info.get('name')
        if not name:
            self.logger.error("软件包名称不能为空")
            return None

        try:

            # 从字典中获取其他字段
            upstream_url = package_info.get('upstream_url', '')
            checker_type = package_info.get('checker_type', '')
            version_extract_key = package_info.get('version_extract_key', '')
            notes = package_info.get('notes', '')

            now = datetime.now().isoformat()

            sql = """
                INSERT INTO packages 
                (name, upstream_url, checker_type, version_extract_key, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            cursor = self.execute(sql, (name, upstream_url, checker_type, version_extract_key, notes, now, now))

            # 返回插入的记录
            new_package = {
                'name': name,
                'upstream_url': upstream_url,
                'checker_type': checker_type,
                'version_extract_key': version_extract_key,
                'notes': notes,
                'created_at': now,
                'updated_at': now
            }

            return new_package
        except Exception as e:
            self.logger.error(f"添加软件包失败: {str(e)}")
            return None

    def update_package(self, name, package_info):
        """更新软件包信息

        Args:
            name: 软件包名称
            package_info: 包含要更新的软件包信息的字典

        Returns:
            dict: 更新后的软件包信息，如果失败则返回None
        """
        try:

            # 先检查软件包是否存在
            existing_package = self.get_package_by_name(name)
            if not existing_package:
                self.logger.error(f"更新软件包失败: 未找到软件包 {name}")
                return None

            # 构建更新SQL
            update_fields = []
            params = []

            # 处理各个可能需要更新的字段
            if 'upstream_url' in package_info:
                update_fields.append("upstream_url = ?")
                params.append(package_info['upstream_url'])

            if 'checker_type' in package_info:
                update_fields.append("checker_type = ?")
                params.append(package_info['checker_type'])

            if 'version_extract_key' in package_info:
                update_fields.append("version_extract_key = ?")
                params.append(package_info['version_extract_key'])

            if 'notes' in package_info:
                update_fields.append("notes = ?")
                params.append(package_info['notes'])

            # 更新时间
            now = datetime.now().isoformat()
            update_fields.append("updated_at = ?")
            params.append(now)

            # 如果没有要更新的字段，则返回原记录
            if not update_fields:
                return existing_package

            # 构建并执行SQL
            sql = f"UPDATE packages SET {', '.join(update_fields)} WHERE name = ?"
            params.append(name)
            cursor = self.execute(sql, tuple(params))

            if cursor.rowcount == 0:
                self.logger.warning(f"更新软件包失败: 未找到软件包 {name}")
                return None

            return self.get_package_by_name(name)
        except Exception as e:
            self.logger.error(f"更新软件包 {name} 失败: {str(e)}")
            return None

    def delete_package(self, name):
        """删除软件包

        Args:
            name: 软件包名称

        Returns:
            bool: 如果删除成功则返回True
        """
        try:
            cursor = self.execute("DELETE FROM packages WHERE name = ?", (name,))

            if cursor.rowcount == 0:
                self.logger.warning(f"删除软件包失败: 未找到软件包 {name}")
                return False

            self.logger.info(f"已删除软件包: {name}")
            return True
        except Exception as e:
            self.logger.error(f"删除软件包 {name} 失败: {str(e)}")
            return False

    def update_aur_version(self, name, aur_version, aur_epoch=None, aur_release=None):
        """更新软件包的 AUR 版本信息

        Args:
            name: 软件包名称
            aur_version: AUR版本
            aur_epoch: AUR epoch值
            aur_release: AUR release值

        Returns:
            int: 成功更新的记录数，如果失败则返回0
        """
        return self.update_multiple_aur_versions([{"name": name, "version": aur_version}]) if name and aur_version else 0
            
    def update_multiple_aur_versions(self, package_updates):
        """批量更新多个软件包的 AUR 版本信息

        Args:
            package_updates: 包含软件包名称和版本的字典列表，格式为 [{"name": name, "version": version}, ...]

        Returns:
            list: 成功更新的软件包信息列表
        """
        if not package_updates:
            return []
            
        try:
            now = datetime.now().isoformat()
            params_list = []
            
            for update in package_updates:
                name = update.get("name")
                version = update.get("version")
                if name and version:
                    params_list.append((version, now, now, name))
            
            if not params_list:
                return 0
                
            sql = """
                UPDATE packages
                SET aur_version = ?, aur_update_date = ?, updated_at = ?
                WHERE name = ?
            """
            
            cursor = self.execute_many(sql, params_list)
            self.logger.info(f"批量更新了 {cursor.rowcount} 个软件包的 AUR 版本")
            
            # 清除相关缓存
            self._clear_packages_cache()
            
            return cursor.rowcount
        except Exception as e:
            self.logger.error(f"批量更新 AUR 版本失败: {str(e)}")
            return 0
            
    def update_upstream_version(self, name, upstream_version):
        """更新软件包的上游版本信息

        Args:
            name: 软件包名称
            upstream_version: 上游版本

        Returns:
            int: 更新的行数，或0表示失败
        """
        return self.update_multiple_upstream_versions([{"name": name, "version": upstream_version}]) if name and upstream_version else 0
            
    def update_multiple_upstream_versions(self, package_updates):
        """批量更新多个软件包的上游版本信息

        Args:
            package_updates: 包含软件包名称和版本的字典列表，格式为 [{"name": name, "version": version}, ...]

        Returns:
            list: 成功更新的软件包信息列表
        """
        if not package_updates:
            return []
            
        try:
            now = datetime.now().isoformat()
            params_list = []
            
            for update in package_updates:
                name = update.get("name")
                version = update.get("version") or update.get("upstream_version")
                if name and version:
                    params_list.append((version, now, now, name))
            
            if not params_list:
                return 0
                
            sql = """
                UPDATE packages
                SET upstream_version = ?, upstream_update_date = ?, updated_at = ?
                WHERE name = ?
            """
            
            cursor = self.execute_many(sql, params_list)
            self.logger.info(f"批量更新了 {cursor.rowcount} 个软件包的上游版本")
            
            # 清除相关缓存
            self._clear_packages_cache()
            
            return cursor.rowcount
        except Exception as e:
            self.logger.error(f"批量更新上游版本失败: {str(e)}")
            return 0
            
    def _clear_packages_cache(self):
        """清除与软件包相关的缓存"""
        if not self._enable_cache:
            return
            
        with self._cache_lock:
            keys_to_remove = []
            for key in self._query_cache.keys():
                if "FROM packages" in key:
                    keys_to_remove.append(key)
                    
            for key in keys_to_remove:
                del self._query_cache[key]
                
            if keys_to_remove:
                self.logger.debug(f"已清除 {len(keys_to_remove)} 个软件包相关缓存项")

    def backup_database(self):
        """备份数据库

        Returns:
            str: 备份文件路径，如果失败则返回None
        """
        try:
            # 如果数据库文件不存在，则无需备份
            if not os.path.exists(self.db_file_path):
                self.logger.warning("数据库文件不存在，无法备份")
                return None
            # 创建备份目录
            backup_dir = os.path.join(os.path.dirname(self.db_file_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)

            # 创建备份文件名
            backup_filename = f"packages_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
            backup_path = os.path.join(backup_dir, backup_filename)

            # 关闭当前所有连接
            self.close()

            # 复制数据库文件
            shutil.copy2(self.db_file_path, backup_path)
            self.logger.info(f"数据库已备份到: {backup_path}")

            # 重新连接数据库
            self.initialize_database()
            return backup_path
        except Exception as e:
            self.logger.error(f"备份数据库失败: {str(e)}")
            return None

    def restore_database(self, backup_path):
        """从备份恢复数据库

        Args:
            backup_path: 备份文件路径

        Returns:
            bool: 如果操作成功则返回True
        """
        try:
            if not os.path.exists(backup_path):
                self.logger.error(f"备份文件不存在: {backup_path}")
                return False

            # 关闭当前所有连接
            self.close()

            # 复制备份文件到数据库位置
            shutil.copy2(backup_path, self.db_file_path)
            self.logger.info(f"数据库已从 {backup_path} 恢复")

            # 重新连接数据库
            return self.initialize_database()
        except Exception as e:
            self.logger.error(f"恢复数据库失败: {str(e)}")
            return False


            self.logger.error(f"获取所有设置失败: {str(e)}")
            return {}


            # 创建备份目录
            backup_dir = os.path.join(os.path.dirname(self.db_file_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)

            # 创建备份文件名
            backup_filename = f"packages_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
            backup_path = os.path.join(backup_dir, backup_filename)

            # 关闭当前所有连接
            self.close()

            # 复制数据库文件
            shutil.copy2(self.db_file_path, backup_path)
            self.logger.info(f"数据库已备份到: {backup_path}")

            # 重新连接数据库
            self.initialize_database()
            return backup_path
        except Exception as e:
            self.logger.error(f"备份数据库失败: {str(e)}")
            return None

    def restore_database(self, backup_path):
        """从备份恢复数据库

        Args:
            backup_path: 备份文件路径

        Returns:
            bool: 如果操作成功则返回True
        """
        try:
            if not os.path.exists(backup_path):
                self.logger.error(f"备份文件不存在: {backup_path}")
                return False

            # 关闭当前所有连接
            self.close()

            # 复制备份文件到数据库位置
            shutil.copy2(backup_path, self.db_file_path)
            self.logger.info(f"数据库已从 {backup_path} 恢复")

            # 重新连接数据库
            return self.initialize_database()
        except Exception as e:
            self.logger.error(f"恢复数据库失败: {str(e)}")
            return False
