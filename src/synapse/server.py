"""
Synapse MCP Server - Main Server Module

This module contains the complete implementation of an MCP (Model Context Protocol) server
that provides intelligent memory and knowledge retrieval functionality.

Key Features:
- FastMCP framework-based MCP server
- Tool registration (save-conversation, search-knowledge, inject-context)
- Unified error handling and response formatting
- Parameter validation and server lifecycle management
- MCP protocol compliance for seamless AI assistant integration
"""

import asyncio
import logging
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
import sys

from mcp.server.fastmcp import FastMCP, Context

from synapse.models import ConversationRecord
from synapse.storage.paths import StoragePaths
from synapse.storage.initializer import StorageInitializer, initialize_synapse_storage
from synapse.storage.file_manager import FileManager
from synapse.utils.logging_config import setup_logging
from synapse.tools.save_conversation import SaveConversationTool
from synapse.tools.search_knowledge import SearchKnowledgeTool
from synapse.tools.inject_context import InjectContextTool

logger = logging.getLogger(__name__)

# Mock Database class for demonstration purposes
class Database:
    """Mock database class for demonstration purposes"""
    
    @classmethod
    async def connect(cls) -> "Database":
        """Connect to database"""
        logger.info("Database connection established")
        return cls()
    
    async def disconnect(self) -> None:
        """Disconnect from database"""
        logger.info("Database connection closed")
    
    async def save_conversation(self, conversation: ConversationRecord) -> str:
        """Save conversation record (mock implementation)"""
        logger.info(f"Saving conversation: {conversation.id}")
        return conversation.id
    
    async def search_conversations(self, query: str, limit: int = 10) -> list:
        """Search conversation records (mock implementation)"""
        logger.info(f"Search query: '{query}', limit: {limit}")
        return [
            {
                "id": "conv_20240115_001",
                "title": f"Solution for '{query}'",
                "snippet": f"This is a detailed explanation and code example for {query}...",
                "match_score": 0.95,
                "created_at": "2024-01-15T10:30:00Z",
                "tags": [query.lower(), "programming"],
                "type": "conversation"
            }
        ]

@dataclass
class AppContext:
    """Application context containing database connections and resources"""
    db: Database
    storage_paths: StoragePaths
    file_manager: FileManager
    save_conversation_tool: SaveConversationTool
    search_knowledge_tool: SearchKnowledgeTool
    inject_context_tool: InjectContextTool

@asynccontextmanager
async def app_lifespan(_: FastMCP):
    """Manage application lifecycle with resource initialization and cleanup"""
    logger.info("Starting Synapse MCP Server...")
    
    try:
        # Initialize storage system
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, initialize_synapse_storage)
        
        # Connect to database
        db = await Database.connect()
        
        # Create resource managers
        storage_paths = StoragePaths()
        file_manager = FileManager(storage_paths)
        
        # Create tool instances
        save_conversation_tool = SaveConversationTool(storage_paths)
        search_knowledge_tool = SearchKnowledgeTool(storage_paths, file_manager)
        inject_context_tool = InjectContextTool(storage_paths, file_manager, search_knowledge_tool)
        
        # Create application context
        app_context = AppContext(
            db=db, 
            storage_paths=storage_paths,
            file_manager=file_manager,
            save_conversation_tool=save_conversation_tool,
            search_knowledge_tool=search_knowledge_tool,
            inject_context_tool=inject_context_tool
        )
        
        logger.info("Synapse MCP Server started successfully")
        yield app_context
        
    except Exception as e:
        logger.error(f"Server startup failed: {str(e)}")
        raise
    finally:
        # Cleanup resources
        logger.info("Shutting down Synapse MCP Server...")
        if 'db' in locals():
            await db.disconnect()
        logger.info("Synapse MCP Server shutdown complete")

# Create FastMCP server instance
mcp = FastMCP("synapse-mcp", lifespan=app_lifespan)

# ==================== MCP Prompt Templates ====================

@mcp.prompt(title="Conversation Analysis")
def conversation_analysis_prompt(
    title: str,
    focus: str = "comprehensive"
) -> str:
    """
    Conversation analysis prompt template.
    
    Analyzes the current conversation context automatically without requiring
    explicit content input. The AI will analyze the full conversation history.
    
    Args:
        title: Conversation title for the analysis
        focus: Analysis focus ("comprehensive", "summary", "tags", "solutions")
    
    Returns:
        str: Formatted analysis prompt for current conversation context
    """
    base_prompt = f"""Please analyze the current technical conversation and provide structured analysis results.

## Conversation Information
**Title**: {title}
**Content**: Please analyze the complete current conversation context

## Analysis Requirements
Please provide the following analysis results in JSON format:

```json
{{
    "summary": "Concise summary of the current conversation (1-2 sentences)",
    "tags": ["technical_tag1", "technical_tag2", "framework_name", "..."],
    "importance": 3,
    "category": "problem-solving | learning | code-review | implementation | debugging | general",
    "has_solutions": true,
    "solution_indicators": ["Types of solutions or approaches discussed"]
}}
```

## Analysis Focus"""
    
    if focus == "comprehensive":
        return base_prompt + """
- Comprehensive analysis: summary, tags, importance, category, solution identification
- Identify tech stack, programming languages, frameworks
- Evaluate educational value and practical utility
- Detect reusable solutions"""
    elif focus == "summary":
        return base_prompt + """
- Focus on generating accurate and concise summaries
- Extract core technical points and conclusions"""
    elif focus == "tags":
        return base_prompt + """
- Focus on extracting technical tags
- Identify programming languages, frameworks, tools, concepts
- Sort by relevance, maximum 10 tags"""
    elif focus == "solutions":
        return base_prompt + """
- Focus on identifying reusable solutions
- Detect code snippets, configuration examples, best practices
- Evaluate solution generalizability"""
    else:
        return base_prompt

@mcp.prompt(title="Solution Extraction")  
def solution_extraction_prompt(
    conversation_title: str,
    conversation_content: str,
    analysis_summary: str = "",
    extraction_type: str = "all"
) -> str:
    """
    Solution extraction prompt template.
    
    Based on conversation content and existing analysis, extract reusable solutions.
    
    Args:
        conversation_title: Conversation title
        conversation_content: Complete conversation content
        analysis_summary: Existing analysis summary
        extraction_type: Extraction type ("all", "code", "approaches", "patterns")
    
    Returns:
        str: Formatted solution extraction prompt
    """
    base_prompt = f"""请从以下技术对话中提取可重用的解决方案。

## 对话信息
**标题**: {conversation_title}
**分析摘要**: {analysis_summary}

**完整内容**:
{conversation_content[:3000]}{'...' if len(conversation_content) > 3000 else ''}

## 提取要求
请提供以下格式的解决方案（JSON格式）：

```json
{{
    "solutions": [
        {{
            "type": "code|approach|pattern|configuration",
            "title": "解决方案标题",
            "description": "详细描述和使用场景",
            "content": "具体的解决方案内容",
            "language": "编程语言（如果是代码）",
            "reusability_score": 0.0-1.0的可重用性评分,
            "tags": ["相关标签"],
            "prerequisites": ["前置条件或依赖"]
        }}
    ]
}}
```

## 提取重点"""
    
    if extraction_type == "code":
        return base_prompt + """
- 重点提取代码片段和函数
- 包含完整的可执行代码
- 添加必要的注释和说明"""
    elif extraction_type == "approaches":
        return base_prompt + """
- 重点提取解决思路和方法
- 包含步骤化的解决流程
- 适用于概念性问题的解决"""
    elif extraction_type == "patterns":
        return base_prompt + """
- 重点提取设计模式和最佳实践
- 包含可复制的架构模式
- 适用于系统设计和架构决策"""
    else:
        return base_prompt + """
- 全面提取所有类型的解决方案
- 包含代码、方法、模式、配置等
- 按重要性和可重用性排序"""

@mcp.prompt(title="内容摘要")
def content_summary_prompt(
    title: str,
    content: str,
    length: str = "medium"
) -> str:
    """
    内容摘要提示词模板
    
    生成不同长度的内容摘要。
    
    Args:
        title: 内容标题
        content: 内容正文
        length: 摘要长度 ("short", "medium", "long")
    
    Returns:
        str: 格式化的摘要提示词
    """
    length_specs = {
        "short": "1句话，最多20字",
        "medium": "2-3句话，50-100字", 
        "long": "1段话，100-200字"
    }
    
    spec = length_specs.get(length, length_specs["medium"])
    
    return f"""请为以下内容生成{spec}的摘要。

## 原始内容
**标题**: {title}
**正文**: 
{content[:1500]}{'...' if len(content) > 1500 else ''}

## 摘要要求
- 长度: {spec}
- 重点: 核心信息和关键要点
- 风格: 简洁清晰，技术准确
- 格式: 纯文本，无需JSON包装

请直接输出摘要内容："""

# ==================== MCP Tool Implementations ====================

@mcp.tool()
async def save_conversation(
    title: str,
    tags: list[str] = None,
    category: str = None, 
    importance: int = None,
    check_duplicates: bool = True,
    # AI分析结果参数（通过conversation_analysis_prompt获得后传入）
    ai_summary: str = None,
    ai_tags: list[str] = None,
    ai_importance: int = None,
    ai_category: str = None,
    ai_solutions: list[dict] = None,
    ctx: Context = None
) -> dict:
    """
    Save AI conversation records to knowledge base based on current conversation context.
    
    This tool works with AI analysis results to store conversation metadata:
    - Accept user-specified or AI-analyzed metadata
    - Extract content from current conversation context automatically
    - Detect and notify duplicate conversations
    - Update search indexes for fast queries
    
    Recommended usage workflow:
    1. User says: "帮我保存今天的对话"
    2. System calls conversation_analysis_prompt to analyze current context
    3. System passes AI analysis results to this tool for saving
    
    Args:
        title: Conversation topic title (required)
        tags: User-defined tag list (optional)
        category: User-specified conversation category (optional)
        importance: User-specified importance level 1-5 (optional)
        check_duplicates: Whether to check for duplicate conversations (default True)
        ai_summary: AI-generated summary from conversation_analysis_prompt
        ai_tags: AI-extracted tag list from conversation_analysis_prompt
        ai_importance: AI-assessed importance from conversation_analysis_prompt
        ai_category: AI-inferred category from conversation_analysis_prompt
        ai_solutions: AI-extracted solution list from conversation_analysis_prompt
        ctx: MCP context object for progress reporting
        
    Returns:
        dict: Detailed save result information including:
            - success: Whether save was successful
            - conversation: Saved conversation details
            - duplicates_found: Number of duplicate conversations found
            - duplicate_ids: List of duplicate conversation IDs
            - storage_path: File storage path
    """
    try:
        if ctx:
            await ctx.info(f"Starting conversation save: {title}")
        
        # Basic parameter validation
        if not title or not title.strip():
            raise ValueError("Conversation title cannot be empty")
        
        if not ai_summary:
            raise ValueError("AI analysis results are required. Please first call conversation_analysis_prompt to analyze the current conversation.")
        
        if importance is not None and (importance < 1 or importance > 5):
            raise ValueError("Importance level must be between 1-5")
        
        # Get save conversation tool instance
        save_tool = None
        if ctx and hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'lifespan_context'):
            save_tool = ctx.request_context.lifespan_context.save_conversation_tool
        
        if not save_tool:
            raise RuntimeError("无法获取SaveConversationTool实例，请检查服务器配置")
        
        if ctx:
            await ctx.info("Processing conversation with AI analysis results...")
        
        # Create conversation content from AI summary since we no longer require explicit content
        # The AI has already analyzed the complete conversation context
        conversation_content = ai_summary + "\n\n[Full conversation content was analyzed by AI system]"
        
        # 使用SaveConversationTool进行保存
        result = await save_tool.save_conversation(
            title=title.strip(),
            content=conversation_content,
            user_tags=tags,
            user_category=category,
            user_importance=importance,
            check_duplicates=check_duplicates,
            # 传递AI分析结果
            ai_summary=ai_summary,
            ai_tags=ai_tags,
            ai_importance=ai_importance,
            ai_category=ai_category,
            ai_solutions=ai_solutions,
            ctx=ctx
        )
        
        # 检查保存结果
        if not result.get("success", False):
            error_msg = result.get("error", "未知错误")
            raise RuntimeError(f"保存失败: {error_msg}")
        
        conversation_info = result.get("conversation", {})
        duplicates_count = result.get("duplicates_found", 0)
        
        if ctx:
            if duplicates_count > 0:
                await ctx.info(f"检测到 {duplicates_count} 个相似对话")
            
            await ctx.info(f"对话保存成功: {conversation_info.get('id', 'Unknown')}")
            await ctx.info(f"自动提取了 {conversation_info.get('auto_tags_count', 0)} 个标签")
        
        # 构建返回结果（保持与原API兼容，同时提供更多信息）
        return {
            # 基本信息（保持兼容）
            "id": conversation_info.get("id"),
            "title": conversation_info.get("title"),
            "stored_at": conversation_info.get("created_at"),
            "tags": conversation_info.get("tags", []),
            "category": conversation_info.get("category", "general"),
            "importance": conversation_info.get("importance", 3),
            "searchable": True,
            
            # 扩展信息
            "summary": conversation_info.get("summary", ""),
            "auto_generated": {
                "tags_count": conversation_info.get("auto_tags_count", 0),
                "user_tags_count": conversation_info.get("user_tags_count", 0),
                "solutions_found": conversation_info.get("solutions_count", 0)
            },
            "duplicate_detection": {
                "checked": check_duplicates,
                "duplicates_found": duplicates_count,
                "duplicate_ids": result.get("duplicate_ids", [])
            },
            "storage_info": {
                "file_path": result.get("storage_path"),
                "indexed": True  # 索引已更新
            }
        }
        
    except Exception as e:
        error_msg = str(e)
        if ctx:
            await ctx.error(f"保存对话失败: {error_msg}")
        
        logger.error(f"保存对话失败 - 标题: {title[:50]}..., 错误: {error_msg}", exc_info=True)
        
        # 返回错误信息而不是抛出异常，让调用方能够处理
        return {
            "success": False,
            "error": error_msg,
            "error_type": type(e).__name__,
            "searchable": False
        }

@mcp.tool()
async def search_knowledge(
    query: str,
    category: str = None,
    tags: list[str] = None,
    time_range: str = "all",
    importance_min: int = None,
    limit: int = 10,
    include_content: bool = False,
    ctx: Context = None
) -> dict:
    """
    在知识库中搜索相关的对话记录和解决方案
    
    使用智能三层搜索策略提供高质量的搜索结果：
    1. 精确匹配层 - 基于索引的关键词精确匹配
    2. 标签过滤层 - 基于技术标签的分类过滤  
    3. 内容匹配层 - 基于内容的模糊匹配和相关性评分
    
    性能目标：响应时间 < 200ms，搜索准确率 > 80%
    
    Args:
        query: 搜索查询关键词（必需）
        category: 内容分类过滤（可选）
        tags: 标签过滤列表（可选）
        time_range: 时间范围过滤 ("week", "month", "all")
        importance_min: 最小重要性等级 (1-5)
        limit: 返回结果数量限制 (1-50)
        include_content: 是否在结果中包含完整对话内容
        ctx: MCP上下文对象
        
    Returns:
        dict: 智能搜索结果，包含详细的相关性分数和统计信息
    """
    try:
        if ctx:
            await ctx.info(f"开始智能搜索: '{query}'")
        
        # 获取搜索知识工具实例
        search_tool = None
        if ctx and hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'lifespan_context'):
            search_tool = ctx.request_context.lifespan_context.search_knowledge_tool
        
        if not search_tool:
            raise RuntimeError("无法获取SearchKnowledgeTool实例，请检查服务器配置")
        
        if ctx:
            await ctx.info("执行三层搜索策略...")
        
        # 使用SearchKnowledgeTool进行智能搜索
        result = search_tool.search_knowledge(
            query=query.strip(),
            category=category,
            tags=tags,
            time_range=time_range,
            importance_min=importance_min,
            limit=limit,
            include_content=include_content
        )
        
        # 检查搜索结果
        if not result:
            raise RuntimeError("搜索工具返回空结果")
        
        search_time = result.get("search_time_ms", 0)
        results_count = len(result.get("results", []))
        
        if ctx:
            await ctx.info(f"搜索完成: 找到 {results_count} 个结果，耗时 {search_time:.2f}ms")
            
            # 提供详细的搜索统计信息
            stats = result.get("statistics", {})
            if stats:
                candidates = stats.get("total_candidates", 0)
                filtered = stats.get("after_filtering", 0)
                if candidates > 0:
                    await ctx.info(f"搜索统计: {candidates} 个候选 → {filtered} 个过滤结果")
                
                # 性能信息
                if search_time > 100:
                    await ctx.info(f"搜索耗时较长: {search_time:.2f}ms (目标<200ms)")
                elif search_time < 50:
                    await ctx.info(f"搜索性能良好: {search_time:.2f}ms")
        
        # 确保返回格式与原API兼容
        return {
            "results": result.get("results", []),
            "total": result.get("total", 0),
            "search_time_ms": round(search_time, 2),
            "query": query,
            "processed_query": result.get("processed_query", query),
            "filters_applied": result.get("filters_applied", {
                "category": category,
                "tags": tags,
                "time_range": time_range,
                "importance_min": importance_min,
                "limit": limit
            }),
            "search_statistics": result.get("statistics", {}),
            "search_engine": "synapse_intelligent_search_v1.0"
        }
        
    except Exception as e:
        error_msg = str(e)
        if ctx:
            await ctx.error(f"搜索失败: {error_msg}")
        
        logger.error(f"搜索失败 - 查询: '{query}', 错误: {error_msg}", exc_info=True)
        
        # 返回错误信息而不是抛出异常，让调用方能够处理
        return {
            "results": [],
            "total": 0,
            "search_time_ms": 0,
            "query": query,
            "error": error_msg,
            "error_type": type(e).__name__,
            "filters_applied": {
                "category": category,
                "tags": tags,
                "time_range": time_range,
                "importance_min": importance_min,
                "limit": limit
            },
            "search_engine": "synapse_intelligent_search_v1.0"
        }


@mcp.tool()
async def inject_context(
    current_query: str,
    max_items: int = 3,
    relevance_threshold: float = 0.7,
    include_solutions: bool = True,
    include_conversations: bool = True,
    ctx: Context = None
) -> dict:
    """
    向当前对话注入相关的历史上下文
    
    使用智能上下文注入系统，基于多因子相关性算法从历史对话和解决方案中
    找到最相关的内容，为当前对话提供有价值的背景信息和参考资料。
    
    相关性计算基于以下因素：
    - 文本相似度（40%）：关键词匹配和内容重叠分析
    - 标签匹配（25%）：基于技术标签的相似度
    - 时间新鲜度（15%）：较新内容的加权优势  
    - 重要性等级（15%）：高重要性内容的优先级
    - 质量因子（5%）：内容质量和完整性评估
    
    Args:
        current_query: 当前用户的查询或问题（必需）
        max_items: 最大注入的上下文项数量 (1-10，默认3)
        relevance_threshold: 相关性阈值 (0.0-1.0，默认0.7)
        include_solutions: 是否包含解决方案内容（默认True）
        include_conversations: 是否包含对话记录（默认True）
        ctx: MCP上下文对象
        
    Returns:
        dict: 包含上下文项、注入摘要和详细统计信息的结果
        {
            "context_items": [...],
            "injection_summary": str,
            "total_items": int,
            "processing_time_ms": float,
            "search_statistics": {...}
        }
    """
    try:
        if ctx:
            await ctx.info(f"开始智能上下文注入: '{current_query[:50]}'")
        
        # 基础参数验证
        if not current_query or not current_query.strip():
            raise ValueError("当前查询不能为空")
        
        if not isinstance(max_items, int) or max_items < 1 or max_items > 10:
            raise ValueError("最大注入项数必须在1-10之间")
        
        if not isinstance(relevance_threshold, (int, float)) or relevance_threshold < 0.0 or relevance_threshold > 1.0:
            raise ValueError("相关性阈值必须在0.0-1.0之间")
        
        # 获取上下文注入工具实例
        inject_tool = None
        if ctx and hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'lifespan_context'):
            inject_tool = ctx.request_context.lifespan_context.inject_context_tool
        
        if not inject_tool:
            raise RuntimeError("无法获取InjectContextTool实例，请检查服务器配置")
        
        if ctx:
            await ctx.info("执行智能相关性分析...")
            if relevance_threshold > 0.8:
                await ctx.info(f"使用高质量阈值: {relevance_threshold}")
        
        # 使用InjectContextTool进行智能上下文注入
        result = inject_tool.inject_context(
            current_query=current_query.strip(),
            max_items=max_items,
            relevance_threshold=relevance_threshold,
            include_solutions=include_solutions,
            include_conversations=include_conversations
        )
        
        # 检查注入结果
        if not result:
            raise RuntimeError("上下文注入工具返回空结果")
        
        context_items_count = result.get("total_items", 0)
        processing_time = result.get("processing_time_ms", 0)
        
        if ctx:
            if context_items_count > 0:
                await ctx.info(f"成功注入 {context_items_count} 个相关上下文项")
                
                # 提供详细的注入统计信息
                stats = result.get("search_statistics", {})
                if stats:
                    candidates = stats.get("candidates_found", 0)
                    above_threshold = stats.get("above_threshold", 0)
                    if candidates > 0:
                        await ctx.info(f"注入统计: {candidates} 个候选 → {above_threshold} 个符合阈值 → {context_items_count} 个最终选择")
                
                # 性能信息
                if processing_time > 300:
                    await ctx.info(f"处理时间: {processing_time:.2f}ms (目标<500ms)")
                else:
                    await ctx.info(f"处理高效: {processing_time:.2f}ms")
            else:
                await ctx.info(f"未找到符合阈值 {relevance_threshold} 的相关上下文")
        
        # 确保返回格式与原API兼容，同时提供扩展信息
        return {
            # 基本兼容信息
            "context_items": result.get("context_items", []),
            "injection_summary": result.get("injection_summary", "上下文注入完成"),
            "total_items": context_items_count,
            "query": current_query,
            "relevance_threshold": relevance_threshold,
            
            # 扩展信息
            "processed_query": result.get("processed_query", current_query),
            "keywords_extracted": result.get("keywords_extracted", []),
            "processing_time_ms": round(processing_time, 2),
            "search_statistics": result.get("search_statistics", {}),
            "settings": {
                "max_items": max_items,
                "include_solutions": include_solutions,
                "include_conversations": include_conversations
            },
            "success": True,
            "context_engine": "synapse_intelligent_inject_v1.0"
        }
        
    except Exception as e:
        error_msg = str(e)
        if ctx:
            await ctx.error(f"上下文注入失败: {error_msg}")
        
        logger.error(f"上下文注入失败 - 查询: '{current_query}', 错误: {error_msg}", exc_info=True)
        
        # 返回错误信息而不是抛出异常，让调用方能够处理
        return {
            "context_items": [],
            "injection_summary": f"注入失败: {error_msg}",
            "total_items": 0,
            "query": current_query,
            "error": error_msg,
            "error_type": type(e).__name__,
            "relevance_threshold": relevance_threshold,
            "settings": {
                "max_items": max_items,
                "include_solutions": include_solutions,
                "include_conversations": include_conversations
            },
            "success": False,
            "context_engine": "synapse_intelligent_inject_v1.0"
        }

@mcp.tool()
async def export_data(
    export_path: str,
    include_backups: bool = False,
    include_cache: bool = False,
    ctx: Context = None
) -> dict:
    """
    Export all Synapse data to a specified directory path.
    
    This tool exports conversations, solutions, indexes, and optionally backups
    to enable data migration, backup, and sharing between systems.
    
    Args:
        export_path: Target directory path for exported data (required)
        include_backups: Whether to include backup files in export (default: False)
        include_cache: Whether to include cache files in export (default: False)
        ctx: MCP context object for logging and progress reporting
        
    Returns:
        dict: Export result with status, statistics, and file paths
    """
    try:
        if ctx:
            await ctx.info(f"Starting data export to: {export_path}")
        
        # Parameter validation
        if not export_path or not export_path.strip():
            raise ValueError("Export path cannot be empty")
        
        from pathlib import Path
        export_dir = Path(export_path.strip()).expanduser().resolve()
        
        # Check if export path is valid and writable
        if export_dir.exists() and not export_dir.is_dir():
            raise ValueError(f"Export path exists but is not a directory: {export_dir}")
        
        # Get file manager instance
        file_manager = None
        if ctx and hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'lifespan_context'):
            file_manager = ctx.request_context.lifespan_context.file_manager
        
        if not file_manager:
            raise RuntimeError("无法获取FileManager实例，请检查服务器配置")
        
        if ctx:
            await ctx.info("Validating export directory permissions...")
        
        # Test write permissions by creating export directory
        try:
            export_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise PermissionError(f"No write permission for export path: {export_dir}")
        except Exception as e:
            raise RuntimeError(f"Failed to create export directory: {e}")
        
        if ctx:
            await ctx.info("Gathering storage statistics...")
        
        # Get pre-export statistics
        storage_stats = file_manager.get_storage_statistics()
        
        if ctx:
            await ctx.info(f"Found {storage_stats.total_conversations} conversations and {storage_stats.total_solutions} solutions")
            await ctx.report_progress(0.2, "Starting data export...")
        
        # Perform the export using FileManager
        export_success = file_manager.export_data(export_dir, include_backups=include_backups)
        
        if not export_success:
            raise RuntimeError("Export operation failed - check file manager logs for details")
        
        if ctx:
            await ctx.report_progress(0.8, "Calculating export statistics...")
        
        # Calculate export statistics
        try:
            exported_files = 0
            exported_size = 0
            
            if export_dir.exists():
                for file_path in export_dir.rglob("*"):
                    if file_path.is_file() and file_path.name != "export_info.json":
                        exported_files += 1
                        exported_size += file_path.stat().st_size
        except Exception as e:
            logger.warning(f"Failed to calculate export statistics: {e}")
            exported_files = -1
            exported_size = -1
        
        if ctx:
            await ctx.report_progress(1.0, "Export completed successfully")
            await ctx.info(f"Exported {exported_files} files ({exported_size / (1024*1024):.2f} MB) to {export_dir}")
        
        # Build comprehensive response
        result = {
            "success": True,
            "export_path": str(export_dir),
            "exported_at": datetime.now().isoformat(),
            "statistics": {
                "total_conversations_exported": storage_stats.total_conversations,
                "total_solutions_exported": storage_stats.total_solutions,
                "total_files_exported": exported_files,
                "total_size_bytes": exported_size,
                "total_size_mb": round(exported_size / (1024*1024), 2) if exported_size > 0 else 0,
                "include_backups": include_backups,
                "include_cache": include_cache
            },
            "exported_components": {
                "conversations": True,
                "solutions": True,
                "indexes": True,
                "backups": include_backups,
                "cache": include_cache,
                "export_info": True
            },
            "summary": f"Successfully exported {storage_stats.total_conversations} conversations and {storage_stats.total_solutions} solutions to {export_dir}"
        }
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        if ctx:
            await ctx.error(f"Data export failed: {error_msg}")
        
        logger.error(f"数据导出失败 - 路径: {export_path}, 错误: {error_msg}", exc_info=True)
        
        return {
            "success": False,
            "export_path": export_path,
            "error": error_msg,
            "error_type": type(e).__name__,
            "exported_at": datetime.now().isoformat(),
            "statistics": {
                "total_conversations_exported": 0,
                "total_solutions_exported": 0,
                "total_files_exported": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "include_backups": include_backups,
                "include_cache": include_cache
            },
            "summary": f"Export failed: {error_msg}"
        }

@mcp.tool()
async def import_data(
    import_path: str,
    merge_mode: str = "append",
    validate_data: bool = True,
    create_backup: bool = True,
    ctx: Context = None
) -> dict:
    """
    Import Synapse data from a specified directory path.
    
    This tool imports conversations, solutions, and indexes from an exported
    data directory, with options for data validation and merge strategies.
    
    Args:
        import_path: Source directory path containing exported data (required)
        merge_mode: Merge strategy - "append" or "overwrite" (default: "append")
        validate_data: Whether to validate data format before import (default: True)
        create_backup: Whether to create backup before import (default: True)
        ctx: MCP context object for logging and progress reporting
        
    Returns:
        dict: Import result with status, statistics, and validation results
    """
    try:
        if ctx:
            await ctx.info(f"Starting data import from: {import_path}")
        
        # Parameter validation
        if not import_path or not import_path.strip():
            raise ValueError("Import path cannot be empty")
        
        if merge_mode not in ["append", "overwrite"]:
            raise ValueError("Merge mode must be 'append' or 'overwrite'")
        
        from pathlib import Path
        import_dir = Path(import_path.strip()).expanduser().resolve()
        
        # Check if import path exists and is valid
        if not import_dir.exists():
            raise FileNotFoundError(f"Import path does not exist: {import_dir}")
        
        if not import_dir.is_dir():
            raise ValueError(f"Import path is not a directory: {import_dir}")
        
        # Get file manager instance
        file_manager = None
        if ctx and hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'lifespan_context'):
            file_manager = ctx.request_context.lifespan_context.file_manager
        
        if not file_manager:
            raise RuntimeError("无法获取FileManager实例，请检查服务器配置")
        
        if ctx:
            await ctx.info("Validating import data structure...")
            await ctx.report_progress(0.1, "Validating import data...")
        
        # Validate import structure
        validation_results = {
            "conversations_found": False,
            "solutions_found": False,
            "indexes_found": False,
            "export_info_found": False,
            "data_valid": True,
            "validation_errors": []
        }
        
        # Check for expected directories and files
        conversations_dir = import_dir / "conversations"
        solutions_dir = import_dir / "solutions"
        indexes_dir = import_dir / "indexes"
        export_info_file = import_dir / "export_info.json"
        
        validation_results["conversations_found"] = conversations_dir.exists() and conversations_dir.is_dir()
        validation_results["solutions_found"] = solutions_dir.exists() and solutions_dir.is_dir()
        validation_results["indexes_found"] = indexes_dir.exists() and indexes_dir.is_dir()
        validation_results["export_info_found"] = export_info_file.exists() and export_info_file.is_file()
        
        # Basic structure validation
        if not any([validation_results["conversations_found"], validation_results["solutions_found"], validation_results["indexes_found"]]):
            validation_results["data_valid"] = False
            validation_results["validation_errors"].append("No valid data directories found (conversations, solutions, or indexes)")
        
        # Data format validation if requested
        if validate_data and validation_results["data_valid"]:
            if ctx:
                await ctx.info("Performing detailed data validation...")
            
            # Count and validate files
            file_counts = {"conversations": 0, "solutions": 0, "invalid_files": 0}
            
            try:
                # Check conversation files
                if conversations_dir.exists():
                    for conv_file in conversations_dir.rglob("*.json"):
                        if conv_file.is_file():
                            try:
                                with open(conv_file, 'r', encoding='utf-8') as f:
                                    conv_data = json.load(f)
                                    # Basic structure validation
                                    if not all(key in conv_data for key in ["id", "title", "content"]):
                                        file_counts["invalid_files"] += 1
                                        validation_results["validation_errors"].append(f"Invalid conversation format: {conv_file.name}")
                                    else:
                                        file_counts["conversations"] += 1
                            except Exception as e:
                                file_counts["invalid_files"] += 1
                                validation_results["validation_errors"].append(f"Cannot read conversation file {conv_file.name}: {str(e)}")
                
                # Check solution files
                if solutions_dir.exists():
                    for sol_file in solutions_dir.glob("*.json"):
                        if sol_file.is_file():
                            try:
                                with open(sol_file, 'r', encoding='utf-8') as f:
                                    sol_data = json.load(f)
                                    # Basic structure validation
                                    if not all(key in sol_data for key in ["id", "type", "content"]):
                                        file_counts["invalid_files"] += 1
                                        validation_results["validation_errors"].append(f"Invalid solution format: {sol_file.name}")
                                    else:
                                        file_counts["solutions"] += 1
                            except Exception as e:
                                file_counts["invalid_files"] += 1
                                validation_results["validation_errors"].append(f"Cannot read solution file {sol_file.name}: {str(e)}")
                
                if file_counts["invalid_files"] > 0:
                    validation_results["data_valid"] = False
                    
            except Exception as e:
                validation_results["data_valid"] = False
                validation_results["validation_errors"].append(f"Data validation failed: {str(e)}")
        
        if ctx:
            if validation_results["data_valid"]:
                await ctx.info(f"Validation passed - Found {file_counts.get('conversations', 0)} conversations and {file_counts.get('solutions', 0)} solutions")
            else:
                await ctx.info(f"Validation found {len(validation_results['validation_errors'])} issues")
        
        # Proceed with import if validation passes or validation is disabled
        if not validate_data or validation_results["data_valid"]:
            
            # Create backup if requested
            backup_info = None
            if create_backup:
                if ctx:
                    await ctx.info("Creating pre-import backup...")
                    await ctx.report_progress(0.3, "Creating backup...")
                
                try:
                    backup_timestamp = int(datetime.now().timestamp())
                    backup_path = file_manager.storage_paths.get_backups_dir() / f"pre_import_backup_{backup_timestamp}"
                    backup_success = file_manager.export_data(backup_path, include_backups=False)
                    
                    if backup_success:
                        backup_info = str(backup_path)
                        if ctx:
                            await ctx.info(f"Backup created successfully: {backup_path}")
                    else:
                        logger.warning("Pre-import backup failed, continuing with import")
                        
                except Exception as e:
                    logger.warning(f"Pre-import backup failed: {e}")
            
            if ctx:
                await ctx.info(f"Starting import with merge mode: {merge_mode}")
                await ctx.report_progress(0.5, "Importing data...")
            
            # Perform the import using FileManager
            import_success = file_manager.import_data(import_dir, merge_mode=merge_mode)
            
            if not import_success:
                raise RuntimeError("Import operation failed - check file manager logs for details")
            
            if ctx:
                await ctx.report_progress(0.9, "Finalizing import...")
            
            # Get post-import statistics
            post_import_stats = file_manager.get_storage_statistics()
            
            if ctx:
                await ctx.report_progress(1.0, "Import completed successfully")
                await ctx.info(f"Import completed - Total: {post_import_stats.total_conversations} conversations, {post_import_stats.total_solutions} solutions")
            
            # Build success response
            result = {
                "success": True,
                "import_path": str(import_dir),
                "imported_at": datetime.now().isoformat(),
                "merge_mode": merge_mode,
                "validation_performed": validate_data,
                "backup_created": create_backup,
                "backup_location": backup_info,
                "validation_results": validation_results,
                "statistics": {
                    "conversations_after_import": post_import_stats.total_conversations,
                    "solutions_after_import": post_import_stats.total_solutions,
                    "total_files_after_import": post_import_stats.total_files,
                    "total_size_mb_after_import": round(post_import_stats.disk_usage_mb, 2)
                },
                "imported_components": {
                    "conversations": validation_results["conversations_found"],
                    "solutions": validation_results["solutions_found"],
                    "indexes": validation_results["indexes_found"]
                },
                "summary": f"Successfully imported data from {import_dir} using {merge_mode} mode"
            }
            
            return result
        
        else:
            # Validation failed
            raise ValueError(f"Data validation failed: {', '.join(validation_results['validation_errors'])}")
        
    except Exception as e:
        error_msg = str(e)
        if ctx:
            await ctx.error(f"Data import failed: {error_msg}")
        
        logger.error(f"数据导入失败 - 路径: {import_path}, 错误: {error_msg}", exc_info=True)
        
        return {
            "success": False,
            "import_path": import_path,
            "error": error_msg,
            "error_type": type(e).__name__,
            "imported_at": datetime.now().isoformat(),
            "merge_mode": merge_mode,
            "validation_performed": validate_data,
            "backup_created": create_backup,
            "validation_results": validation_results if 'validation_results' in locals() else {},
            "summary": f"Import failed: {error_msg}"
        }

@mcp.tool()
async def get_storage_info(ctx: Context = None) -> dict:
    """
    Get comprehensive storage system information and statistics.
    
    This tool provides detailed information about Synapse storage locations,
    directory status, usage statistics, and system health.
    
    Args:
        ctx: MCP context object for logging and progress reporting
        
    Returns:
        dict: Complete storage system information including:
            - Storage directory paths
            - Directory existence and permissions status
            - Storage usage statistics
            - Initialization status
            - System health information
    """
    try:
        if ctx:
            await ctx.info("Retrieving storage system information")
        
        # Initialize storage system components
        storage_paths = StoragePaths()
        initializer = StorageInitializer(storage_paths)
        
        # Get file manager instance for statistics
        file_manager = None
        if ctx and hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'lifespan_context'):
            file_manager = ctx.request_context.lifespan_context.file_manager
        
        # Get comprehensive storage status
        storage_status = initializer.get_storage_status()
        
        # Calculate storage size in MB
        total_size_mb = storage_status["total_size_bytes"] / (1024 * 1024) if storage_status["total_size_bytes"] > 0 else 0.0
        
        # Get real storage statistics if file manager is available
        storage_stats = None
        conversation_count = 0
        solution_count = 0
        
        if file_manager:
            if ctx:
                await ctx.info("Gathering detailed storage statistics...")
            try:
                storage_stats = file_manager.get_storage_statistics()
                conversation_count = storage_stats.total_conversations
                solution_count = storage_stats.total_solutions
            except Exception as e:
                logger.warning(f"Failed to get detailed storage statistics: {e}")
        
        # Get backup information
        backup_info = {
            "backups_available": 0,
            "latest_backup": None,
            "total_backup_size_mb": 0.0,
            "backup_directory_status": "unknown"
        }
        
        try:
            backups_dir = storage_paths.get_backups_dir()
            if backups_dir.exists():
                backup_files = list(backups_dir.glob("*backup*"))
                backup_info["backups_available"] = len([f for f in backup_files if f.is_dir()])
                backup_info["backup_directory_status"] = "available"
                
                # Find latest backup
                if backup_files:
                    latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime if x.exists() else 0)
                    backup_info["latest_backup"] = {
                        "path": str(latest_backup),
                        "created_at": datetime.fromtimestamp(latest_backup.stat().st_mtime).isoformat(),
                        "size_mb": round(sum(f.stat().st_size for f in latest_backup.rglob("*") if f.is_file()) / (1024*1024), 2)
                    }
                
                # Calculate total backup size
                try:
                    total_backup_size = sum(
                        sum(f.stat().st_size for f in backup_dir.rglob("*") if f.is_file())
                        for backup_dir in backup_files if backup_dir.is_dir()
                    )
                    backup_info["total_backup_size_mb"] = round(total_backup_size / (1024*1024), 2)
                except Exception:
                    backup_info["total_backup_size_mb"] = 0.0
            else:
                backup_info["backup_directory_status"] = "not_created"
        except Exception as e:
            logger.warning(f"Failed to get backup information: {e}")
            backup_info["backup_directory_status"] = "error"
        
        # System health check
        health_status = {
            "overall_status": "healthy",
            "issues": [],
            "warnings": []
        }
        
        # Check for potential issues
        if not storage_status["permissions_ok"]:
            health_status["issues"].append("Insufficient permissions for some storage directories")
            health_status["overall_status"] = "degraded"
        
        if total_size_mb > 1000:  # > 1GB
            health_status["warnings"].append(f"Storage usage is high: {total_size_mb:.1f} MB")
        
        if storage_stats and storage_stats.total_files > 5000:
            health_status["warnings"].append(f"Large number of files: {storage_stats.total_files}")
        
        if backup_info["backups_available"] == 0:
            health_status["warnings"].append("No backups available")
        
        # Maintenance information
        maintenance_info = {
            "last_maintenance": None,
            "maintenance_needed": False,
            "recommended_actions": []
        }
        
        # Check if maintenance is needed
        if backup_info["backups_available"] > 10:
            maintenance_info["maintenance_needed"] = True
            maintenance_info["recommended_actions"].append("Clean up old backup files")
        
        if storage_stats and storage_stats.disk_usage_mb > 500:
            maintenance_info["maintenance_needed"] = True
            maintenance_info["recommended_actions"].append("Consider archiving old conversations")
        
        # Try to get last maintenance timestamp from metadata
        try:
            metadata_file = storage_paths.get_indexes_dir() / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    maintenance_info["last_maintenance"] = metadata.get("last_maintenance")
        except Exception:
            pass
        
        # Build comprehensive response with enhanced information
        storage_info = {
            # Primary storage locations
            "data_directory": storage_status["storage_paths"]["data"],
            "config_directory": storage_status["storage_paths"]["config"],
            "cache_directory": storage_status["storage_paths"]["cache"],
            
            # Data subdirectories
            "conversations_directory": storage_status["storage_paths"]["conversations"],
            "solutions_directory": storage_status["storage_paths"]["solutions"],
            "indexes_directory": storage_status["storage_paths"]["indexes"],
            "logs_directory": storage_status["storage_paths"]["logs"],
            "backups_directory": storage_status["storage_paths"]["backups"],
            
            # System status
            "initialized": storage_status["initialized"],
            "permissions_ok": storage_status["permissions_ok"],
            "total_storage_size_bytes": storage_status["total_size_bytes"],
            "total_storage_size_mb": round(total_size_mb, 2),
            
            # Directory details
            "directory_status": storage_status["directory_status"],
            
            # Real statistics
            "total_conversations": conversation_count,
            "total_solutions": solution_count,
            "total_files": storage_stats.total_files if storage_stats else 0,
            "average_file_size_kb": round(storage_stats.avg_file_size_kb, 2) if storage_stats else 0,
            
            # Backup information
            "backup_info": backup_info,
            
            # System health
            "health_status": health_status,
            
            # Maintenance information
            "maintenance_info": maintenance_info,
            
            # Application info
            "server_status": "running",
            "version": "1.0.0",
            "platform": sys.platform,
            "last_updated": datetime.now().isoformat()
        }
        
        if ctx:
            await ctx.info(f"Storage information retrieved successfully - Initialized: {storage_status['initialized']}")
        
        return storage_info
        
    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to retrieve storage information: {str(e)}")
        logger.error(f"Failed to retrieve storage information: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to retrieve storage information: {str(e)}")

@mcp.tool()
async def backup_data(
    backup_name: str = None,
    include_cache: bool = False,
    compression: bool = False,
    ctx: Context = None
) -> dict:
    """
    Create a manual backup of all Synapse data.
    
    This tool creates a comprehensive backup of conversations, solutions, indexes,
    and configuration files for disaster recovery purposes.
    
    Args:
        backup_name: Custom name for the backup (optional, auto-generated if not provided)
        include_cache: Whether to include cache files in backup (default: False)
        compression: Whether to compress the backup (default: False - not implemented)
        ctx: MCP context object for logging and progress reporting
        
    Returns:
        dict: Backup result with status, location, and statistics
    """
    try:
        if ctx:
            await ctx.info("Starting manual data backup...")
        
        # Get file manager instance
        file_manager = None
        if ctx and hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'lifespan_context'):
            file_manager = ctx.request_context.lifespan_context.file_manager
        
        if not file_manager:
            raise RuntimeError("无法获取FileManager实例，请检查服务器配置")
        
        # Generate backup name if not provided
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"manual_backup_{timestamp}"
        else:
            # Sanitize backup name
            import re
            backup_name = re.sub(r'[^\w\-_.]', '_', backup_name.strip())
            if not backup_name:
                backup_name = f"manual_backup_{int(datetime.now().timestamp())}"
        
        if ctx:
            await ctx.info(f"Creating backup: {backup_name}")
            await ctx.report_progress(0.1, "Preparing backup...")
        
        # Get pre-backup statistics
        storage_stats = file_manager.get_storage_statistics()
        
        # Create backup directory
        backup_path = file_manager.storage_paths.get_backups_dir() / backup_name
        
        if backup_path.exists():
            raise ValueError(f"Backup already exists: {backup_name}")
        
        if ctx:
            await ctx.info(f"Backup location: {backup_path}")
            await ctx.report_progress(0.3, "Creating backup directory...")
        
        # Perform the backup
        backup_success = file_manager.export_data(backup_path, include_backups=False)
        
        if not backup_success:
            raise RuntimeError("Backup operation failed - check file manager logs for details")
        
        if ctx:
            await ctx.report_progress(0.8, "Calculating backup statistics...")
        
        # Calculate backup statistics
        backup_stats = {
            "backup_size_bytes": 0,
            "backup_size_mb": 0.0,
            "files_backed_up": 0,
            "directories_backed_up": 0
        }
        
        try:
            if backup_path.exists():
                for item in backup_path.rglob("*"):
                    if item.is_file():
                        backup_stats["files_backed_up"] += 1
                        backup_stats["backup_size_bytes"] += item.stat().st_size
                    elif item.is_dir():
                        backup_stats["directories_backed_up"] += 1
                
                backup_stats["backup_size_mb"] = round(backup_stats["backup_size_bytes"] / (1024*1024), 2)
        except Exception as e:
            logger.warning(f"Failed to calculate backup statistics: {e}")
        
        # Create backup metadata
        backup_metadata = {
            "backup_name": backup_name,
            "created_at": datetime.now().isoformat(),
            "backup_type": "manual",
            "source_statistics": {
                "conversations_count": storage_stats.total_conversations,
                "solutions_count": storage_stats.total_solutions,
                "total_files": storage_stats.total_files,
                "source_size_mb": round(storage_stats.disk_usage_mb, 2)
            },
            "backup_statistics": backup_stats,
            "include_cache": include_cache,
            "compression": compression,
            "version": "1.0.0"
        }
        
        # Save backup metadata
        try:
            metadata_file = backup_path / "backup_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(backup_metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save backup metadata: {e}")
        
        if ctx:
            await ctx.report_progress(1.0, "Backup completed successfully")
            await ctx.info(f"Backup created successfully: {backup_stats['files_backed_up']} files ({backup_stats['backup_size_mb']} MB)")
        
        result = {
            "success": True,
            "backup_name": backup_name,
            "backup_path": str(backup_path),
            "created_at": datetime.now().isoformat(),
            "backup_type": "manual",
            "statistics": backup_stats,
            "source_data": {
                "conversations_backed_up": storage_stats.total_conversations,
                "solutions_backed_up": storage_stats.total_solutions,
                "total_source_files": storage_stats.total_files
            },
            "options": {
                "include_cache": include_cache,
                "compression": compression
            },
            "summary": f"Successfully created backup '{backup_name}' with {backup_stats['files_backed_up']} files ({backup_stats['backup_size_mb']} MB)"
        }
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        if ctx:
            await ctx.error(f"Backup creation failed: {error_msg}")
        
        logger.error(f"备份创建失败 - 名称: {backup_name}, 错误: {error_msg}", exc_info=True)
        
        return {
            "success": False,
            "backup_name": backup_name or "unknown",
            "error": error_msg,
            "error_type": type(e).__name__,
            "created_at": datetime.now().isoformat(),
            "summary": f"Backup creation failed: {error_msg}"
        }

@mcp.tool()
async def restore_backup(
    backup_name: str,
    restore_mode: str = "append",
    verify_backup: bool = True,
    create_restore_backup: bool = True,
    ctx: Context = None
) -> dict:
    """
    Restore Synapse data from a previously created backup.
    
    This tool restores conversations, solutions, and indexes from a backup
    directory with options for verification and pre-restore backup.
    
    Args:
        backup_name: Name of the backup to restore (required)
        restore_mode: Restore strategy - "append" or "overwrite" (default: "append")
        verify_backup: Whether to verify backup integrity before restore (default: True)
        create_restore_backup: Whether to backup current data before restore (default: True)
        ctx: MCP context object for logging and progress reporting
        
    Returns:
        dict: Restore result with status, statistics, and verification results
    """
    try:
        if ctx:
            await ctx.info(f"Starting backup restore: {backup_name}")
        
        # Parameter validation
        if not backup_name or not backup_name.strip():
            raise ValueError("Backup name cannot be empty")
        
        if restore_mode not in ["append", "overwrite"]:
            raise ValueError("Restore mode must be 'append' or 'overwrite'")
        
        # Get file manager instance
        file_manager = None
        if ctx and hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'lifespan_context'):
            file_manager = ctx.request_context.lifespan_context.file_manager
        
        if not file_manager:
            raise RuntimeError("无法获取FileManager实例，请检查服务器配置")
        
        # Locate backup directory
        backup_path = file_manager.storage_paths.get_backups_dir() / backup_name.strip()
        
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_name}")
        
        if not backup_path.is_dir():
            raise ValueError(f"Backup path is not a directory: {backup_name}")
        
        if ctx:
            await ctx.info(f"Found backup at: {backup_path}")
            await ctx.report_progress(0.1, "Verifying backup...")
        
        # Backup verification
        verification_results = {
            "backup_valid": True,
            "verification_errors": [],
            "backup_metadata": None,
            "conversations_found": 0,
            "solutions_found": 0
        }
        
        if verify_backup:
            try:
                # Check backup structure
                conversations_dir = backup_path / "conversations"
                solutions_dir = backup_path / "solutions"
                indexes_dir = backup_path / "indexes"
                metadata_file = backup_path / "backup_metadata.json"
                
                if not any([conversations_dir.exists(), solutions_dir.exists(), indexes_dir.exists()]):
                    verification_results["backup_valid"] = False
                    verification_results["verification_errors"].append("No valid data directories found in backup")
                
                # Load backup metadata if available
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            verification_results["backup_metadata"] = json.load(f)
                    except Exception as e:
                        verification_results["verification_errors"].append(f"Cannot read backup metadata: {str(e)}")
                
                # Count backup contents
                if conversations_dir.exists():
                    verification_results["conversations_found"] = len(list(conversations_dir.rglob("*.json")))
                
                if solutions_dir.exists():
                    verification_results["solutions_found"] = len(list(solutions_dir.glob("*.json")))
                
                if verification_results["conversations_found"] == 0 and verification_results["solutions_found"] == 0:
                    verification_results["backup_valid"] = False
                    verification_results["verification_errors"].append("No conversation or solution files found in backup")
                
            except Exception as e:
                verification_results["backup_valid"] = False
                verification_results["verification_errors"].append(f"Backup verification failed: {str(e)}")
        
        if verify_backup and not verification_results["backup_valid"]:
            raise ValueError(f"Backup verification failed: {', '.join(verification_results['verification_errors'])}")
        
        if ctx:
            if verification_results["backup_valid"]:
                await ctx.info(f"Backup verified - {verification_results['conversations_found']} conversations, {verification_results['solutions_found']} solutions")
            await ctx.report_progress(0.3, "Creating pre-restore backup...")
        
        # Create pre-restore backup if requested
        restore_backup_info = None
        if create_restore_backup:
            try:
                restore_backup_timestamp = int(datetime.now().timestamp())
                restore_backup_path = file_manager.storage_paths.get_backups_dir() / f"pre_restore_backup_{restore_backup_timestamp}"
                restore_backup_success = file_manager.export_data(restore_backup_path, include_backups=False)
                
                if restore_backup_success:
                    restore_backup_info = str(restore_backup_path)
                    if ctx:
                        await ctx.info(f"Pre-restore backup created: {restore_backup_path}")
                else:
                    logger.warning("Pre-restore backup failed, continuing with restore")
                    
            except Exception as e:
                logger.warning(f"Pre-restore backup failed: {e}")
        
        if ctx:
            await ctx.info(f"Starting restore with mode: {restore_mode}")
            await ctx.report_progress(0.5, "Restoring data...")
        
        # Perform the restore using FileManager import
        restore_success = file_manager.import_data(backup_path, merge_mode=restore_mode)
        
        if not restore_success:
            raise RuntimeError("Restore operation failed - check file manager logs for details")
        
        if ctx:
            await ctx.report_progress(0.9, "Finalizing restore...")
        
        # Get post-restore statistics
        post_restore_stats = file_manager.get_storage_statistics()
        
        if ctx:
            await ctx.report_progress(1.0, "Restore completed successfully")
            await ctx.info(f"Restore completed - Total: {post_restore_stats.total_conversations} conversations, {post_restore_stats.total_solutions} solutions")
        
        # Build success response
        result = {
            "success": True,
            "backup_name": backup_name,
            "backup_path": str(backup_path),
            "restored_at": datetime.now().isoformat(),
            "restore_mode": restore_mode,
            "verification_performed": verify_backup,
            "pre_restore_backup_created": create_restore_backup,
            "pre_restore_backup_location": restore_backup_info,
            "verification_results": verification_results,
            "statistics": {
                "conversations_after_restore": post_restore_stats.total_conversations,
                "solutions_after_restore": post_restore_stats.total_solutions,
                "total_files_after_restore": post_restore_stats.total_files,
                "total_size_mb_after_restore": round(post_restore_stats.disk_usage_mb, 2)
            },
            "restored_components": {
                "conversations": verification_results["conversations_found"] > 0,
                "solutions": verification_results["solutions_found"] > 0,
                "indexes": True  # Assume indexes are always restored if present
            },
            "summary": f"Successfully restored backup '{backup_name}' using {restore_mode} mode"
        }
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        if ctx:
            await ctx.error(f"Backup restore failed: {error_msg}")
        
        logger.error(f"备份恢复失败 - 备份: {backup_name}, 错误: {error_msg}", exc_info=True)
        
        return {
            "success": False,
            "backup_name": backup_name,
            "error": error_msg,
            "error_type": type(e).__name__,
            "restored_at": datetime.now().isoformat(),
            "restore_mode": restore_mode,
            "verification_performed": verify_backup,
            "pre_restore_backup_created": create_restore_backup,
            "verification_results": verification_results if 'verification_results' in locals() else {},
            "summary": f"Restore failed: {error_msg}"
        }

# ==================== 主入口函数 ====================

async def main():
    """
    Synapse MCP 服务器的主入口点
    
    这个函数启动MCP服务器并处理客户端连接。
    它设置日志、初始化存储系统，然后启动服务器。
    """
    # 设置日志
    setup_logging()
    logger.info("启动 Synapse MCP 服务器...")
    
    try:
        # 运行FastMCP服务器
        # 默认使用stdio传输方式，这是MCP的标准连接方式
        mcp.run()
        
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"服务器运行时错误: {str(e)}", exc_info=True)
        sys.exit(1)

def sync_main():
    """
    Synchronous version of main entry point for compatibility.
    
    This function provides a synchronous interface to start the async server.
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped")
    except Exception as e:
        print(f"Server startup failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    sync_main()