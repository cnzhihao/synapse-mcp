"""
智能上下文注入工具 for Synapse MCP

本模块实现了基于解决方案的智能上下文注入功能，为当前AI对话提供相关的代码片段、方法和模式。

核心功能：
1. 解决方案相关性计算 - 基于文本相似度、标签匹配、引用计数的多因子算法
2. 上下文选择和过滤 - 阈值过滤、去重优化、质量平衡
3. 解决方案格式化 - 生成针对性的代码片段和解决方案摘要
4. 引用计数追踪 - 自动跟踪解决方案的使用频率
5. 智能摘要生成 - 为注入的解决方案创建有意义的总结

技术特性：
- 解决方案导向的相关性评分算法
- 与解决方案搜索系统的深度集成
- 引用计数驱动的权重计算
- 高性能响应 (目标 < 500ms)
- 完整的错误处理和日志记录
- MCP协议标准兼容
"""

import logging
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from collections import Counter

from synapse.storage.paths import StoragePaths
from synapse.storage.file_manager import FileManager
from synapse.tools.search_knowledge import SearchKnowledgeTool
from synapse.models.conversation import Solution

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """上下文项数据结构 - 专门用于解决方案上下文"""
    solution_id: str
    solution_type: str  # code, approach, pattern
    language: Optional[str]
    description: str
    content: str
    relevance: float
    reusability_score: float
    reference_count: int
    last_referenced: Optional[str]
    tags: List[str]
    explanation: str  # 解释为什么这个解决方案相关
    
    # 向后兼容的属性
    @property
    def title(self) -> str:
        """向后兼容：返回描述作为标题"""
        return self.description
    
    @property
    def source_type(self) -> str:
        """向后兼容：返回固定的源类型"""
        return "solution"
    
    @property
    def source_id(self) -> str:
        """向后兼容：返回解决方案ID"""
        return self.solution_id




class InjectContextTool:
    """
    基于解决方案的智能上下文注入工具
    
    这个工具能够智能地分析当前用户查询，从提取的解决方案中找到最相关的代码片段、
    方法和模式，并将其格式化后注入到当前对话中，提升AI助手的代码理解和复用能力。
    
    主要功能：
    - 解决方案相关性计算：基于文本相似度、标签匹配、引用计数的评分算法
    - 引用计数追踪：自动跟踪解决方案的使用频率
    - 智能内容选择：去重、质量过滤、类型多样性平衡
    - 解决方案格式化：生成易于理解的代码片段和方法摘要
    - 性能优化：缓存和高效搜索策略
    
    使用示例:
        storage_paths = StoragePaths()
        file_manager = FileManager(storage_paths)
        search_tool = SearchKnowledgeTool(storage_paths, file_manager)
        inject_tool = InjectContextTool(storage_paths, file_manager, search_tool)
        
        result = inject_tool.inject_context(
            current_query="如何优化React hooks性能",
            max_items=3,
            relevance_threshold=0.7
        )
    """
    
    def __init__(self, storage_paths: StoragePaths, file_manager: FileManager, search_tool: SearchKnowledgeTool):
        """
        初始化上下文注入工具
        
        Args:
            storage_paths: 存储路径管理器
            file_manager: 文件管理器，用于访问存储的内容
            search_tool: 搜索工具，用于查找相关内容
        """
        self.storage_paths = storage_paths
        self.file_manager = file_manager
        self.search_tool = search_tool
        
        
        # 性能和质量配置
        self.max_content_length = 500  # 注入内容的最大长度
        self.min_snippet_length = 50   # 最小片段长度
        self.search_multiplier = 3      # 搜索数量倍数（用于候选池）
        
        logger.info("InjectContextTool 初始化完成")
    
    def inject_context(
        self, 
        current_query: str,
        max_items: int = 3,
        relevance_threshold: float = 0.7,
        include_solutions: bool = True,
        include_conversations: bool = True
    ) -> Dict[str, Any]:
        """
        为当前查询注入相关的解决方案上下文
        
        这是主要的解决方案上下文注入功能，它会：
        1. 分析当前查询的关键词和技术需求
        2. 搜索相关的解决方案（代码、方法、模式）
        3. 计算基于引用计数和质量的相关性评分
        4. 选择最佳的解决方案并跟踪引用计数
        5. 格式化并返回结果
        
        Args:
            current_query: 当前用户的查询或问题
            max_items: 最大注入的解决方案数量 (1-10)
            relevance_threshold: 相关性阈值 (0.0-1.0)
            include_solutions: 是否包含解决方案内容（保留兼容性）
            include_conversations: 已废弃，保留向后兼容性
            
        Returns:
            Dict: 包含上下文项和注入摘要的结果
            {
                "context_items": [...],
                "injection_summary": "...",
                "total_items": int,
                "query": str,
                "relevance_threshold": float,
                "processing_time_ms": float
            }
        """
        start_time = time.time()
        
        try:
            logger.info(f"开始为查询注入上下文: '{current_query[:100]}'")
            
            # 1. 参数验证
            self._validate_parameters(current_query, max_items, relevance_threshold)
            
            # 2. 查询预处理和关键词提取
            processed_query, keywords = self._preprocess_query(current_query)
            
            # 3. 搜索候选内容
            candidates = self._search_candidates(processed_query, keywords, max_items)
            
            # 4. 计算相关性评分
            scored_candidates = self._calculate_relevance_scores(
                current_query, keywords, candidates
            )
            
            # 5. 选择最佳上下文项
            selected_items = self._select_context_items(
                scored_candidates, max_items, relevance_threshold
            )
            
            # 6. 格式化上下文项
            context_items = self._format_context_items(selected_items)
            
            # 7. 生成注入摘要
            injection_summary = self._generate_injection_summary(
                current_query, context_items, relevance_threshold
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            result = {
                "context_items": [item.__dict__ for item in context_items],
                "injection_summary": injection_summary,
                "total_items": len(context_items),
                "query": current_query,
                "processed_query": processed_query,
                "keywords_extracted": keywords,
                "relevance_threshold": relevance_threshold,
                "processing_time_ms": round(processing_time, 2),
                "search_statistics": {
                    "candidates_found": len(candidates),
                    "scored_candidates": len(scored_candidates),
                    "above_threshold": len(selected_items),
                    "returned_items": len(context_items)
                }
            }
            
            logger.info(f"上下文注入完成: {len(context_items)} 项，耗时 {processing_time:.2f}ms")
            return result
            
        except Exception as e:
            error_msg = f"上下文注入失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # 返回错误结果而不是抛出异常
            return {
                "context_items": [],
                "injection_summary": f"注入失败: {error_msg}",
                "total_items": 0,
                "query": current_query,
                "error": error_msg,
                "processing_time_ms": (time.time() - start_time) * 1000
            }
    
    def _validate_parameters(self, current_query: str, max_items: int, relevance_threshold: float) -> None:
        """验证输入参数"""
        if not current_query or not current_query.strip():
            raise ValueError("当前查询不能为空")
        
        if not isinstance(max_items, int) or max_items < 1 or max_items > 10:
            raise ValueError("最大注入项数必须在1-10之间")
        
        if not isinstance(relevance_threshold, (int, float)) or relevance_threshold < 0.0 or relevance_threshold > 1.0:
            raise ValueError("相关性阈值必须在0.0-1.0之间")
    
    def _preprocess_query(self, query: str) -> Tuple[str, List[str]]:
        """
        预处理查询并提取关键词
        
        Args:
            query: 原始查询字符串
            
        Returns:
            Tuple[处理后的查询, 关键词列表]
        """
        # 清理查询
        processed = query.strip().lower()
        
        # 提取关键词（简单的基于空格和标点的分词）
        # 在实际应用中，可以使用更高级的NLP技术
        words = re.findall(r'\b\w+\b', processed)
        
        # 过滤停用词和短词
        stop_words = {'的', '了', '在', '是', '有', '和', '或', '但', '如果', '因为', '所以', 
                     'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
        
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        # 限制关键词数量，保留最重要的
        keywords = keywords[:10]  # 最多保留10个关键词
        
        logger.debug(f"查询预处理: '{query}' -> 关键词: {keywords}")
        return processed, keywords
    
    def _search_candidates(self, processed_query: str, keywords: List[str], max_items: int) -> List[Dict]:
        """
        搜索候选解决方案
        
        Args:
            processed_query: 处理后的查询
            keywords: 提取的关键词
            max_items: 所需的最大项数
            
        Returns:
            List[Dict]: 候选解决方案列表
        """
        candidates = []
        
        try:
            # 使用解决方案搜索，获取更多候选项
            search_limit = min(max_items * self.search_multiplier, 50)
            
            # 首先用完整查询搜索解决方案
            search_result = self.search_tool.search_knowledge(
                query=processed_query,
                search_in="all",
                limit=search_limit
            )
            
            # 处理简化的搜索结果格式
            if search_result and search_result.get("results"):
                candidates.extend(search_result["results"])
                logger.debug(f"解决方案搜索获得 {len(candidates)} 个候选项")
            
            # 如果候选项不够，使用关键词分别搜索
            if len(candidates) < search_limit and keywords:
                for keyword in keywords[:3]:  # 只用前3个最重要的关键词
                    keyword_result = self.search_tool.search_knowledge(
                        query=keyword,
                        search_in="all",
                        limit=10
                    )
                    
                    if keyword_result and keyword_result.get("results"):
                        # 添加新的候选项（去重）
                        existing_ids = {item.get("id") for item in candidates}
                        new_candidates = [
                            item for item in keyword_result["results"] 
                            if item.get("id") not in existing_ids
                        ]
                        candidates.extend(new_candidates)
                        
                        if len(candidates) >= search_limit:
                            break
            
            logger.debug(f"总共找到 {len(candidates)} 个候选项")
            return candidates[:search_limit]  # 限制候选项数量
            
        except Exception as e:
            logger.error(f"搜索候选内容失败: {str(e)}")
            return []
    
    def _calculate_relevance_scores(
        self, 
        original_query: str, 
        keywords: List[str], 
        candidates: List[Dict]
    ) -> List[Tuple[Dict, float]]:
        """
        简化的相关性评分 - 基于简单关键词匹配
        
        Args:
            original_query: 原始查询
            keywords: 提取的关键词
            candidates: 候选内容列表
            
        Returns:
            List[Tuple[候选项, 相关性评分]]: 带评分的候选项列表
        """
        scored_candidates = []
        
        for candidate in candidates:
            try:
                # 简单的关键词匹配评分
                score = self._simple_relevance_score(original_query, keywords, candidate)
                scored_candidates.append((candidate, score))
                
            except Exception as e:
                logger.warning(f"计算候选项相关性失败 {candidate.get('id', 'unknown')}: {str(e)}")
                continue
        
        # 按分数排序
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        logger.debug(f"完成相关性评分: {len(scored_candidates)} 个候选项")
        return scored_candidates
    
    def _simple_relevance_score(self, query: str, keywords: List[str], candidate: Dict) -> float:
        """简化的相关性评分 - 基于关键词匹配"""
        try:
            candidate_text = ""
            
            # 组合候选项的文本内容
            if candidate.get("title"):
                candidate_text += candidate["title"].lower() + " "
            if candidate.get("snippet"):
                candidate_text += candidate["snippet"].lower() + " "
            if candidate.get("description"):
                candidate_text += candidate["description"].lower() + " "
            
            # 计算关键词匹配数量
            matched_keywords = sum(1 for keyword in keywords if keyword.lower() in candidate_text)
            keyword_score = matched_keywords / max(len(keywords), 1) if keywords else 0
            
            # 计算查询词在候选项中的出现比例
            query_words = query.lower().split()
            matched_query_words = sum(1 for word in query_words if word in candidate_text)
            query_score = matched_query_words / max(len(query_words), 1)
            
            # 简单的加权平均
            final_score = (keyword_score * 0.6 + query_score * 0.4)
            
            # 基于创建时间的简单加成（新的内容加分）
            created_at = candidate.get("created_at")
            if created_at:
                try:
                    from datetime import datetime
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    days_old = (datetime.now(created_date.tzinfo) - created_date).days
                    if days_old < 30:
                        final_score += 0.1  # 新内容加分
                except:
                    pass
            
            return min(1.0, final_score)
            
        except Exception:
            return 0.0
    
    
    
    
    
    
    
    def _select_context_items(
        self, 
        scored_candidates: List[Tuple[Dict, float]], 
        max_items: int, 
        threshold: float
    ) -> List[Tuple[Dict, float]]:
        """
        选择最佳的上下文项
        
        选择策略：
        1. 分数必须超过阈值
        2. 去重相似内容
        3. 平衡不同类型的内容
        4. 优先选择高质量项
        
        Args:
            scored_candidates: 评分后的候选项列表
            max_items: 最大选择数量
            threshold: 相关性阈值
            
        Returns:
            List[Tuple[候选项, 评分]]: 选中的上下文项
        """
        selected = []
        seen_titles = set()
        
        for candidate, score in scored_candidates:
            # 检查是否达到阈值
            if score < threshold:
                continue
            
            # 检查是否已达到最大数量
            if len(selected) >= max_items:
                break
            
            # 简单的去重逻辑 - 检查标题相似性
            title = candidate.get("title", "").lower()
            title_words = set(title.split())
            
            # 检查与已选择项的相似性
            is_duplicate = False
            for seen_title in seen_titles:
                seen_words = set(seen_title.split())
                # 如果有超过60%的词重复，认为是重复内容
                if len(title_words & seen_words) / max(len(title_words | seen_words), 1) > 0.6:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                selected.append((candidate, score))
                seen_titles.add(title)
        
        logger.debug(f"从 {len(scored_candidates)} 个候选项中选择了 {len(selected)} 个上下文项")
        return selected
    
    def _format_context_items(self, selected_items: List[Tuple[Dict, float]]) -> List[ContextItem]:
        """
        格式化解决方案上下文项
        
        将解决方案搜索结果转换为标准的ContextItem格式，包括内容截取、解释生成和引用计数追踪
        
        Args:
            selected_items: 选中的候选解决方案和评分列表
            
        Returns:
            List[ContextItem]: 格式化后的解决方案上下文项列表
        """
        formatted_items = []
        
        for candidate, score in selected_items:
            try:
                # 准备内容 - 新的搜索格式使用snippet字段
                content = candidate.get("snippet", "")
                if len(content) > self.max_content_length:
                    content = content[:self.max_content_length] + "..."
                
                # 使用搜索提供的匹配原因，如果没有则生成简单解释
                explanation = candidate.get("match_reason", self._generate_simple_explanation(score))
                
                # 创建解决方案上下文项
                context_item = ContextItem(
                    solution_id=candidate.get("id", "unknown"),
                    solution_type=candidate.get("type", "unknown"),
                    language=candidate.get("language"),
                    description=candidate.get("title", "未知解决方案"),  # 新格式使用title字段
                    content=content,
                    relevance=round(score, 3),
                    reusability_score=candidate.get("reusability_score", 0.0),
                    reference_count=candidate.get("reference_count", 0),
                    last_referenced=candidate.get("last_referenced"),
                    tags=candidate.get("tags", []),
                    explanation=explanation
                )
                
                formatted_items.append(context_item)
                
                # 重要：跟踪引用计数
                self._track_solution_reference(candidate.get("id"))
                
            except Exception as e:
                logger.warning(f"格式化解决方案上下文项失败: {e}")
                continue
        
        return formatted_items
    
    def _generate_simple_explanation(self, score: float) -> str:
        """生成简化的相关性解释"""
        if score > 0.8:
            return "高度相关匹配"
        elif score > 0.6:
            return "较好相关匹配"
        elif score > 0.4:
            return "一般相关匹配"
        else:
            return "基础相关匹配"
    
    def _generate_injection_summary(self, query: str, context_items: List[ContextItem], threshold: float) -> str:
        """生成注入摘要"""
        if not context_items:
            return f"未找到与'{query}'相关性超过{threshold:.1%}的历史内容"
        
        # 统计信息
        total_items = len(context_items)
        avg_relevance = sum(item.relevance for item in context_items) / total_items if total_items > 0 else 0
        
        # 内容类型统计
        type_counts = Counter(item.source_type for item in context_items)
        type_summary = "、".join([f"{count}个{type_name}" for type_name, count in type_counts.items()])
        
        # 生成摘要
        summary = f"为查询'{query[:50]}'找到{total_items}个相关上下文（{type_summary}），平均相关性{avg_relevance:.1%}"
        
        if context_items:
            best_item = max(context_items, key=lambda x: x.relevance)
            summary += f"，最佳匹配：{best_item.title[:30]}（相关性{best_item.relevance:.1%}）"
        
        return summary
    
    def _track_solution_reference(self, solution_id: str) -> None:
        """
        跟踪解决方案引用计数
        
        当解决方案被注入到上下文中时调用此方法，会：
        1. 加载对应的解决方案对象
        2. 增加引用计数
        3. 更新最后引用时间
        4. 保存到文件系统
        
        Args:
            solution_id: 被引用的解决方案ID
        """
        if not solution_id or solution_id == "unknown":
            return
        
        try:
            # 加载解决方案
            solution = self.file_manager.load_solution(solution_id)
            if not solution:
                logger.warning(f"无法加载解决方案用于引用追踪: {solution_id}")
                return
            
            # 增加引用计数并更新时间
            solution.increment_reference()
            
            # 保存更新后的解决方案
            success = self.file_manager.save_solution(solution)
            if success:
                logger.debug(f"解决方案引用计数已更新: {solution_id} -> {solution.reference_count}")
            else:
                logger.warning(f"保存解决方案引用计数失败: {solution_id}")
                
        except Exception as e:
            logger.error(f"跟踪解决方案引用失败 {solution_id}: {e}")
            # 不抛出异常，避免影响主要功能