"""
搜索索引管理模块

本模块实现了轻量级的搜索索引系统，用于提高对话搜索的速度和准确性。
不使用复杂的向量数据库，而是采用关键词和标签的倒排索引。

核心功能：
1. 关键词索引 - 基于标题、摘要、标签的关键词倒排索引
2. 标签索引 - 技术标签的快速查询索引  
3. 时间索引 - 基于时间的快速过滤
4. 索引维护 - 增量更新和定期重建
"""

import json
import logging
from datetime import datetime, date
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict
from pathlib import Path

from synapse.models.conversation import ConversationRecord
from synapse.storage.paths import StoragePaths

# 配置日志
logger = logging.getLogger(__name__)


class SearchIndex:
    """
    搜索索引数据结构
    
    存储所有索引信息的统一数据结构：
    - keyword_index: 关键词倒排索引 {keyword: [conversation_ids]}
    - tag_index: 标签索引 {tag: [conversation_ids]}  
    - metadata_index: 元数据索引 {conversation_id: metadata}
    - stats: 索引统计信息
    """
    
    def __init__(self):
        self.keyword_index: Dict[str, Set[str]] = defaultdict(set)
        self.tag_index: Dict[str, Set[str]] = defaultdict(set)
        self.metadata_index: Dict[str, Dict[str, Any]] = {}
        self.stats = {
            "total_conversations": 0,
            "total_keywords": 0,
            "total_tags": 0,
            "last_updated": None,
            "index_version": "1.0"
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式用于JSON序列化"""
        return {
            "keyword_index": {
                keyword: list(conv_ids) 
                for keyword, conv_ids in self.keyword_index.items()
            },
            "tag_index": {
                tag: list(conv_ids)
                for tag, conv_ids in self.tag_index.items()
            },
            "metadata_index": self.metadata_index,
            "stats": self.stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchIndex':
        """从字典创建SearchIndex对象"""
        index = cls()
        
        # 加载关键词索引
        keyword_data = data.get("keyword_index", {})
        for keyword, conv_ids in keyword_data.items():
            index.keyword_index[keyword] = set(conv_ids)
        
        # 加载标签索引
        tag_data = data.get("tag_index", {})
        for tag, conv_ids in tag_data.items():
            index.tag_index[tag] = set(conv_ids)
        
        # 加载元数据索引
        index.metadata_index = data.get("metadata_index", {})
        
        # 加载统计信息
        index.stats = data.get("stats", index.stats)
        
        return index


class SearchIndexer:
    """
    搜索索引管理器
    
    负责创建、更新和维护搜索索引。
    提供高效的索引构建和查询支持。
    """
    
    def __init__(self, storage_paths: StoragePaths):
        """
        初始化搜索索引器
        
        Args:
            storage_paths: 存储路径管理器
        """
        self.storage_paths = storage_paths
        self.index_file_path = storage_paths.get_indexes_dir() / "search_index.json"
        self._current_index: Optional[SearchIndex] = None
        
        # 确保索引目录存在
        self.storage_paths.create_directory(storage_paths.get_indexes_dir())
    
    def load_index(self) -> SearchIndex:
        """
        加载搜索索引
        
        Returns:
            SearchIndex: 搜索索引对象
        """
        if self._current_index is not None:
            return self._current_index
        
        try:
            if self.index_file_path.exists():
                with open(self.index_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._current_index = SearchIndex.from_dict(data)
                    logger.debug(f"成功加载搜索索引: {len(self._current_index.metadata_index)} 条记录")
            else:
                # 创建新的索引
                self._current_index = SearchIndex()
                logger.info("创建新的搜索索引")
        
        except Exception as e:
            logger.error(f"加载搜索索引失败: {e}")
            self._current_index = SearchIndex()
        
        return self._current_index
    
    def save_index(self) -> bool:
        """
        保存搜索索引到文件
        
        Returns:
            bool: 保存是否成功
        """
        if self._current_index is None:
            return True
        
        try:
            # 更新统计信息
            self._current_index.stats.update({
                "total_conversations": len(self._current_index.metadata_index),
                "total_keywords": len(self._current_index.keyword_index),
                "total_tags": len(self._current_index.tag_index),
                "last_updated": datetime.now().isoformat()
            })
            
            # 保存到文件
            with open(self.index_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._current_index.to_dict(), f, indent=2, ensure_ascii=False)
            
            logger.debug(f"成功保存搜索索引: {self.index_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存搜索索引失败: {e}")
            return False
    
    def add_conversation(self, conversation: ConversationRecord) -> bool:
        """
        添加对话到搜索索引
        
        Args:
            conversation: 对话记录
            
        Returns:
            bool: 添加是否成功
        """
        try:
            index = self.load_index()
            
            # 1. 提取关键词并添加到关键词索引
            keywords = self._extract_keywords(conversation)
            for keyword in keywords:
                index.keyword_index[keyword].add(conversation.id)
            
            # 2. 添加标签到标签索引
            for tag in conversation.tags:
                if tag:  # 确保标签不为空
                    index.tag_index[tag.lower()].add(conversation.id)
            
            # 3. 添加元数据
            metadata = {
                "title": conversation.title,
                "category": conversation.category,
                "importance": conversation.importance,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "tags": conversation.tags,
                "summary": conversation.summary[:200],  # 限制摘要长度
                "content_length": len(conversation.content),
                "solutions_count": len(conversation.solutions)
            }
            
            index.metadata_index[conversation.id] = metadata
            
            # 4. 保存索引
            success = self.save_index()
            
            if success:
                logger.info(f"成功添加对话到索引: {conversation.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"添加对话到索引失败 {conversation.id}: {e}")
            return False
    
    def remove_conversation(self, conversation_id: str) -> bool:
        """
        从搜索索引中移除对话
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 移除是否成功
        """
        try:
            index = self.load_index()
            
            # 1. 从元数据索引中获取对话信息
            if conversation_id not in index.metadata_index:
                logger.warning(f"索引中未找到对话: {conversation_id}")
                return False
            
            metadata = index.metadata_index[conversation_id]
            
            # 2. 从关键词索引中移除
            keywords = self._extract_keywords_from_metadata(metadata)
            for keyword in keywords:
                if keyword in index.keyword_index:
                    index.keyword_index[keyword].discard(conversation_id)
                    # 如果关键词没有关联的对话，删除该关键词
                    if not index.keyword_index[keyword]:
                        del index.keyword_index[keyword]
            
            # 3. 从标签索引中移除
            for tag in metadata.get("tags", []):
                if tag and tag.lower() in index.tag_index:
                    index.tag_index[tag.lower()].discard(conversation_id)
                    # 如果标签没有关联的对话，删除该标签
                    if not index.tag_index[tag.lower()]:
                        del index.tag_index[tag.lower()]
            
            # 4. 从元数据索引中移除
            del index.metadata_index[conversation_id]
            
            # 5. 保存索引
            success = self.save_index()
            
            if success:
                logger.info(f"成功从索引中移除对话: {conversation_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"从索引中移除对话失败 {conversation_id}: {e}")
            return False
    
    def update_conversation(self, conversation: ConversationRecord) -> bool:
        """
        更新搜索索引中的对话信息
        
        Args:
            conversation: 更新后的对话记录
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 先移除旧的索引信息
            self.remove_conversation(conversation.id)
            
            # 再添加新的索引信息
            return self.add_conversation(conversation)
            
        except Exception as e:
            logger.error(f"更新索引中的对话失败 {conversation.id}: {e}")
            return False
    
    def search_conversations(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        time_range: Optional[str] = None,
        importance_min: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        搜索对话
        
        Args:
            query: 搜索查询关键词
            tags: 标签过滤
            category: 分类过滤
            time_range: 时间范围过滤
            importance_min: 最小重要性等级
            limit: 结果数量限制
            
        Returns:
            List[Dict[str, Any]]: 搜索结果列表
        """
        try:
            index = self.load_index()
            
            # 1. 关键词搜索
            query_words = self._tokenize_query(query)
            candidate_ids = self._search_by_keywords(index, query_words)
            
            # 2. 标签过滤
            if tags:
                tag_ids = self._search_by_tags(index, tags)
                candidate_ids = candidate_ids.intersection(tag_ids) if candidate_ids else tag_ids
            
            # 3. 应用其他过滤条件
            filtered_results = []
            for conv_id in candidate_ids:
                metadata = index.metadata_index.get(conv_id)
                if not metadata:
                    continue
                
                # 分类过滤
                if category and metadata.get("category") != category:
                    continue
                
                # 重要性过滤
                if importance_min and metadata.get("importance", 0) < importance_min:
                    continue
                
                # 时间范围过滤
                if time_range and not self._matches_time_range(metadata, time_range):
                    continue
                
                # 计算相关性分数
                score = self._calculate_relevance_score(metadata, query_words, tags)
                
                result = {
                    "id": conv_id,
                    "title": metadata.get("title", ""),
                    "summary": metadata.get("summary", ""),
                    "tags": metadata.get("tags", []),
                    "category": metadata.get("category", ""),
                    "importance": metadata.get("importance", 0),
                    "created_at": metadata.get("created_at", ""),
                    "match_score": round(score, 3),
                    "type": "conversation"
                }
                
                filtered_results.append(result)
            
            # 4. 按相关性分数排序并限制结果数量
            filtered_results.sort(key=lambda x: x["match_score"], reverse=True)
            
            return filtered_results[:limit]
            
        except Exception as e:
            logger.error(f"搜索对话失败: {e}")
            return []
    
    def get_index_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息
        
        Returns:
            Dict[str, Any]: 索引统计信息
        """
        try:
            index = self.load_index()
            return index.stats.copy()
            
        except Exception as e:
            logger.error(f"获取索引统计信息失败: {e}")
            return {}
    
    def rebuild_index(self, file_manager) -> bool:
        """
        重建搜索索引
        
        Args:
            file_manager: 文件管理器实例
            
        Returns:
            bool: 重建是否成功
        """
        try:
            logger.info("开始重建搜索索引...")
            
            # 1. 创建新的索引
            new_index = SearchIndex()
            
            # 2. 获取所有对话记录ID
            conversation_ids = file_manager.list_conversations()
            
            success_count = 0
            error_count = 0
            
            # 3. 逐个加载对话并添加到索引
            for conv_id in conversation_ids:
                try:
                    conversation = file_manager.load_conversation(conv_id)
                    if conversation:
                        # 提取关键词
                        keywords = self._extract_keywords(conversation)
                        for keyword in keywords:
                            new_index.keyword_index[keyword].add(conversation.id)
                        
                        # 添加标签
                        for tag in conversation.tags:
                            if tag:
                                new_index.tag_index[tag.lower()].add(conversation.id)
                        
                        # 添加元数据
                        metadata = {
                            "title": conversation.title,
                            "category": conversation.category,
                            "importance": conversation.importance,
                            "created_at": conversation.created_at.isoformat(),
                            "updated_at": conversation.updated_at.isoformat(),
                            "tags": conversation.tags,
                            "summary": conversation.summary[:200],
                            "content_length": len(conversation.content),
                            "solutions_count": len(conversation.solutions)
                        }
                        
                        new_index.metadata_index[conversation.id] = metadata
                        success_count += 1
                    
                except Exception as e:
                    logger.warning(f"处理对话 {conv_id} 时失败: {e}")
                    error_count += 1
            
            # 4. 保存新索引
            self._current_index = new_index
            save_success = self.save_index()
            
            if save_success:
                logger.info(f"索引重建成功: 处理 {success_count} 条对话, {error_count} 条失败")
                return True
            else:
                logger.error("索引重建失败: 无法保存索引文件")
                return False
                
        except Exception as e:
            logger.error(f"重建索引失败: {e}")
            return False
    
    def _extract_keywords(self, conversation: ConversationRecord) -> Set[str]:
        """从对话记录中提取关键词"""
        keywords = set()
        
        # 从标题提取关键词
        title_words = self._tokenize_text(conversation.title)
        keywords.update(title_words)
        
        # 从摘要提取关键词
        summary_words = self._tokenize_text(conversation.summary)
        keywords.update(summary_words)
        
        # 添加标签作为关键词
        keywords.update(tag.lower() for tag in conversation.tags if tag)
        
        # 从分类提取
        if conversation.category:
            keywords.add(conversation.category.lower())
        
        return keywords
    
    def _extract_keywords_from_metadata(self, metadata: Dict[str, Any]) -> Set[str]:
        """从元数据中提取关键词"""
        keywords = set()
        
        # 从标题提取
        title_words = self._tokenize_text(metadata.get("title", ""))
        keywords.update(title_words)
        
        # 从摘要提取
        summary_words = self._tokenize_text(metadata.get("summary", ""))
        keywords.update(summary_words)
        
        # 从标签提取
        tags = metadata.get("tags", [])
        keywords.update(tag.lower() for tag in tags if tag)
        
        # 从分类提取
        category = metadata.get("category", "")
        if category:
            keywords.add(category.lower())
        
        return keywords
    
    def _tokenize_text(self, text: str) -> Set[str]:
        """文本分词"""
        if not text:
            return set()
        
        # 简单的分词：按空格和标点符号分割
        import string
        
        # 转换为小写
        text = text.lower()
        
        # 移除标点符号
        text = text.translate(str.maketrans('', '', string.punctuation))
        
        # 按空格分词
        words = text.split()
        
        # 过滤长度和停用词
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did'}
        
        filtered_words = set()
        for word in words:
            if len(word) >= 2 and word not in stop_words:
                filtered_words.add(word)
        
        return filtered_words
    
    def _tokenize_query(self, query: str) -> Set[str]:
        """查询分词"""
        return self._tokenize_text(query)
    
    def _search_by_keywords(self, index: SearchIndex, query_words: Set[str]) -> Set[str]:
        """基于关键词搜索"""
        result_ids = set()
        
        for word in query_words:
            if word in index.keyword_index:
                result_ids.update(index.keyword_index[word])
        
        return result_ids
    
    def _search_by_tags(self, index: SearchIndex, tags: List[str]) -> Set[str]:
        """基于标签搜索"""
        result_ids = set()
        
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in index.tag_index:
                result_ids.update(index.tag_index[tag_lower])
        
        return result_ids
    
    def _matches_time_range(self, metadata: Dict[str, Any], time_range: str) -> bool:
        """检查是否匹配时间范围"""
        try:
            created_at_str = metadata.get("created_at")
            if not created_at_str:
                return False
            
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            now = datetime.now()
            
            if time_range == "week":
                return (now - created_at).days <= 7
            elif time_range == "month":
                return (now - created_at).days <= 30
            else:  # "all"
                return True
                
        except Exception:
            return False
    
    def _calculate_relevance_score(
        self,
        metadata: Dict[str, Any],
        query_words: Set[str],
        tags: Optional[List[str]] = None
    ) -> float:
        """
        计算相关性分数
        
        基于以下因素：
        - 标题匹配：50%权重
        - 标签匹配：30%权重  
        - 摘要匹配：20%权重
        - 重要性加权
        - 时间新鲜度加权
        """
        score = 0.0
        
        # 1. 标题匹配 (50%权重)
        title_words = self._tokenize_text(metadata.get("title", ""))
        title_matches = len(query_words.intersection(title_words))
        if title_matches > 0 and query_words:
            title_score = title_matches / len(query_words)
            score += title_score * 0.5
        
        # 2. 标签匹配 (30%权重)
        if tags:
            conversation_tags = set(tag.lower() for tag in metadata.get("tags", []))
            search_tags = set(tag.lower() for tag in tags)
            tag_matches = len(search_tags.intersection(conversation_tags))
            if tag_matches > 0:
                tag_score = tag_matches / len(search_tags)
                score += tag_score * 0.3
        
        # 3. 摘要匹配 (20%权重)
        summary_words = self._tokenize_text(metadata.get("summary", ""))
        summary_matches = len(query_words.intersection(summary_words))
        if summary_matches > 0 and query_words:
            summary_score = summary_matches / len(query_words)
            score += summary_score * 0.2
        
        # 4. 重要性加权 (5%权重)
        importance = metadata.get("importance", 1)
        importance_boost = importance / 5.0 * 0.05
        score += importance_boost
        
        # 5. 时间新鲜度加权 (5%权重)
        try:
            created_at_str = metadata.get("created_at", "")
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                now = datetime.now()
                days_old = (now - created_at).days
                
                # 30天内的对话获得新鲜度加分
                if days_old <= 30:
                    freshness_boost = (30 - days_old) / 30.0 * 0.05
                    score += freshness_boost
        except Exception:
            pass
        
        return min(score, 1.0)  # 确保分数不超过1.0