"""
智能上下文注入工具 for Synapse MCP

本模块实现了完整的历史上下文智能注入功能，为当前AI对话提供相关的历史知识和解决方案。

核心功能：
1. 智能相关性计算 - 基于文本相似度、标签匹配、质量评分的多因子算法
2. 上下文选择和过滤 - 阈值过滤、去重优化、内容长度平衡
3. 内容格式化 - 生成针对性的上下文摘要和代码片段
4. 质量评估 - 评估注入内容的质量和相关性
5. 智能摘要生成 - 为注入的上下文创建有意义的总结

技术特性：
- 多维度相关性评分算法
- 与现有搜索系统的深度集成
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
from synapse.models.conversation import ConversationRecord

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """上下文项数据结构"""
    title: str
    content: str
    relevance: float
    source_type: str
    source_id: str
    created_at: str
    tags: List[str]
    category: str
    importance: int
    explanation: str  # 解释为什么这个上下文相关


@dataclass
class RelevanceScore:
    """相关性评分详细信息"""
    total_score: float
    text_similarity: float
    tag_match: float
    recency_bonus: float
    importance_bonus: float
    quality_factor: float


class InjectContextTool:
    """
    智能上下文注入工具
    
    这个工具能够智能地分析当前用户查询，从历史对话和解决方案中找到最相关的内容，
    并将其格式化后注入到当前对话中，提升AI助手的上下文理解能力。
    
    主要功能：
    - 智能相关性计算：基于多种因素的相关性评分算法
    - 内容选择优化：去重、质量过滤、多样性平衡
    - 格式化输出：生成易于理解的上下文摘要
    - 性能优化：缓存和高效搜索策略
    
    使用示例:
        storage_paths = StoragePaths()
        file_manager = FileManager(storage_paths)
        search_tool = SearchKnowledgeTool(storage_paths, file_manager)
        inject_tool = InjectContextTool(storage_paths, file_manager, search_tool)
        
        result = inject_tool.inject_context(
            current_query="如何优化React组件性能",
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
        
        # 相关性计算权重配置
        self.relevance_weights = {
            'text_similarity': 0.4,    # 文本相似度权重
            'tag_match': 0.25,         # 标签匹配权重
            'recency_bonus': 0.15,     # 时间新鲜度权重
            'importance_bonus': 0.15,   # 重要性权重
            'quality_factor': 0.05     # 质量因子权重
        }
        
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
        为当前查询注入相关的历史上下文
        
        这是主要的上下文注入功能，它会：
        1. 分析当前查询的关键词和意图
        2. 搜索历史对话和解决方案
        3. 计算相关性评分
        4. 选择最佳的上下文项
        5. 格式化并返回结果
        
        Args:
            current_query: 当前用户的查询或问题
            max_items: 最大注入的上下文项数量 (1-10)
            relevance_threshold: 相关性阈值 (0.0-1.0)
            include_solutions: 是否包含解决方案内容
            include_conversations: 是否包含对话记录
            
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
        搜索候选内容
        
        Args:
            processed_query: 处理后的查询
            keywords: 提取的关键词
            max_items: 所需的最大项数
            
        Returns:
            List[Dict]: 候选内容列表
        """
        candidates = []
        
        try:
            # 使用关键词搜索，获取更多候选项
            search_limit = min(max_items * self.search_multiplier, 50)
            
            # 首先用完整查询搜索
            search_result = self.search_tool.search_knowledge(
                query=processed_query,
                limit=search_limit,
                include_content=True
            )
            
            if search_result and search_result.get("results"):
                candidates.extend(search_result["results"])
                logger.debug(f"完整查询搜索获得 {len(search_result['results'])} 个候选项")
            
            # 如果候选项不够，使用关键词分别搜索
            if len(candidates) < search_limit and keywords:
                for keyword in keywords[:3]:  # 只用前3个最重要的关键词
                    keyword_result = self.search_tool.search_knowledge(
                        query=keyword,
                        limit=10,
                        include_content=True
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
    ) -> List[Tuple[Dict, RelevanceScore]]:
        """
        计算每个候选项的相关性评分
        
        相关性评分算法包含以下因素：
        1. 文本相似度 (40%) - 基于关键词匹配和内容重叠
        2. 标签匹配 (25%) - 基于标签的相似度
        3. 时间新鲜度 (15%) - 较新的内容得分更高
        4. 重要性加成 (15%) - 高重要性的内容得分更高
        5. 质量因子 (5%) - 基于内容质量的调整
        
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
                # 1. 计算文本相似度
                text_sim = self._calculate_text_similarity(original_query, keywords, candidate)
                
                # 2. 计算标签匹配度
                tag_match = self._calculate_tag_match(keywords, candidate)
                
                # 3. 计算时间新鲜度加成
                recency_bonus = self._calculate_recency_bonus(candidate)
                
                # 4. 计算重要性加成
                importance_bonus = self._calculate_importance_bonus(candidate)
                
                # 5. 计算质量因子
                quality_factor = self._calculate_quality_factor(candidate)
                
                # 综合计算总分
                total_score = (
                    text_sim * self.relevance_weights['text_similarity'] +
                    tag_match * self.relevance_weights['tag_match'] +
                    recency_bonus * self.relevance_weights['recency_bonus'] +
                    importance_bonus * self.relevance_weights['importance_bonus'] +
                    quality_factor * self.relevance_weights['quality_factor']
                )
                
                # 确保分数在0-1之间
                total_score = max(0.0, min(1.0, total_score))
                
                score = RelevanceScore(
                    total_score=total_score,
                    text_similarity=text_sim,
                    tag_match=tag_match,
                    recency_bonus=recency_bonus,
                    importance_bonus=importance_bonus,
                    quality_factor=quality_factor
                )
                
                scored_candidates.append((candidate, score))
                
            except Exception as e:
                logger.warning(f"计算候选项相关性失败 {candidate.get('id', 'unknown')}: {str(e)}")
                continue
        
        # 按总分排序
        scored_candidates.sort(key=lambda x: x[1].total_score, reverse=True)
        
        logger.debug(f"完成相关性评分: {len(scored_candidates)} 个候选项")
        return scored_candidates
    
    def _calculate_text_similarity(self, query: str, keywords: List[str], candidate: Dict) -> float:
        """计算文本相似度"""
        try:
            candidate_text = ""
            
            # 组合候选项的文本内容
            if candidate.get("title"):
                candidate_text += candidate["title"].lower() + " "
            if candidate.get("snippet"):
                candidate_text += candidate["snippet"].lower() + " "
            
            # 计算关键词匹配数量
            matched_keywords = sum(1 for keyword in keywords if keyword.lower() in candidate_text)
            keyword_ratio = matched_keywords / max(len(keywords), 1)
            
            # 计算查询词在候选项中的出现比例
            query_words = query.lower().split()
            matched_query_words = sum(1 for word in query_words if word in candidate_text)
            query_ratio = matched_query_words / max(len(query_words), 1)
            
            # 综合计算文本相似度
            similarity = (keyword_ratio * 0.6 + query_ratio * 0.4)
            
            return min(1.0, similarity)
            
        except Exception:
            return 0.0
    
    def _calculate_tag_match(self, keywords: List[str], candidate: Dict) -> float:
        """计算标签匹配度"""
        try:
            candidate_tags = candidate.get("tags", [])
            if not candidate_tags:
                return 0.0
            
            # 计算关键词与标签的匹配
            matched_tags = sum(1 for keyword in keywords for tag in candidate_tags 
                             if keyword.lower() in tag.lower() or tag.lower() in keyword.lower())
            
            tag_ratio = matched_tags / max(len(candidate_tags), 1)
            return min(1.0, tag_ratio)
            
        except Exception:
            return 0.0
    
    def _calculate_recency_bonus(self, candidate: Dict) -> float:
        """计算时间新鲜度加成"""
        try:
            created_at_str = candidate.get("created_at")
            if not created_at_str:
                return 0.5  # 默认中等值
            
            # 解析创建时间
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            now = datetime.now(created_at.tzinfo)
            
            # 计算天数差
            days_old = (now - created_at).days
            
            # 新鲜度衰减函数（30天内线性衰减，之后保持最小值）
            if days_old <= 30:
                recency = 1.0 - (days_old / 30) * 0.5  # 30天内从1.0衰减到0.5
            else:
                recency = 0.3  # 超过30天的内容给予固定的低分
            
            return max(0.0, recency)
            
        except Exception:
            return 0.5  # 默认中等值
    
    def _calculate_importance_bonus(self, candidate: Dict) -> float:
        """计算重要性加成"""
        try:
            importance = candidate.get("importance", 3)  # 默认重要性为3
            # 将1-5的重要性转换为0-1的分数
            return (importance - 1) / 4.0
            
        except Exception:
            return 0.5  # 默认中等值
    
    def _calculate_quality_factor(self, candidate: Dict) -> float:
        """计算质量因子"""
        try:
            quality = 0.5  # 基础质量分数
            
            # 根据内容长度调整质量
            snippet = candidate.get("snippet", "")
            if len(snippet) > 100:
                quality += 0.2  # 内容丰富加分
            elif len(snippet) < 30:
                quality -= 0.2  # 内容太少扣分
            
            # 根据标签数量调整质量
            tags = candidate.get("tags", [])
            if len(tags) >= 3:
                quality += 0.1  # 标签丰富加分
            elif len(tags) == 0:
                quality -= 0.1  # 无标签扣分
            
            return max(0.0, min(1.0, quality))
            
        except Exception:
            return 0.5  # 默认中等值
    
    def _select_context_items(
        self, 
        scored_candidates: List[Tuple[Dict, RelevanceScore]], 
        max_items: int, 
        threshold: float
    ) -> List[Tuple[Dict, RelevanceScore]]:
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
            if score.total_score < threshold:
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
    
    def _format_context_items(self, selected_items: List[Tuple[Dict, RelevanceScore]]) -> List[ContextItem]:
        """
        格式化上下文项
        
        将搜索结果转换为标准的ContextItem格式，包括内容截取和解释生成
        
        Args:
            selected_items: 选中的候选项和评分列表
            
        Returns:
            List[ContextItem]: 格式化后的上下文项列表
        """
        formatted_items = []
        
        for candidate, score in selected_items:
            try:
                # 准备内容
                content = candidate.get("snippet", candidate.get("content", ""))
                if len(content) > self.max_content_length:
                    content = content[:self.max_content_length] + "..."
                
                # 生成相关性解释
                explanation = self._generate_relevance_explanation(score)
                
                # 创建上下文项
                context_item = ContextItem(
                    title=candidate.get("title", "未知标题"),
                    content=content,
                    relevance=round(score.total_score, 3),
                    source_type=candidate.get("type", "conversation"),
                    source_id=candidate.get("id", "unknown"),
                    created_at=candidate.get("created_at", ""),
                    tags=candidate.get("tags", []),
                    category=candidate.get("category", "general"),
                    importance=candidate.get("importance", 3),
                    explanation=explanation
                )
                
                formatted_items.append(context_item)
                
            except Exception as e:
                logger.warning(f"格式化上下文项失败: {str(e)}")
                continue
        
        return formatted_items
    
    def _generate_relevance_explanation(self, score: RelevanceScore) -> str:
        """生成相关性解释"""
        explanations = []
        
        if score.text_similarity > 0.7:
            explanations.append("高文本相似度")
        elif score.text_similarity > 0.4:
            explanations.append("中等文本相似度")
        
        if score.tag_match > 0.5:
            explanations.append("标签匹配良好")
        
        if score.importance_bonus > 0.6:
            explanations.append("高重要性内容")
        
        if score.recency_bonus > 0.8:
            explanations.append("近期内容")
        
        if not explanations:
            explanations.append("基础相关性匹配")
        
        return "、".join(explanations)
    
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