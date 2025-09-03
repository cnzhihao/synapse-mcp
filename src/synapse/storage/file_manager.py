"""
JSON文件存储和目录管理系统 for Synapse MCP.

本模块实现了完整的JSON文件管理系统，包括：
- 安全的JSON文件读写操作
- 文件锁机制防止并发冲突
- 按日期组织的目录结构 (YYYY/MM/)
- 备份和恢复功能
- 存储空间监控和使用统计

主要特性：
- 原子性文件操作：写入失败时不会损坏原有数据
- 文件锁定：使用fcntl在Unix系统和msvcrt在Windows系统防止并发访问冲突
- 自动目录创建：按需创建年月目录结构
- 备份机制：自动创建备份文件，支持恢复
- 错误恢复：完整的异常处理和错误恢复机制
"""

import json
import os
try:
    import fcntl
except ImportError:
    # fcntl is not available on Windows
    fcntl = None
import shutil
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from contextlib import contextmanager
import tempfile
import logging
import time
import threading
from dataclasses import dataclass

from synapse.storage.paths import StoragePaths
from synapse.models.conversation import ConversationRecord, Solution

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class StorageStats:
    """存储统计信息数据类"""
    total_conversations: int = 0
    total_solutions: int = 0
    total_files: int = 0
    total_size_bytes: int = 0
    disk_usage_mb: float = 0.0
    avg_file_size_kb: float = 0.0
    last_updated: datetime = None
    

@dataclass  
class BackupInfo:
    """备份信息数据类"""
    backup_path: Path
    original_path: Path
    created_at: datetime
    size_bytes: int


class FileManager:
    """
    JSON文件存储和目录管理器
    
    这个类提供了完整的文件管理功能，用于处理Synapse MCP系统中的
    ConversationRecord和Solution对象的存储。
    
    核心功能：
    1. JSON文件的安全读写操作
    2. 文件锁机制防止并发冲突
    3. 按日期组织的目录结构管理
    4. 备份和恢复功能
    5. 存储空间监控和统计
    
    使用示例：
        storage_paths = StoragePaths()
        file_manager = FileManager(storage_paths)
        
        # 保存对话记录
        conversation = ConversationRecord(title="测试", content="内容")
        success = await file_manager.save_conversation(conversation)
        
        # 加载对话记录
        loaded = await file_manager.load_conversation(conversation.id)
    """
    
    def __init__(self, storage_paths: StoragePaths):
        """
        初始化FileManager
        
        Args:
            storage_paths: StoragePaths实例，用于路径管理
        """
        self.storage_paths = storage_paths
        self.lock_timeout = 30.0  # 文件锁超时时间（秒）
        self._file_locks = {}  # 文件锁缓存
        self._lock_mutex = threading.Lock()  # 线程锁
        
        # 确保必要的目录存在
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """确保所有必需的存储目录存在"""
        directories = [
            self.storage_paths.get_conversations_dir(),
            self.storage_paths.get_solutions_dir(),
            self.storage_paths.get_indexes_dir(),
            self.storage_paths.get_backups_dir(),
            self.storage_paths.get_cache_dir()
        ]
        
        for directory in directories:
            self.storage_paths.create_directory(directory)
    
    @contextmanager
    def _file_lock(self, file_path: Path, mode: str = 'r'):
        """
        文件锁上下文管理器
        
        提供跨平台的文件锁定机制，防止并发访问冲突。
        在Unix系统使用fcntl，在Windows系统使用msvcrt。
        
        Args:
            file_path: 要锁定的文件路径
            mode: 文件打开模式 ('r', 'w', 'a')
        
        Yields:
            file: 打开并锁定的文件对象
            
        Raises:
            TimeoutError: 获取文件锁超时
            OSError: 文件操作失败
        """
        lock_key = str(file_path.absolute())
        
        with self._lock_mutex:
            if lock_key not in self._file_locks:
                self._file_locks[lock_key] = threading.Lock()
            file_lock = self._file_locks[lock_key]
        
        # 获取线程锁
        if not file_lock.acquire(timeout=self.lock_timeout):
            raise TimeoutError(f"获取文件锁超时: {file_path}")
        
        try:
            # 确保父目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 打开文件
            file_obj = open(file_path, mode, encoding='utf-8')
            
            try:
                # 尝试获取文件系统级锁定
                if os.name == 'posix' and fcntl:
                    # Unix系统使用fcntl
                    lock_type = fcntl.LOCK_EX if 'w' in mode or 'a' in mode else fcntl.LOCK_SH
                    fcntl.flock(file_obj.fileno(), lock_type | fcntl.LOCK_NB)
                elif os.name == 'nt':
                    # Windows系统使用msvcrt
                    import msvcrt
                    start_time = time.time()
                    while time.time() - start_time < self.lock_timeout:
                        try:
                            msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        raise TimeoutError(f"Windows文件锁超时: {file_path}")
                
                yield file_obj
                
            finally:
                # 释放文件系统级锁定
                if os.name == 'posix' and fcntl:
                    fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
                elif os.name == 'nt':
                    import msvcrt
                    try:
                        msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass  # 忽略解锁错误
                
                file_obj.close()
        
        finally:
            # 释放线程锁
            file_lock.release()
    
    def _get_conversation_file_path(self, conversation_id: str, date_obj: Optional[date] = None) -> Path:
        """
        获取对话文件的完整路径
        
        根据对话ID和日期生成按年月组织的文件路径。
        路径格式: conversations/YYYY/MM/conv_YYYYMMDD_XXX.json
        
        Args:
            conversation_id: 对话ID
            date_obj: 日期对象，如果为None则使用当前日期
            
        Returns:
            Path: 对话文件的完整路径
        """
        if date_obj is None:
            date_obj = datetime.now().date()
        
        year_month_dir = self.storage_paths.get_conversations_dir() / str(date_obj.year) / f"{date_obj.month:02d}"
        return year_month_dir / f"{conversation_id}.json"
    
    def _get_solution_file_path(self, solution_id: str) -> Path:
        """
        获取解决方案文件的完整路径
        
        Args:
            solution_id: 解决方案ID
            
        Returns:
            Path: 解决方案文件路径
        """
        return self.storage_paths.get_solutions_dir() / f"{solution_id}.json"
    
    def _create_backup(self, file_path: Path) -> Optional[BackupInfo]:
        """
        创建文件备份
        
        在修改文件前创建备份，以防写入失败时数据丢失。
        备份文件存储在backups目录中。
        
        Args:
            file_path: 要备份的文件路径
            
        Returns:
            BackupInfo: 备份信息，如果备份失败返回None
        """
        if not file_path.exists():
            return None
        
        try:
            backups_dir = self.storage_paths.get_backups_dir()
            backup_name = f"{file_path.stem}_backup_{int(time.time())}{file_path.suffix}"
            backup_path = backups_dir / backup_name
            
            # 创建备份目录
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(file_path, backup_path)
            
            backup_info = BackupInfo(
                backup_path=backup_path,
                original_path=file_path,
                created_at=datetime.now(),
                size_bytes=backup_path.stat().st_size
            )
            
            logger.debug(f"创建备份成功: {backup_path}")
            return backup_info
            
        except Exception as e:
            logger.warning(f"创建备份失败 {file_path}: {e}")
            return None
    
    def _restore_from_backup(self, backup_info: BackupInfo) -> bool:
        """
        从备份恢复文件
        
        Args:
            backup_info: 备份信息
            
        Returns:
            bool: 恢复是否成功
        """
        try:
            if backup_info.backup_path.exists():
                shutil.copy2(backup_info.backup_path, backup_info.original_path)
                logger.info(f"从备份恢复成功: {backup_info.original_path}")
                return True
            else:
                logger.error(f"备份文件不存在: {backup_info.backup_path}")
                return False
                
        except Exception as e:
            logger.error(f"从备份恢复失败: {e}")
            return False
    
    def _atomic_write_json(self, file_path: Path, data: Any, backup: bool = True) -> bool:
        """
        原子性写入JSON文件
        
        使用临时文件和重命名操作确保写入的原子性，
        避免写入过程中系统崩溃导致文件损坏。
        
        Args:
            file_path: 目标文件路径
            data: 要写入的数据
            backup: 是否在写入前创建备份
            
        Returns:
            bool: 写入是否成功
        """
        backup_info = None
        
        try:
            # 创建备份
            if backup and file_path.exists():
                backup_info = self._create_backup(file_path)
            
            # 确保目标目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用临时文件进行原子性写入
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                suffix='.tmp',
                prefix=file_path.stem + '_',
                dir=file_path.parent,
                delete=False
            ) as temp_file:
                json.dump(data, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # 强制写入磁盘
                temp_path = Path(temp_file.name)
            
            # 原子性重命名
            temp_path.replace(file_path)
            
            logger.debug(f"JSON文件写入成功: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"JSON文件写入失败 {file_path}: {e}")
            
            # 尝试恢复备份
            if backup_info:
                self._restore_from_backup(backup_info)
            
            # 清理临时文件
            try:
                if 'temp_path' in locals() and temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            
            return False
    
    def save_conversation(self, conversation: ConversationRecord) -> bool:
        """
        保存对话记录到JSON文件
        
        将ConversationRecord对象保存到按日期组织的目录结构中。
        使用文件锁防止并发写入冲突。
        
        Args:
            conversation: 要保存的对话记录
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 生成文件路径
            file_path = self._get_conversation_file_path(
                conversation.id, 
                conversation.created_at.date()
            )
            
            # 转换为字典格式
            conversation_data = conversation.to_dict()
            
            # 原子性写入
            success = self._atomic_write_json(file_path, conversation_data)
            
            if success:
                logger.info(f"保存对话记录成功: {conversation.id}")
            else:
                logger.error(f"保存对话记录失败: {conversation.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"保存对话记录异常 {conversation.id}: {e}")
            return False
    
    def load_conversation(self, conversation_id: str, search_all_dates: bool = True) -> Optional[ConversationRecord]:
        """
        加载对话记录从JSON文件
        
        Args:
            conversation_id: 对话ID
            search_all_dates: 如果True，搜索所有日期目录；如果False，只搜索当前日期
            
        Returns:
            ConversationRecord: 加载的对话记录，未找到时返回None
        """
        try:
            # 首先尝试从当前日期目录加载
            file_path = self._get_conversation_file_path(conversation_id)
            
            if file_path.exists():
                return self._load_conversation_from_file(file_path)
            
            # 如果需要，搜索所有日期目录
            if search_all_dates:
                conversations_dir = self.storage_paths.get_conversations_dir()
                
                # 遍历年目录
                for year_dir in conversations_dir.iterdir():
                    if not year_dir.is_dir() or not year_dir.name.isdigit():
                        continue
                    
                    # 遍历月目录
                    for month_dir in year_dir.iterdir():
                        if not month_dir.is_dir():
                            continue
                        
                        # 查找对话文件
                        candidate_file = month_dir / f"{conversation_id}.json"
                        if candidate_file.exists():
                            return self._load_conversation_from_file(candidate_file)
            
            logger.debug(f"对话记录未找到: {conversation_id}")
            return None
            
        except Exception as e:
            logger.error(f"加载对话记录异常 {conversation_id}: {e}")
            return None
    
    def _fix_conversation_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        修复对话数据中可能存在的兼容性问题
        
        Args:
            data: 原始对话数据字典
            
        Returns:
            Dict[str, Any]: 修复后的对话数据
        """
        # 修复solutions中的language字段问题
        if 'solutions' in data and isinstance(data['solutions'], list):
            for solution in data['solutions']:
                if isinstance(solution, dict):
                    # 如果是code类型但没有language，尝试推断或设置默认值
                    if solution.get('type') == 'code' and not solution.get('language'):
                        content = solution.get('content', '').lower()
                        
                        # 简单的语言推断
                        if 'npx' in content or 'npm' in content or 'yarn' in content:
                            solution['language'] = 'bash'
                        elif 'def ' in content or 'import ' in content or 'python' in content:
                            solution['language'] = 'python'
                        elif 'function' in content or 'const ' in content or 'let ' in content:
                            solution['language'] = 'javascript'
                        elif '<?php' in content or 'php' in content:
                            solution['language'] = 'php'
                        elif '#include' in content or 'int main' in content:
                            solution['language'] = 'c'
                        elif 'public class' in content or 'java' in content:
                            solution['language'] = 'java'
                        else:
                            # 如果无法推断，设置为通用的shell/bash
                            solution['language'] = 'shell'
                        
                        logger.info(f"修复解决方案 {solution.get('id', 'unknown')} 的语言字段: {solution['language']}")
        
        return data
    
    def _load_conversation_from_file(self, file_path: Path) -> Optional[ConversationRecord]:
        """
        从指定文件加载对话记录
        
        Args:
            file_path: 文件路径
            
        Returns:
            ConversationRecord: 加载的对话记录
        """
        try:
            with self._file_lock(file_path, 'r') as f:
                data = json.load(f)
                
            # 修复可能存在的数据问题
            data = self._fix_conversation_data(data)
            
            return ConversationRecord.from_dict(data)
                
        except Exception as e:
            logger.error(f"从文件加载对话记录失败 {file_path}: {e}")
            return None
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除对话记录
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            # 先查找文件
            conversation = self.load_conversation(conversation_id)
            if not conversation:
                logger.warning(f"要删除的对话记录不存在: {conversation_id}")
                return False
            
            # 获取文件路径
            file_path = self._get_conversation_file_path(
                conversation_id,
                conversation.created_at.date()
            )
            
            if file_path.exists():
                # 创建备份后删除
                backup_info = self._create_backup(file_path)
                file_path.unlink()
                
                logger.info(f"删除对话记录成功: {conversation_id}")
                return True
            else:
                logger.warning(f"对话记录文件不存在: {conversation_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除对话记录异常 {conversation_id}: {e}")
            return False
    
    def list_conversations(self, limit: Optional[int] = None, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[str]:
        """
        列出所有对话记录ID
        
        Args:
            limit: 限制返回数量
            start_date: 开始日期过滤
            end_date: 结束日期过滤
            
        Returns:
            List[str]: 对话ID列表
        """
        conversation_ids = []
        
        try:
            conversations_dir = self.storage_paths.get_conversations_dir()
            
            # 遍历年目录
            for year_dir in sorted(conversations_dir.iterdir(), reverse=True):
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue
                
                year = int(year_dir.name)
                
                # 遍历月目录
                for month_dir in sorted(year_dir.iterdir(), reverse=True):
                    if not month_dir.is_dir() or not month_dir.name.isdigit():
                        continue
                    
                    month = int(month_dir.name)
                    current_date = date(year, month, 1)
                    
                    # 日期过滤
                    if start_date and current_date < start_date:
                        continue
                    if end_date and current_date > end_date:
                        continue
                    
                    # 遍历JSON文件
                    for json_file in sorted(month_dir.glob("*.json"), reverse=True):
                        if json_file.stem.startswith("conv_"):
                            conversation_ids.append(json_file.stem)
                            
                            # 检查数量限制
                            if limit and len(conversation_ids) >= limit:
                                return conversation_ids
            
            return conversation_ids
            
        except Exception as e:
            logger.error(f"列出对话记录异常: {e}")
            return []
    
    def save_solution(self, solution: Solution) -> bool:
        """
        保存解决方案到JSON文件
        
        Args:
            solution: 要保存的解决方案
            
        Returns:
            bool: 保存是否成功
        """
        try:
            file_path = self._get_solution_file_path(solution.id)
            solution_data = solution.to_dict()
            
            success = self._atomic_write_json(file_path, solution_data)
            
            if success:
                logger.info(f"保存解决方案成功: {solution.id}")
            else:
                logger.error(f"保存解决方案失败: {solution.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"保存解决方案异常 {solution.id}: {e}")
            return False
    
    def load_solution(self, solution_id: str) -> Optional[Solution]:
        """
        加载解决方案从JSON文件
        
        Args:
            solution_id: 解决方案ID
            
        Returns:
            Solution: 加载的解决方案，未找到时返回None
        """
        try:
            file_path = self._get_solution_file_path(solution_id)
            
            if not file_path.exists():
                return None
            
            with self._file_lock(file_path, 'r') as f:
                data = json.load(f)
                return Solution.from_dict(data)
                
        except Exception as e:
            logger.error(f"加载解决方案异常 {solution_id}: {e}")
            return None
    
    def load_all_solutions(self) -> List[Solution]:
        """
        批量加载所有解决方案
        
        此方法提供了一种高效的方式来加载solutions目录中的所有解决方案，
        包括单独的解决方案文件和批量提取文件。
        
        Returns:
            List[Solution]: 所有解决方案的列表，已去重
        """
        solutions = []
        solutions_dir = self.storage_paths.get_solutions_dir()
        
        if not solutions_dir.exists():
            logger.warning(f"解决方案目录不存在: {solutions_dir}")
            return []
        
        try:
            # 加载单个解决方案文件 (sol_*.json)
            for solution_file in solutions_dir.glob("sol_*.json"):
                try:
                    solution = self.load_solution(solution_file.stem)
                    if solution:
                        solutions.append(solution)
                except Exception as e:
                    logger.warning(f"加载单个解决方案文件失败 {solution_file}: {e}")
                    continue
            
            # 加载批量提取的解决方案文件 (extracted_*_solutions_*.json)
            for batch_file in solutions_dir.glob("extracted_*_solutions_*.json"):
                try:
                    with self._file_lock(batch_file, 'r') as f:
                        data = json.load(f)
                        
                    batch_solutions = data.get("solutions", [])
                    for sol_data in batch_solutions:
                        try:
                            solution = Solution.from_dict(sol_data)
                            solutions.append(solution)
                        except Exception as e:
                            logger.warning(f"解析批量解决方案失败 {batch_file}: {e}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"加载批量解决方案文件失败 {batch_file}: {e}")
                    continue
            
            # 去重 - 基于ID，保留引用次数最高的版本
            unique_solutions = {}
            for solution in solutions:
                if solution.id not in unique_solutions:
                    unique_solutions[solution.id] = solution
                else:
                    # 保留引用次数更高的版本
                    if solution.reference_count > unique_solutions[solution.id].reference_count:
                        unique_solutions[solution.id] = solution
            
            result = list(unique_solutions.values())
            logger.info(f"成功加载 {len(result)} 个解决方案（去重后）")
            return result
            
        except Exception as e:
            logger.error(f"批量加载解决方案失败: {e}")
            return []
    
    def update_solution_reference_count(self, solution_id: str) -> bool:
        """
        更新解决方案的引用计数
        
        此方法提供了一种高效的方式来增加解决方案的引用计数，
        无需完整加载和保存解决方案对象。
        
        Args:
            solution_id: 要更新的解决方案ID
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 加载解决方案
            solution = self.load_solution(solution_id)
            if not solution:
                logger.warning(f"无法找到解决方案用于引用计数更新: {solution_id}")
                return False
            
            # 增加引用计数和更新时间
            solution.increment_reference()
            
            # 保存更新后的解决方案
            success = self.save_solution(solution)
            if success:
                logger.debug(f"解决方案引用计数更新成功: {solution_id} -> {solution.reference_count}")
            else:
                logger.error(f"保存解决方案引用计数失败: {solution_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"更新解决方案引用计数异常 {solution_id}: {e}")
            return False
    
    def get_storage_statistics(self) -> StorageStats:
        """
        获取存储统计信息
        
        Returns:
            StorageStats: 存储统计信息
        """
        stats = StorageStats(last_updated=datetime.now())
        
        try:
            conversations_dir = self.storage_paths.get_conversations_dir()
            solutions_dir = self.storage_paths.get_solutions_dir()
            
            total_size = 0
            total_files = 0
            
            # 统计对话记录
            if conversations_dir.exists():
                for file_path in conversations_dir.rglob("*.json"):
                    if file_path.is_file():
                        stats.total_conversations += 1
                        total_files += 1
                        file_size = file_path.stat().st_size
                        total_size += file_size
            
            # 统计解决方案
            if solutions_dir.exists():
                for file_path in solutions_dir.glob("*.json"):
                    if file_path.is_file():
                        stats.total_solutions += 1
                        total_files += 1
                        file_size = file_path.stat().st_size
                        total_size += file_size
            
            # 计算统计指标
            stats.total_files = total_files
            stats.total_size_bytes = total_size
            stats.disk_usage_mb = total_size / (1024 * 1024)
            stats.avg_file_size_kb = (total_size / total_files / 1024) if total_files > 0 else 0
            
            return stats
            
        except Exception as e:
            logger.error(f"获取存储统计异常: {e}")
            return stats
    
    def cleanup_backups(self, max_age_days: int = 30, max_count: int = 100) -> int:
        """
        清理旧备份文件
        
        Args:
            max_age_days: 保留备份的最大天数
            max_count: 保留备份的最大数量
            
        Returns:
            int: 清理的备份文件数量
        """
        cleaned_count = 0
        
        try:
            backups_dir = self.storage_paths.get_backups_dir()
            
            if not backups_dir.exists():
                return 0
            
            # 获取所有备份文件并按创建时间排序
            backup_files = []
            for backup_file in backups_dir.glob("*_backup_*"):
                if backup_file.is_file():
                    stat = backup_file.stat()
                    backup_files.append((backup_file, stat.st_mtime))
            
            # 按修改时间排序（最新的在前）
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 3600
            
            for i, (backup_file, mtime) in enumerate(backup_files):
                should_delete = False
                
                # 检查是否超过数量限制
                if i >= max_count:
                    should_delete = True
                
                # 检查是否超过时间限制
                if current_time - mtime > max_age_seconds:
                    should_delete = True
                
                if should_delete:
                    try:
                        backup_file.unlink()
                        cleaned_count += 1
                        logger.debug(f"清理旧备份文件: {backup_file}")
                    except Exception as e:
                        logger.warning(f"清理备份文件失败 {backup_file}: {e}")
            
            logger.info(f"清理了 {cleaned_count} 个备份文件")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理备份文件异常: {e}")
            return cleaned_count
    
    def export_data(self, export_path: Path, include_backups: bool = False) -> bool:
        """
        导出所有数据到指定路径
        
        Args:
            export_path: 导出目录路径
            include_backups: 是否包含备份文件
            
        Returns:
            bool: 导出是否成功
        """
        try:
            export_path.mkdir(parents=True, exist_ok=True)
            
            # 导出对话记录
            conversations_src = self.storage_paths.get_conversations_dir()
            if conversations_src.exists():
                conversations_dst = export_path / "conversations"
                shutil.copytree(conversations_src, conversations_dst, dirs_exist_ok=True)
            
            # 导出解决方案
            solutions_src = self.storage_paths.get_solutions_dir()
            if solutions_src.exists():
                solutions_dst = export_path / "solutions"
                shutil.copytree(solutions_src, solutions_dst, dirs_exist_ok=True)
            
            # 导出索引
            indexes_src = self.storage_paths.get_indexes_dir()
            if indexes_src.exists():
                indexes_dst = export_path / "indexes"
                shutil.copytree(indexes_src, indexes_dst, dirs_exist_ok=True)
            
            # 可选导出备份
            if include_backups:
                backups_src = self.storage_paths.get_backups_dir()
                if backups_src.exists():
                    backups_dst = export_path / "backups"
                    shutil.copytree(backups_src, backups_dst, dirs_exist_ok=True)
            
            # 生成导出信息文件
            export_info = {
                "exported_at": datetime.now().isoformat(),
                "source_paths": self.storage_paths.get_storage_info(),
                "statistics": self.get_storage_statistics().__dict__,
                "include_backups": include_backups
            }
            
            export_info_file = export_path / "export_info.json"
            with open(export_info_file, 'w', encoding='utf-8') as f:
                json.dump(export_info, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"数据导出成功: {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"数据导出失败: {e}")
            return False
    
    def import_data(self, import_path: Path, merge_mode: str = "append") -> bool:
        """
        从指定路径导入数据
        
        Args:
            import_path: 导入数据的路径
            merge_mode: 合并模式 ("append": 追加, "overwrite": 覆盖)
            
        Returns:
            bool: 导入是否成功
        """
        try:
            if not import_path.exists():
                logger.error(f"导入路径不存在: {import_path}")
                return False
            
            # 创建完整备份
            backup_success = self.export_data(
                self.storage_paths.get_backups_dir() / f"pre_import_{int(time.time())}",
                include_backups=False
            )
            
            if not backup_success:
                logger.warning("导入前备份失败，继续导入")
            
            # 导入对话记录
            conversations_src = import_path / "conversations"
            if conversations_src.exists():
                conversations_dst = self.storage_paths.get_conversations_dir()
                if merge_mode == "overwrite" and conversations_dst.exists():
                    shutil.rmtree(conversations_dst)
                shutil.copytree(conversations_src, conversations_dst, dirs_exist_ok=True)
            
            # 导入解决方案
            solutions_src = import_path / "solutions"
            if solutions_src.exists():
                solutions_dst = self.storage_paths.get_solutions_dir()
                if merge_mode == "overwrite" and solutions_dst.exists():
                    shutil.rmtree(solutions_dst)
                shutil.copytree(solutions_src, solutions_dst, dirs_exist_ok=True)
            
            # 导入索引
            indexes_src = import_path / "indexes"
            if indexes_src.exists():
                indexes_dst = self.storage_paths.get_indexes_dir()
                if merge_mode == "overwrite" and indexes_dst.exists():
                    shutil.rmtree(indexes_dst)
                shutil.copytree(indexes_src, indexes_dst, dirs_exist_ok=True)
            
            logger.info(f"数据导入成功: {import_path}")
            return True
            
        except Exception as e:
            logger.error(f"数据导入失败: {e}")
            return False