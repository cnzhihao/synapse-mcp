"""
AI语义搜索工具 for Synapse MCP

本模块实现了基于AI语义理解的知识库搜索功能，完全替换了传统的关键词匹配搜索。

核心功能：
1. AI语义搜索 - 利用调用方AI的语义理解能力进行智能搜索
2. 候选数据组织 - 将对话按重要性、时间、标签等维度分类组织
3. 智能指令生成 - 为AI生成清晰的搜索任务指令
4. 高效数据处理 - 只加载必要的元数据，避免性能问题

技术特性：
- 无需复杂的分词和索引系统
- 支持自然语言查询
- 理解同义词和语义相关性
- 智能候选数量控制
- 完整的错误处理和日志记录
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from synapse.storage.paths import StoragePaths
from synapse.storage.file_manager import FileManager
from synapse.models.conversation import ConversationRecord

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ConversationMetadata:
    """对话元数据结构"""
    id: str
    title: str
    summary: str
    tags: List[str]
    category: str
    importance: int
    created_at: str
    updated_at: str
    content_length: int
    solutions_count: int


class SearchKnowledgeTool:
    """
    AI语义搜索工具
    
    利用调用方AI的语义理解能力进行智能搜索，完全替换传统的关键词匹配。
    
    工作流程：
    1. 获取所有对话列表
    2. 应用基础过滤条件（时间、分类、重要性等）
    3. 按优先级分类组织候选数据
    4. 生成AI任务指令
    5. 返回结构化数据供AI进行语义匹配
    
    使用示例：
        storage_paths = StoragePaths()
        file_manager = FileManager(storage_paths)
        search_tool = SearchKnowledgeTool(storage_paths, file_manager)
        
        result = search_tool.search_knowledge(
            query="React性能优化",
            limit=10
        )
    """
    
    def __init__(self, storage_paths: StoragePaths, file_manager: FileManager):
        """
        初始化AI语义搜索工具
        
        Args:
            storage_paths: 存储路径管理器
            file_manager: 文件管理器，用于加载对话内容
        """
        self.storage_paths = storage_paths
        self.file_manager = file_manager
        
        # 配置参数
        self.max_candidates = 100  # 最大候选数量
        self.recent_days_threshold = 30  # 最近对话的天数阈值
        self.high_importance_threshold = 4  # 高重要性阈值
        
        # 缓存配置
        self.cache_ttl = 300  # 缓存生存时间5分钟
        self._conversation_cache = {}  # 对话列表缓存
        self._metadata_cache = {}  # 对话元数据缓存
        self._search_result_cache = {}  # 搜索结果缓存
        
        logger.info("AI语义搜索工具初始化完成（已启用缓存）")
    
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
        执行AI语义搜索
        
        Args:
            query: 搜索查询（必需）
            category: 内容分类过滤（可选）
            tags: 标签过滤列表（可选）
            time_range: 时间范围过滤 ("week", "month", "all")
            importance_min: 最小重要性等级 (1-5)
            limit: 期望返回的结果数量
            include_content: 是否在候选中包含内容预览
            
        Returns:
            Dict[str, Any]: AI语义搜索的结构化数据
        """
        start_time = time.time()
        
        try:
            logger.info(f"开始AI语义搜索: '{query}'")
            
            # 1. 参数验证
            self._validate_search_params(query, limit)
            
            # 2. 获取所有对话列表（使用缓存）
            all_conversations = self._get_cached_conversations()
            if all_conversations is None:
                all_conversations = self.file_manager.list_conversations()
                self._cache_conversations(all_conversations)
                logger.debug(f"获取到 {len(all_conversations)} 个对话（已缓存）")
            else:
                logger.debug(f"获取到 {len(all_conversations)} 个对话（缓存命中）")
            
            # 3. 应用基础过滤条件
            filtered_conversations = self._apply_basic_filters(
                all_conversations, category, tags, time_range, importance_min
            )
            logger.debug(f"过滤后剩余 {len(filtered_conversations)} 个对话")
            
            # 4. 限制候选数量
            limited_conversations = self._limit_candidates(filtered_conversations)
            logger.debug(f"限制后保留 {len(limited_conversations)} 个候选")
            
            # 5. 组织候选数据
            candidate_categories = self._organize_candidates(
                limited_conversations, include_content
            )
            
            # 6. 生成AI任务指令
            ai_instruction = self._generate_ai_instruction(query, candidate_categories, limit)
            
            # 7. 计算处理时间
            processing_time = (time.time() - start_time) * 1000
            
            # 8. 构建返回结果
            result = {
                "search_mode": "ai_semantic",
                "query": query,
                "total_candidates": len(limited_conversations),
                "candidates_before_filter": len(all_conversations),
                "candidate_categories": candidate_categories,
                "ai_task": ai_instruction,
                "filters_applied": {
                    "category": category,
                    "tags": tags,
                    "time_range": time_range,
                    "importance_min": importance_min,
                    "limit": limit
                },
                "metadata": {
                    "processing_time_ms": round(processing_time, 2),
                    "include_content_preview": include_content,
                    "max_candidates_limit": self.max_candidates
                }
            }
            
            logger.info(f"AI语义搜索完成: {len(limited_conversations)} 个候选，耗时 {processing_time:.2f}ms")
            return result
            
        except Exception as e:
            error_msg = f"AI语义搜索失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
    
    def _validate_search_params(self, query: str, limit: int) -> None:
        """验证搜索参数"""
        if not query or not query.strip():
            raise ValueError("搜索查询不能为空")
        
        if len(query.strip()) < 2:
            raise ValueError("搜索查询至少需要2个字符")
        
        if limit < 1 or limit > 50:
            raise ValueError("结果数量限制必须在1-50之间")
    
    def _apply_basic_filters(
        self,
        conversations: List[str],
        category: Optional[str],
        tags: Optional[List[str]], 
        time_range: str,
        importance_min: Optional[int]
    ) -> List[str]:
        """
        应用基础过滤条件
        
        Args:
            conversations: 所有对话ID列表
            category: 分类过滤
            tags: 标签过滤
            time_range: 时间范围过滤
            importance_min: 最小重要性过滤
            
        Returns:
            List[str]: 过滤后的对话ID列表
        """
        filtered = []
        
        for conv_id in conversations:
            try:
                # 加载对话元数据（使用缓存）
                cached_metadata = self._get_cached_metadata(conv_id)
                if cached_metadata:
                    conversation = cached_metadata
                else:
                    conversation = self.file_manager.load_conversation(conv_id)
                    if not conversation:
                        continue
                    # 缓存元数据  
                    metadata_dict = {
                        'category': conversation.category,
                        'importance': conversation.importance,
                        'tags': conversation.tags,
                        'created_at': conversation.created_at
                    }
                    self._cache_metadata(conv_id, metadata_dict)
                    conversation = metadata_dict
                
                # 分类过滤
                if category and conversation['category'] != category:
                    continue
                
                # 重要性过滤
                if importance_min and conversation['importance'] < importance_min:
                    continue
                
                # 标签过滤
                if tags and not any(tag.lower() in [t.lower() for t in conversation['tags']] for tag in tags):
                    continue
                
                # 时间范围过滤
                if not self._matches_time_range(conversation['created_at'], time_range):
                    continue
                
                filtered.append(conv_id)
                
            except Exception as e:
                logger.warning(f"处理对话 {conv_id} 时出错: {e}")
                continue
        
        return filtered
    
    def _matches_time_range(self, created_at: datetime, time_range: str) -> bool:
        """检查对话是否在指定时间范围内"""
        if time_range == "all":
            return True
        
        try:
            now = datetime.now()
            days_diff = (now - created_at).days
            
            if time_range == "week":
                return days_diff <= 7
            elif time_range == "month":
                return days_diff <= 30
            else:
                return True
                
        except Exception:
            return True
    
    def _limit_candidates(self, conversations: List[str]) -> List[str]:
        """
        限制候选数量，避免AI输入过长
        
        优先级排序：重要性高 > 时间新 > 其他
        """
        if len(conversations) <= self.max_candidates:
            return conversations
        
        # 加载元数据进行优先级排序
        conversation_priorities = []
        for conv_id in conversations:
            try:
                conversation = self.file_manager.load_conversation(conv_id)
                if conversation:
                    # 计算优先级分数
                    priority_score = self._calculate_priority_score(conversation)
                    conversation_priorities.append((conv_id, priority_score))
            except Exception as e:
                logger.warning(f"计算优先级时处理对话 {conv_id} 失败: {e}")
                continue
        
        # 按优先级排序并取前N个
        conversation_priorities.sort(key=lambda x: x[1], reverse=True)
        return [conv_id for conv_id, _ in conversation_priorities[:self.max_candidates]]
    
    def _calculate_priority_score(self, conversation: ConversationRecord) -> float:
        """
        计算对话的优先级分数
        
        考虑因素：
        - 重要性 (40%权重)
        - 时间新鲜度 (30%权重)
        - 内容丰富度 (20%权重)
        - 解决方案数量 (10%权重)
        """
        score = 0.0
        
        # 重要性分数 (0-1)
        importance_score = conversation.importance / 5.0
        score += importance_score * 0.4
        
        # 时间新鲜度分数 (0-1)
        try:
            days_old = (datetime.now() - conversation.created_at).days
            freshness_score = max(0, (365 - days_old) / 365)  # 一年内的对话
            score += freshness_score * 0.3
        except:
            score += 0.1  # 默认分数
        
        # 内容丰富度分数 (0-1)
        content_length = len(conversation.content)
        richness_score = min(1.0, content_length / 1000)  # 1000字符为满分
        score += richness_score * 0.2
        
        # 解决方案数量分数 (0-1)
        solutions_score = min(1.0, len(conversation.solutions) / 5)  # 5个解决方案为满分
        score += solutions_score * 0.1
        
        return score
    
    def _organize_candidates(
        self,
        conversation_ids: List[str], 
        include_content: bool = False
    ) -> Dict[str, List[Dict]]:
        """
        将候选对话按类型分类组织
        
        分类维度：
        - high_importance: 高重要性对话 (重要性>=4)
        - recent_discussions: 最近对话 (30天内)
        - tagged_content: 有标签的对话
        - general_conversations: 一般对话
        """
        categories = {
            "high_importance": [],
            "recent_discussions": [],
            "tagged_content": [],
            "general_conversations": []
        }
        
        for conv_id in conversation_ids:
            try:
                conversation = self.file_manager.load_conversation(conv_id)
                if not conversation:
                    continue
                
                # 构建候选信息
                candidate_info = self._build_candidate_info(conversation, include_content)
                
                # 分类逻辑
                if conversation.importance >= self.high_importance_threshold:
                    categories["high_importance"].append(candidate_info)
                elif self._is_recent_conversation(conversation.created_at):
                    categories["recent_discussions"].append(candidate_info)
                elif conversation.tags and any(tag.strip() for tag in conversation.tags):
                    categories["tagged_content"].append(candidate_info)
                else:
                    categories["general_conversations"].append(candidate_info)
                    
            except Exception as e:
                logger.warning(f"组织候选数据时处理对话 {conv_id} 失败: {e}")
                continue
        
        return categories
    
    def _build_candidate_info(
        self, 
        conversation: ConversationRecord, 
        include_content: bool = False
    ) -> Dict[str, Any]:
        """构建候选对话的信息字典"""
        info = {
            "id": conversation.id,
            "title": conversation.title,
            "summary": conversation.summary,
            "tags": conversation.tags,
            "category": conversation.category,
            "importance": conversation.importance,
            "created_at": conversation.created_at.isoformat(),
            "content_length": len(conversation.content),
            "solutions_count": len(conversation.solutions)
        }
        
        if include_content:
            # 只包含内容的前300个字符作为预览
            content_preview = conversation.content[:300]
            if len(conversation.content) > 300:
                content_preview += "..."
            info["content_preview"] = content_preview
        
        return info
    
    def _is_recent_conversation(self, created_at: datetime) -> bool:
        """判断是否为最近的对话"""
        try:
            days_old = (datetime.now() - created_at).days
            return days_old <= self.recent_days_threshold
        except:
            return False
    
    def _generate_ai_instruction(
        self, 
        query: str, 
        categories: Dict[str, List[Dict]], 
        limit: int
    ) -> str:
        """
        为AI生成清晰的搜索任务指令
        """
        total_candidates = sum(len(cat) for cat in categories.values())
        
        instruction = f"""请根据查询 "{query}" 从以下 {total_candidates} 个候选对话中进行语义匹配和筛选：

🌟 **高重要性对话** ({len(categories['high_importance'])}个)
重要性评分 ≥ 4 的对话，通常包含重要的技术解决方案和深度讨论：
{self._format_candidates_for_display(categories['high_importance'])}

🕒 **最近讨论** ({len(categories['recent_discussions'])}个)  
最近30天内的对话，可能包含最新的技术趋势和问题：
{self._format_candidates_for_display(categories['recent_discussions'])}

🏷️ **标签相关** ({len(categories['tagged_content'])}个)
带有技术标签的对话，便于技术主题匹配：
{self._format_candidates_for_display(categories['tagged_content'])}

📝 **一般对话** ({len(categories['general_conversations'])}个)
其他一般对话：
{self._format_candidates_for_display(categories['general_conversations'])}

**任务要求：**
1. 根据语义相关性选择最符合查询 "{query}" 的 {limit} 个对话
2. 优先考虑：
   - 标题和内容与查询语义高度相关的对话
   - 高重要性且主题相关的对话
   - 技术标签匹配的专业讨论
   - 最近的相关讨论
3. 请直接返回选中对话的完整信息，按相关性排序
4. 简要解释每个选择的理由

请开始语义匹配和筛选。"""
        
        return instruction
    
    def _format_candidates_for_display(self, candidates: List[Dict]) -> str:
        """将候选对话格式化为易读的显示格式"""
        if not candidates:
            return "  (无)"
        
        formatted = []
        for i, candidate in enumerate(candidates, 1):
            tags_str = ", ".join(candidate["tags"]) if candidate["tags"] else "无标签"
            
            formatted.append(f"""  {i}. 【{candidate['title']}】
     ID: {candidate['id']}
     摘要: {candidate['summary'][:100]}{'...' if len(candidate['summary']) > 100 else ''}
     标签: {tags_str}
     重要性: {candidate['importance']}/5
     时间: {candidate['created_at'][:10]}""")
        
        return "\n".join(formatted)
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """获取搜索工具统计信息"""
        try:
            all_conversations = self.file_manager.list_conversations()
            
            return {
                "search_mode": "ai_semantic",
                "total_conversations": len(all_conversations),
                "max_candidates_limit": self.max_candidates,
                "recent_days_threshold": self.recent_days_threshold,
                "high_importance_threshold": self.high_importance_threshold,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取搜索统计信息失败: {e}")
            return {
                "search_mode": "ai_semantic",
                "error": str(e)
            }
    
    def _generate_cache_key(self, query: str, category: Optional[str], tags: Optional[List[str]], 
                           time_range: str, importance_min: Optional[int], limit: int, 
                           include_content: bool) -> str:
        """生成搜索缓存键"""
        import hashlib
        
        components = [
            query.strip().lower(),
            category or "",
            ",".join(sorted(tags or [])),
            time_range,
            str(importance_min or 0),
            str(limit),
            str(include_content)
        ]
        
        cache_key = hashlib.md5("|".join(components).encode()).hexdigest()
        return f"search_{cache_key}"
    
    def _get_cached_conversations(self) -> Optional[List[str]]:
        """获取缓存的对话列表"""
        cache_key = "conversations_list"
        if cache_key not in self._conversation_cache:
            return None
        
        cached_item = self._conversation_cache[cache_key]
        cached_time = cached_item.get("cached_at", 0)
        
        # 检查缓存是否过期
        if time.time() - cached_time > self.cache_ttl:
            del self._conversation_cache[cache_key]
            return None
        
        return cached_item["conversations"]
    
    def _cache_conversations(self, conversations: List[str]) -> None:
        """缓存对话列表"""
        cache_key = "conversations_list"
        self._conversation_cache[cache_key] = {
            "conversations": conversations,
            "cached_at": time.time()
        }
    
    def _get_cached_metadata(self, conv_id: str) -> Optional[Dict]:
        """获取缓存的对话元数据"""
        if conv_id not in self._metadata_cache:
            return None
        
        cached_item = self._metadata_cache[conv_id]
        cached_time = cached_item.get("cached_at", 0)
        
        # 检查缓存是否过期
        if time.time() - cached_time > self.cache_ttl:
            del self._metadata_cache[conv_id]
            return None
        
        return cached_item["metadata"]
    
    def _cache_metadata(self, conv_id: str, metadata: Dict) -> None:
        """缓存对话元数据"""
        self._metadata_cache[conv_id] = {
            "metadata": metadata,
            "cached_at": time.time()
        }
        
        # 简单的缓存大小控制
        if len(self._metadata_cache) > 200:
            # 清理最旧的50个缓存项
            sorted_items = sorted(
                self._metadata_cache.items(),
                key=lambda x: x[1].get("cached_at", 0)
            )
            for key, _ in sorted_items[:50]:
                del self._metadata_cache[key]
    
    def clear_cache(self) -> Dict[str, int]:
        """清空所有缓存"""
        stats = {
            "conversations_cache": len(self._conversation_cache),
            "metadata_cache": len(self._metadata_cache), 
            "search_result_cache": len(self._search_result_cache)
        }
        
        self._conversation_cache.clear()
        self._metadata_cache.clear()
        self._search_result_cache.clear()
        
        logger.info(f"已清空缓存: {stats}")
        return stats