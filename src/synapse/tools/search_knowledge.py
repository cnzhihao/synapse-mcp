"""
简化的解决方案grep搜索工具 for Synapse MCP

根据重构计划，将复杂的评分算法替换为简单的grep搜索，让AI负责语义理解和关键词生成。

核心功能：
1. 简单grep搜索 - 在指定字段中搜索关键词
2. 时间排序 - 按创建时间倒序排列
3. AI搜索建议 - 为AI提供后续搜索建议
4. 清晰的匹配原因说明

技术特性：
- 极简的grep逻辑，易于理解和调试
- 响应速度 < 100ms
- 支持多字段搜索（title/content/tags/all）
- AI友好的搜索建议系统
"""

import logging
import time
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from synapse.storage.paths import StoragePaths
from synapse.storage.file_manager import FileManager
from synapse.models.conversation import Solution

# 配置日志
logger = logging.getLogger(__name__)


class SearchKnowledgeTool:
    """
    简化的解决方案grep搜索工具
    
    专门执行简单的文本搜索，让AI负责语义理解和关键词生成。
    
    工作流程：
    1. AI分析用户问题，生成搜索关键词
    2. 工具执行简单的grep搜索
    3. 按时间排序返回结果
    4. 提供AI后续搜索建议
    
    使用示例：
        storage_paths = StoragePaths()
        file_manager = FileManager(storage_paths)
        search_tool = SearchKnowledgeTool(storage_paths, file_manager)
        
        result = search_tool.search_knowledge(
            query="Python async exception",
            search_in="all",
            limit=10
        )
    """
    
    def __init__(self, storage_paths: StoragePaths, file_manager: FileManager):
        """
        初始化简化的搜索工具
        
        Args:
            storage_paths: 存储路径管理器
            file_manager: 文件管理器，用于加载解决方案内容
        """
        self.storage_paths = storage_paths
        self.file_manager = file_manager
        
        # 简化的配置参数
        self.max_results = 50  # 最大结果数量
        self.content_preview_length = 200  # 内容预览长度
        
        logger.info("SimplifiedSearchKnowledgeTool 初始化完成")
    
    def search_knowledge(
        self,
        query: str,
        search_in: str = "all",  # "title" | "content" | "tags" | "all"
        limit: int = 10
    ) -> dict:
        """
        简单grep搜索工具 - 让AI提供关键词，工具负责搜索
        
        🤖 AI使用建议：
        - 根据用户问题生成多个不同的关键词进行搜索
        - 尝试中英文、技术术语的不同表达方式
        - 建议连续搜索2-3次不同关键词以提高召回率
        
        示例用法：
        用户问："Python异步编程错误处理"
        AI应该搜索：
        1. "Python async exception"
        2. "异步 错误处理"  
        3. "asyncio try except"
        
        Args:
            query: 搜索关键词（由AI理解用户问题后生成）
            search_in: 搜索范围（title/content/tags/all）
            limit: 返回结果数量 (1-50)
            
        Returns:
            dict: 搜索结果
            {
                "query": "用户输入的关键词",
                "total_found": 5,
                "search_area": "content",
                "results": [
                    {
                        "id": "sol_001",
                        "title": "...",
                        "snippet": "匹配内容片段...",
                        "created_at": "2024-01-01T12:00:00Z",
                        "match_reason": "标题匹配 'async'"
                    }
                ],
                "suggestion": "建议AI尝试搜索其他相关关键词如 'asyncio', '异步编程'"
            }
        """
        start_time = time.time()
        
        try:
            logger.info(f"简化grep搜索: '{query}' in {search_in}")
            
            # 参数验证
            if not query or not query.strip():
                raise ValueError("搜索查询不能为空")
            
            if limit < 1 or limit > 50:
                raise ValueError("limit必须在1-50之间")
                
            if search_in not in ["title", "content", "tags", "all"]:
                raise ValueError("search_in必须是 'title', 'content', 'tags', 'all' 之一")
            
            # 加载所有解决方案
            all_solutions = self._load_solutions()
            logger.debug(f"加载了 {len(all_solutions)} 个解决方案")
            
            # 执行简单grep搜索
            results = self._simple_grep_search(query.strip().lower(), search_in, all_solutions)
            
            # 按时间倒序排列，最新的优先
            results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            # 限制结果数量
            results = results[:limit]
            
            processing_time = (time.time() - start_time) * 1000
            
            # 生成AI后续搜索建议
            suggestion = self._generate_search_suggestion(query, len(results))
            
            return {
                "query": query,
                "total_found": len(results),
                "search_area": search_in,
                "results": results,
                "suggestion": suggestion,
                "processing_time_ms": round(processing_time, 2)
            }
            
        except Exception as e:
            error_msg = f"搜索失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "query": query,
                "total_found": 0,
                "search_area": search_in,
                "results": [],
                "error": error_msg,
                "processing_time_ms": (time.time() - start_time) * 1000
            }
    
    def _load_solutions(self) -> List[Solution]:
        """加载所有解决方案"""
        try:
            return self.file_manager.load_all_solutions()
        except Exception as e:
            logger.warning(f"加载解决方案失败: {e}")
            return []
    
    def _simple_grep_search(self, query: str, search_in: str, solutions: List[Solution]) -> List[Dict]:
        """
        执行简单的grep搜索 - 核心搜索逻辑
        
        Args:
            query: 小写的搜索查询
            search_in: 搜索范围
            solutions: 解决方案列表
            
        Returns:
            List[Dict]: 匹配的结果列表
        """
        results = []
        search_terms = query.split()  # 将查询分解为多个词
        
        for solution in solutions:
            try:
                match_info = self._check_solution_match(solution, search_terms, search_in)
                if match_info:
                    result = {
                        "id": solution.id,
                        "title": solution.description,
                        "snippet": self._generate_snippet(solution, search_terms),
                        "type": solution.type,
                        "language": solution.language,
                        "created_at": solution.to_dict().get("created_at", ""),
                        "reference_count": solution.reference_count,
                        "reusability_score": solution.reusability_score,
                        "match_reason": match_info["reason"]
                    }
                    results.append(result)
                    
            except Exception as e:
                logger.warning(f"处理解决方案 {solution.id} 时出错: {e}")
                continue
        
        logger.debug(f"grep搜索找到 {len(results)} 个匹配项")
        return results
    
    def _check_solution_match(self, solution: Solution, search_terms: List[str], search_in: str) -> Optional[Dict]:
        """
        检查解决方案是否匹配搜索词
        
        Returns:
            Dict: 匹配信息，包含原因；如果不匹配返回None
        """
        match_reasons = []
        
        # 构建搜索文本
        search_texts = {}
        
        if search_in in ["title", "all"]:
            search_texts["title"] = solution.description.lower()
        
        if search_in in ["content", "all"]:
            search_texts["content"] = solution.content.lower()
        
        if search_in in ["tags", "all"]:
            search_texts["tags"] = " ".join(solution.tags).lower() if solution.tags else ""
        
        # 检查每个搜索区域
        for area, text in search_texts.items():
            for term in search_terms:
                if term in text:
                    match_reasons.append(f"{area}匹配 '{term}'")
        
        if match_reasons:
            return {"reason": "、".join(match_reasons)}
        
        return None
    
    def _generate_snippet(self, solution: Solution, search_terms: List[str]) -> str:
        """生成包含搜索词的内容片段"""
        content = solution.content
        
        # 寻找第一个匹配的搜索词位置
        first_match_pos = len(content)
        for term in search_terms:
            pos = content.lower().find(term)
            if pos != -1 and pos < first_match_pos:
                first_match_pos = pos
        
        # 如果找到匹配，以匹配位置为中心生成片段
        if first_match_pos < len(content):
            start = max(0, first_match_pos - 50)
            end = min(len(content), first_match_pos + self.content_preview_length - 50)
            snippet = content[start:end]
            
            # 如果不是从开头开始，添加省略号
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."
                
            return snippet
        else:
            # 没有匹配的情况，返回开头部分
            return content[:self.content_preview_length] + ("..." if len(content) > self.content_preview_length else "")
    
    def _generate_search_suggestion(self, query: str, results_count: int) -> str:
        """为AI生成后续搜索建议"""
        suggestions = []
        
        if results_count == 0:
            suggestions.append("尝试使用更通用的关键词")
            suggestions.append("检查是否有拼写错误")
            suggestions.append("尝试英文或中文的不同表达")
        elif results_count < 3:
            suggestions.append("可以尝试相关的技术术语")
            suggestions.append("搜索更具体的关键词组合")
        elif results_count > 20:
            suggestions.append("可以使用更具体的关键词缩小范围")
            suggestions.append("尝试添加编程语言或框架名称")
        
        # 基于查询词的具体建议
        query_lower = query.lower()
        if "python" in query_lower:
            suggestions.append("可尝试: 'async', 'await', 'asyncio'")
        elif "javascript" in query_lower or "js" in query_lower:
            suggestions.append("可尝试: 'promise', 'async/await', 'callback'")
        elif "react" in query_lower:
            suggestions.append("可尝试: 'hooks', 'useEffect', 'useState'")
        
        if suggestions:
            return f"建议AI尝试: {' | '.join(suggestions[:3])}"
        else:
            return "搜索结果良好，可尝试相关关键词进一步搜索"