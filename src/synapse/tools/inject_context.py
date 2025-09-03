"""
智能上下文注入工具 for Synapse MCP (简化版)

本模块实现了简化的上下文注入功能，直接接收搜索结果并引导AI应用到问题解决中。

改进目标：
1. 移除复杂的评分和排序算法
2. 让AI负责语义理解和内容应用
3. 无信息遗漏，处理所有搜索结果
4. 结果导向，引导AI输出可操作的解决方案

核心功能：
1. 直接接收搜索结果 - 从search_knowledge工具获得的结果
2. 简单格式化处理 - 清理和组织搜索结果
3. AI引导机制 - 返回结构化指令引导AI应用解决方案
4. 向后兼容 - 保留必要的兼容性参数

技术特性：
- 极简处理逻辑，响应速度 < 100ms
- 结构化返回数据，引导AI后续处理
- 完整的错误处理和日志记录
- MCP协议标准兼容
"""

import logging
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)


class InjectContextTool:
    """
    简化的智能上下文注入工具
    
    这个工具采用"简单粗暴"的策略：
    1. 直接接收搜索结果，不进行内部搜索
    2. 简单格式化处理，避免复杂的评分算法
    3. 返回引导AI进行问题解决应用的结构化数据
    4. 让AI负责语义理解和具体应用
    
    主要优势：
    - 处理速度快：无复杂计算，响应时间 < 100ms
    - 信息无遗漏：处理所有搜索结果，不进行筛选
    - AI智能处理：充分利用AI的理解和应用能力
    - 易于维护：逻辑简单，代码易懂
    
    使用示例:
        inject_tool = InjectContextTool()
        
        # 先用search_knowledge获取搜索结果
        search_result = search_knowledge_tool.search_knowledge("React hooks优化")
        
        # 然后注入上下文并引导AI应用
        result = inject_tool.inject_context(
            current_query="如何优化React hooks性能",
            search_results=search_result["results"]
        )
    """
    
    def __init__(self):
        """
        初始化简化的上下文注入工具
        
        无需复杂的依赖注入，保持简单
        """
        logger.info("SimplifiedInjectContextTool 初始化完成")
    
    async def inject_context(
        self, 
        current_query: str,
        search_results: List[Dict],
        include_solutions: bool = True,      # 保留向后兼容性
        include_conversations: bool = True,  # 保留向后兼容性
        ctx: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        为当前查询注入搜索结果上下文，并引导AI应用到问题解决中
        
        Args:
            current_query: 当前用户的查询或问题（必需）
            search_results: 来自search_knowledge工具的搜索结果列表（必需）
            include_solutions: 保留向后兼容性（默认True）
            include_conversations: 保留向后兼容性（默认True）
            ctx: MCP上下文对象
            
        Returns:
            Dict: 引导AI进行问题解决应用的结构化数据
            {
                "content": [{"type": "text", "text": "结构化JSON数据"}],
                "processing_time_ms": float,
                "total_items": int,
                "injection_summary": str
            }
        """
        start_time = time.time()
        
        try:
            if ctx:
                await ctx.info(f"开始为查询注入上下文: '{current_query[:50]}'")
                await ctx.info(f"处理 {len(search_results)} 个搜索结果")
            
            # 参数验证
            if not current_query or not current_query.strip():
                raise ValueError("当前查询不能为空")
            
            if not isinstance(search_results, list):
                raise ValueError("search_results 必须是列表类型")
            
            # 格式化搜索结果供AI处理
            formatted_results = self._format_search_results_for_ai(search_results)
            
            processing_time = (time.time() - start_time) * 1000
            
            if ctx:
                await ctx.info(f"上下文注入完成，引导AI进行问题解决应用")
            
            # 返回引导AI进行问题解决应用的结构化数据
            return {
                "content": [{
                    "type": "text", 
                    "text": json.dumps({
                        "query": current_query,
                        "total_results": len(search_results),
                        "search_results": formatted_results,
                        "action_needed": "apply_context_to_problem",
                        "instruction": f"""请基于以上 {len(search_results)} 个搜索结果，为当前问题 '{current_query}' 提供具体的解决方案：

1. **分析相关性**：从搜索结果中识别与当前问题最相关的解决方案
2. **提取核心方法**：总结可以直接应用的代码片段、方法或模式
3. **具体应用指导**：说明如何将这些解决方案应用到当前问题中
4. **实施建议**：提供具体的实现步骤或代码示例

请直接给出可操作的解决方案，而不仅仅是总结。"""
                    }, indent=2, ensure_ascii=False)
                }],
                "processing_time_ms": round(processing_time, 2),
                "total_items": len(search_results),
                "injection_summary": f"已为查询 '{current_query}' 准备 {len(search_results)} 个解决方案供AI分析应用"
            }
            
        except Exception as e:
            error_msg = str(e)
            if ctx:
                await ctx.error(f"上下文注入失败: {error_msg}")
            
            logger.error(f"上下文注入失败 - 查询: '{current_query}', 错误: {error_msg}", exc_info=True)
            
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": error_msg,
                        "query": current_query,
                        "action_needed": "handle_error"
                    }, indent=2, ensure_ascii=False)
                }],
                "processing_time_ms": (time.time() - start_time) * 1000,
                "total_items": 0,
                "injection_summary": f"注入失败: {error_msg}"
            }

    def _format_search_results_for_ai(self, search_results: List[Dict]) -> List[Dict]:
        """
        格式化搜索结果供AI处理
        
        简化搜索结果格式，保留AI需要的关键信息
        
        Args:
            search_results: 来自search_knowledge的搜索结果
            
        Returns:
            List[Dict]: 格式化后的结果列表
        """
        formatted = []
        
        for result in search_results:
            formatted_result = {
                "id": result.get("id", "unknown"),
                "title": result.get("title", "未知标题"),
                "type": result.get("type", "unknown"),
                "language": result.get("language"),
                "content": result.get("content", result.get("snippet", "")),  # 优先使用完整内容，fallback到snippet
                "reusability_score": result.get("reusability_score", 0.0),
                "match_reason": result.get("match_reason", ""),
            }
            
            # 移除空值
            formatted_result = {k: v for k, v in formatted_result.items() if v}
            formatted.append(formatted_result)
        
        return formatted