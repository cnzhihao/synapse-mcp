"""
智能知识库搜索工具 for Synapse MCP

本模块实现了完整的知识库搜索功能，提供智能、高效的对话记录和解决方案检索。

核心功能：
1. 三层搜索策略 - 精确匹配、标签过滤、模糊匹配的组合搜索
2. 多因子评分算法 - 基于相关性、重要性、时间新鲜度的综合评分
3. 高性能查询 - 目标响应时间 < 200ms，搜索准确率 > 80%
4. 丰富的过滤选项 - 支持分类、标签、时间范围、重要性等多维度过滤
5. 智能结果排序 - 基于多因子评分的智能排序和相关性优化

技术特性：
- 倒排索引加速搜索性能
- 缓存机制减少重复计算
- 并发安全的索引访问
- 完整的错误处理和日志记录
- MCP协议标准兼容
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass

from synapse.storage.paths import StoragePaths
from synapse.storage.file_manager import FileManager
from synapse.tools.search_indexer import SearchIndexer
from synapse.models.conversation import ConversationRecord

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    id: str
    title: str
    snippet: str
    match_score: float
    created_at: str
    tags: List[str]
    category: str
    importance: int
    type: str
    content_length: int
    solutions_count: int


@dataclass
class SearchStats:
    """搜索统计信息"""
    query_processed: str
    search_time_ms: float
    total_candidates: int
    filtered_results: int
    returned_results: int
    index_hits: int
    cache_hits: int


class SearchKnowledgeTool:
    """
    智能知识库搜索工具
    
    实现了完整的知识库搜索功能，包括：
    - 三层搜索策略：精确匹配 + 标签过滤 + 内容匹配
    - 多因子评分算法：相关性 + 重要性 + 时间新鲜度
    - 高性能优化：索引查询 + 结果缓存 + 并发控制
    - 丰富过滤：类别、标签、时间范围、重要性等级
    
    使用示例:
        storage_paths = StoragePaths()
        file_manager = FileManager(storage_paths)
        search_tool = SearchKnowledgeTool(storage_paths, file_manager)
        
        results = search_tool.search_knowledge(
            query="React性能优化",
            category="programming",
            tags=["react", "performance"],
            limit=10
        )
    """
    
    def __init__(self, storage_paths: StoragePaths, file_manager: FileManager):
        """
        初始化搜索工具
        
        Args:
            storage_paths: 存储路径管理器
            file_manager: 文件管理器，用于加载对话内容
        """
        self.storage_paths = storage_paths
        self.file_manager = file_manager
        self.indexer = SearchIndexer(storage_paths)
        
        # 性能优化配置
        self.max_snippet_length = 200
        self.min_relevance_score = 0.1
        self.cache_ttl = 300  # 缓存时间5分钟
        self._search_cache = {}
        
        # 搜索权重配置 (总和必须为1.0)
        self.scoring_weights = {
            "exact_match": 0.5,     # 精确匹配权重
            "tag_match": 0.3,       # 标签匹配权重
            "content_match": 0.2,   # 内容匹配权重
            "importance_boost": 0.05,  # 重要性加权
            "recency_boost": 0.05   # 时间新鲜度加权
        }
        
        logger.info("SearchKnowledgeTool 初始化完成")
    
    def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        time_range: str = "all",
        importance_min: Optional[int] = None,
        limit: int = 10,
        include_content: bool = False
    ) -> Dict[str, Any]:
        """
        在知识库中搜索相关的对话记录和解决方案
        
        实现三层搜索策略：
        1. 精确匹配层 - 标题和关键词的精确匹配
        2. 标签过滤层 - 基于技术标签的分类过滤
        3. 内容匹配层 - 对话内容的模糊匹配
        
        Args:
            query: 搜索查询关键词（必需）
            category: 内容分类过滤（可选）
            tags: 标签过滤列表（可选）
            time_range: 时间范围过滤 ("week", "month", "all")
            importance_min: 最小重要性等级 (1-5)
            limit: 返回结果数量限制 (1-50)
            include_content: 是否在结果中包含完整对话内容
            
        Returns:
            Dict[str, Any]: 搜索结果，包含：
                - results: 搜索结果列表
                - total: 总结果数量
                - search_time_ms: 搜索耗时（毫秒）
                - query: 原始查询
                - filters_applied: 应用的过滤条件
                - statistics: 详细搜索统计信息
                
        Raises:
            ValueError: 参数验证失败
            RuntimeError: 搜索执行失败
        """
        # 记录搜索开始时间
        start_time = time.time()
        
        try:
            # 1. 参数验证和预处理
            self._validate_search_params(query, category, tags, time_range, importance_min, limit)
            processed_query = self._preprocess_query(query)
            
            logger.info(f"开始搜索: '{processed_query}', 过滤条件: category={category}, tags={tags}")
            
            # 2. 检查缓存
            cache_key = self._generate_cache_key(processed_query, category, tags, time_range, importance_min, limit)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                logger.debug("命中搜索缓存")
                return cached_result
            
            # 3. 执行三层搜索策略
            search_results, stats = self._execute_multilayer_search(
                processed_query, category, tags, time_range, importance_min, limit, include_content
            )
            
            # 4. 计算搜索耗时
            search_time_ms = (time.time() - start_time) * 1000
            stats.search_time_ms = search_time_ms
            
            # 5. 构建返回结果
            result = {
                "results": [result.to_dict() for result in search_results],
                "total": stats.filtered_results,
                "search_time_ms": round(search_time_ms, 2),
                "query": query,
                "processed_query": processed_query,
                "filters_applied": {
                    "category": category,
                    "tags": tags,
                    "time_range": time_range,
                    "importance_min": importance_min,
                    "limit": limit
                },
                "statistics": {
                    "total_candidates": stats.total_candidates,
                    "after_filtering": stats.filtered_results,
                    "returned_count": stats.returned_results,
                    "index_operations": stats.index_hits,
                    "cache_hits": stats.cache_hits
                }
            }
            
            # 6. 缓存结果
            self._cache_result(cache_key, result)
            
            logger.info(f"搜索完成: 找到 {len(search_results)} 个结果，耗时 {search_time_ms:.2f}ms")
            return result
            
        except Exception as e:
            error_msg = f"搜索执行失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
    
    def _validate_search_params(
        self, query: str, category: Optional[str], tags: Optional[List[str]], 
        time_range: str, importance_min: Optional[int], limit: int
    ) -> None:
        """验证搜索参数"""
        if not query or not query.strip():
            raise ValueError("搜索查询不能为空")
        
        if len(query.strip()) < 2:
            raise ValueError("搜索查询至少需要2个字符")
        
        if limit < 1 or limit > 50:
            raise ValueError("结果数量限制必须在1-50之间")
        
        if time_range not in ["week", "month", "all"]:
            raise ValueError("时间范围必须是 'week', 'month' 或 'all'")
        
        if importance_min is not None and (importance_min < 1 or importance_min > 5):
            raise ValueError("最小重要性等级必须在1-5之间")
        
        if tags and len(tags) > 20:
            raise ValueError("标签过滤不能超过20个")
        
        if category and len(category) > 50:
            raise ValueError("分类名称不能超过50个字符")
    
    def _preprocess_query(self, query: str) -> str:
        """预处理查询字符串"""
        # 去除多余空格，转换为小写
        processed = ' '.join(query.strip().split()).lower()
        
        # 移除特殊字符但保留中文字符
        import string
        allowed_chars = set(string.ascii_letters + string.digits + string.whitespace + "中文字符范围")
        # 简化处理：保留字母、数字、空格和常见标点
        processed = ''.join(c for c in processed if c.isalnum() or c.isspace() or ord(c) > 127)
        
        return processed.strip()
    
    def _generate_cache_key(
        self, query: str, category: Optional[str], tags: Optional[List[str]], 
        time_range: str, importance_min: Optional[int], limit: int
    ) -> str:
        """生成搜索缓存键"""
        import hashlib
        
        # 构建缓存键组件
        components = [
            query,
            category or "",
            ",".join(sorted(tags or [])),
            time_range,
            str(importance_min or 0),
            str(limit)
        ]
        
        # 生成MD5哈希
        cache_key = hashlib.md5("|".join(components).encode()).hexdigest()
        return f"search_{cache_key}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存的搜索结果"""
        if cache_key not in self._search_cache:
            return None
        
        cached_item = self._search_cache[cache_key]
        cached_time = cached_item.get("cached_at", 0)
        
        # 检查缓存是否过期
        if time.time() - cached_time > self.cache_ttl:
            del self._search_cache[cache_key]
            return None
        
        # 更新统计信息
        result = cached_item["result"].copy()
        if "statistics" in result:
            result["statistics"]["cache_hits"] = result["statistics"].get("cache_hits", 0) + 1
        
        return result
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """缓存搜索结果"""
        try:
            # 简单的缓存大小控制
            if len(self._search_cache) > 100:
                # 删除最老的20%缓存项
                sorted_items = sorted(
                    self._search_cache.items(),
                    key=lambda x: x[1].get("cached_at", 0)
                )
                for key, _ in sorted_items[:20]:
                    del self._search_cache[key]
            
            self._search_cache[cache_key] = {
                "result": result,
                "cached_at": time.time()
            }
        except Exception as e:
            logger.warning(f"缓存搜索结果失败: {e}")
    
    def _execute_multilayer_search(
        self,
        query: str,
        category: Optional[str],
        tags: Optional[List[str]],
        time_range: str,
        importance_min: Optional[int],
        limit: int,
        include_content: bool
    ) -> Tuple[List[SearchResult], SearchStats]:
        """
        执行三层搜索策略
        
        Layer 1: 精确匹配 - 基于索引的关键词精确匹配
        Layer 2: 标签过滤 - 基于标签的分类过滤
        Layer 3: 内容匹配 - 基于内容的模糊匹配和相关性评分
        """
        stats = SearchStats(
            query_processed=query,
            search_time_ms=0,
            total_candidates=0,
            filtered_results=0,
            returned_results=0,
            index_hits=0,
            cache_hits=0
        )
        
        # Layer 1: 使用SearchIndexer进行基础搜索
        try:
            raw_results = self.indexer.search_conversations(
                query=query,
                tags=tags,
                category=category,
                time_range=time_range,
                importance_min=importance_min,
                limit=limit * 2  # 获取更多结果用于后续精细过滤
            )
            
            stats.total_candidates = len(raw_results)
            stats.index_hits = 1
            
            logger.debug(f"Layer 1 索引搜索返回 {len(raw_results)} 个候选结果")
            
        except Exception as e:
            logger.error(f"索引搜索失败: {e}")
            return [], stats
        
        # Layer 2: 增强结果处理和内容加载
        enhanced_results = []
        for raw_result in raw_results:
            try:
                # 加载完整对话内容用于内容匹配
                conversation = self.file_manager.load_conversation(raw_result["id"])
                if not conversation:
                    logger.warning(f"无法加载对话内容: {raw_result['id']}")
                    continue
                
                # Layer 3: 重新计算更精确的相关性分数
                enhanced_score = self._calculate_enhanced_relevance_score(
                    conversation, query, tags
                )
                
                # 过滤低相关性结果
                if enhanced_score < self.min_relevance_score:
                    continue
                
                # 创建增强的搜索结果
                search_result = self._create_search_result(
                    conversation, enhanced_score, query, include_content
                )
                enhanced_results.append(search_result)
                
            except Exception as e:
                logger.warning(f"处理搜索结果失败 {raw_result.get('id', 'unknown')}: {e}")
                continue
        
        # Layer 3: 按相关性分数排序并限制结果数量
        enhanced_results.sort(key=lambda x: x.match_score, reverse=True)
        final_results = enhanced_results[:limit]
        
        stats.filtered_results = len(enhanced_results)
        stats.returned_results = len(final_results)
        
        logger.debug(f"多层搜索完成: {stats.total_candidates} → {stats.filtered_results} → {stats.returned_results}")
        
        return final_results, stats
    
    def _calculate_enhanced_relevance_score(
        self,
        conversation: ConversationRecord,
        query: str,
        tags: Optional[List[str]]
    ) -> float:
        """
        计算增强的相关性分数
        
        基于以下因子的加权计算：
        - 精确匹配分数 (50%权重)
        - 标签匹配分数 (30%权重)  
        - 内容匹配分数 (20%权重)
        - 重要性加权 (5%权重)
        - 时间新鲜度加权 (5%权重)
        """
        total_score = 0.0
        query_words = set(self._tokenize_text(query))
        
        # 1. 精确匹配分数 (标题匹配)
        title_words = set(self._tokenize_text(conversation.title))
        title_matches = len(query_words.intersection(title_words))
        if title_matches > 0 and query_words:
            title_score = min(title_matches / len(query_words), 1.0)
            total_score += title_score * self.scoring_weights["exact_match"]
        
        # 2. 标签匹配分数
        if tags:
            conversation_tags = set(tag.lower() for tag in conversation.tags)
            search_tags = set(tag.lower() for tag in tags)
            tag_matches = len(search_tags.intersection(conversation_tags))
            if tag_matches > 0:
                tag_score = tag_matches / len(search_tags)
                total_score += tag_score * self.scoring_weights["tag_match"]
        
        # 3. 内容匹配分数 (摘要和内容匹配)
        content_text = f"{conversation.summary} {conversation.content[:500]}"
        content_words = set(self._tokenize_text(content_text))
        content_matches = len(query_words.intersection(content_words))
        if content_matches > 0 and query_words:
            content_score = min(content_matches / len(query_words), 1.0)
            total_score += content_score * self.scoring_weights["content_match"]
        
        # 4. 重要性加权
        importance_boost = (conversation.importance / 5.0) * self.scoring_weights["importance_boost"]
        total_score += importance_boost
        
        # 5. 时间新鲜度加权
        try:
            now = datetime.now()
            days_old = (now - conversation.created_at).days
            
            # 30天内的对话获得新鲜度加分
            if days_old <= 30:
                freshness_boost = ((30 - days_old) / 30.0) * self.scoring_weights["recency_boost"]
                total_score += freshness_boost
        except Exception:
            pass  # 忽略时间计算错误
        
        return min(total_score, 1.0)  # 确保分数不超过1.0
    
    def _tokenize_text(self, text: str) -> Set[str]:
        """文本分词（简化版本）"""
        if not text:
            return set()
        
        import string
        
        # 转换为小写并移除标点符号
        text = text.lower()
        text = text.translate(str.maketrans('', '', string.punctuation))
        
        # 分词
        words = text.split()
        
        # 过滤停用词和短词
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 
            'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'can', 'may', 'might'
        }
        
        filtered_words = set()
        for word in words:
            if len(word) >= 2 and word not in stop_words:
                filtered_words.add(word)
        
        return filtered_words
    
    def _create_search_result(
        self,
        conversation: ConversationRecord,
        score: float,
        query: str,
        include_content: bool
    ) -> SearchResult:
        """创建搜索结果对象"""
        # 生成智能摘要片段
        snippet = self._generate_smart_snippet(conversation, query)
        
        result = SearchResult(
            id=conversation.id,
            title=conversation.title,
            snippet=snippet,
            match_score=round(score, 3),
            created_at=conversation.created_at.isoformat(),
            tags=conversation.tags,
            category=conversation.category,
            importance=conversation.importance,
            type="conversation",
            content_length=len(conversation.content),
            solutions_count=len(conversation.solutions)
        )
        
        # 如果需要包含完整内容
        if include_content:
            result.full_content = conversation.content
        
        return result
    
    def _generate_smart_snippet(self, conversation: ConversationRecord, query: str) -> str:
        """生成智能摘要片段"""
        try:
            # 优先使用摘要
            if conversation.summary and len(conversation.summary.strip()) > 10:
                snippet = conversation.summary.strip()
                if len(snippet) <= self.max_snippet_length:
                    return snippet
                return snippet[:self.max_snippet_length - 3] + "..."
            
            # 从内容中查找包含查询关键词的段落
            query_words = self._tokenize_text(query)
            content_lines = conversation.content.split('\n')
            
            for line in content_lines:
                line = line.strip()
                if not line or len(line) < 20:
                    continue
                
                line_words = self._tokenize_text(line)
                if query_words.intersection(line_words):
                    if len(line) <= self.max_snippet_length:
                        return line
                    return line[:self.max_snippet_length - 3] + "..."
            
            # 使用内容开头作为备选
            if conversation.content:
                content_start = conversation.content.strip()
                if len(content_start) <= self.max_snippet_length:
                    return content_start
                return content_start[:self.max_snippet_length - 3] + "..."
            
            return f"对话记录 - {conversation.title}"
            
        except Exception as e:
            logger.warning(f"生成摘要片段失败: {e}")
            return f"对话记录 - {conversation.title}"
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """获取搜索工具统计信息"""
        try:
            index_stats = self.indexer.get_index_stats()
            
            return {
                "cache_size": len(self._search_cache),
                "cache_ttl_seconds": self.cache_ttl,
                "min_relevance_threshold": self.min_relevance_score,
                "max_snippet_length": self.max_snippet_length,
                "scoring_weights": self.scoring_weights,
                "index_statistics": index_stats,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取搜索统计信息失败: {e}")
            return {}
    
    def clear_cache(self) -> int:
        """清空搜索缓存"""
        cache_size = len(self._search_cache)
        self._search_cache.clear()
        logger.info(f"清空搜索缓存，共清理 {cache_size} 个缓存项")
        return cache_size
    
    def rebuild_search_index(self) -> bool:
        """重建搜索索引"""
        try:
            logger.info("开始重建搜索索引...")
            success = self.indexer.rebuild_index(self.file_manager)
            
            if success:
                # 清空缓存以确保使用新索引
                self.clear_cache()
                logger.info("搜索索引重建成功")
            else:
                logger.error("搜索索引重建失败")
            
            return success
            
        except Exception as e:
            logger.error(f"重建搜索索引异常: {e}")
            return False


# 为了向后兼容，定义SearchResult的to_dict方法
def _search_result_to_dict(self) -> Dict[str, Any]:
    """将SearchResult转换为字典"""
    result = {
        "id": self.id,
        "title": self.title,
        "snippet": self.snippet,
        "match_score": self.match_score,
        "created_at": self.created_at,
        "tags": self.tags,
        "category": self.category,
        "importance": self.importance,
        "type": self.type,
        "content_length": self.content_length,
        "solutions_count": self.solutions_count
    }
    
    # 如果有完整内容，也包含进去
    if hasattr(self, 'full_content'):
        result['full_content'] = self.full_content
    
    return result

# 将to_dict方法绑定到SearchResult类
SearchResult.to_dict = _search_result_to_dict