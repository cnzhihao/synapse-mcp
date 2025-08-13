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
from contextlib import asynccontextmanager
from dataclasses import dataclass
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
    content: str,
    focus: str = "comprehensive"
) -> str:
    """
    Conversation analysis prompt template.
    
    Generates prompts for analyzing technical conversations to extract
    summaries, tags, importance ratings, and other metadata.
    
    Args:
        title: Conversation title
        content: Conversation content
        focus: Analysis focus ("comprehensive", "summary", "tags", "solutions")
    
    Returns:
        str: Formatted analysis prompt
    """
    base_prompt = f"""Please analyze the following technical conversation and provide structured analysis results.

## Conversation Information
**Title**: {title}
**Content**: 
{content[:2000]}{'...' if len(content) > 2000 else ''}

## Analysis Requirements
Please provide the following analysis results (JSON format):

```json
{{
    "summary": "Concise conversation summary (1-2 sentences)",
    "tags": ["technical_tag1", "technical_tag2", "..."],
    "importance": "Importance rating from 1-5",
    "category": "Conversation category (e.g., problem-solving, learning, code-review)",
    "has_solutions": "true/false",
    "solution_indicators": ["Types of solutions included"]
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
    content: str,
    tags: list[str] = None,
    category: str = None, 
    importance: int = None,
    check_duplicates: bool = True,
    # AI分析结果参数（由客户端通过prompt获得后传入）
    ai_summary: str = None,
    ai_tags: list[str] = None,
    ai_importance: int = None,
    ai_category: str = None,
    ai_solutions: list[dict] = None,
    ctx: Context = None
) -> dict:
    """
    Save AI conversation records to knowledge base with AI analysis support.
    
    This tool focuses on data storage and management:
    - Accept user-specified or AI-analyzed metadata
    - Clean and format conversation content
    - Detect and notify duplicate conversations
    - Update search indexes for fast queries
    
    Correct usage:
    1. First call conversation_analysis_prompt to get AI analysis
    2. Pass AI analysis results to this tool for saving
    
    Args:
        title: Conversation topic title (required)
        content: Complete conversation content (required)
        tags: User-defined tag list (optional)
        category: User-specified conversation category (optional)
        importance: User-specified importance level 1-5 (optional)
        check_duplicates: Whether to check for duplicate conversations (default True)
        ai_summary: AI-generated summary (obtained via prompt)
        ai_tags: AI-extracted tag list (obtained via prompt)
        ai_importance: AI-assessed importance (obtained via prompt)
        ai_category: AI-inferred category (obtained via prompt)
        ai_solutions: AI-extracted solution list (obtained via prompt)
        ctx: MCP context object
        
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
        
        if not content or not content.strip():
            raise ValueError("Conversation content cannot be empty")
        
        if importance is not None and (importance < 1 or importance > 5):
            raise ValueError("Importance level must be between 1-5")
        
        # Get save conversation tool instance
        save_tool = None
        if ctx and hasattr(ctx, 'request_context') and hasattr(ctx.request_context, 'lifespan_context'):
            save_tool = ctx.request_context.lifespan_context.save_conversation_tool
        
        if not save_tool:
            raise RuntimeError("无法获取SaveConversationTool实例，请检查服务器配置")
        
        if ctx:
            await ctx.info("正在处理对话内容...")
        
        # 使用SaveConversationTool进行保存
        result = await save_tool.save_conversation(
            title=title.strip(),
            content=content.strip(),
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
        
        # Get comprehensive storage status
        storage_status = initializer.get_storage_status()
        
        # Calculate storage size in MB
        total_size_mb = storage_status["total_size_bytes"] / (1024 * 1024) if storage_status["total_size_bytes"] > 0 else 0.0
        
        # Build response with comprehensive information
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
            
            # Application info
            "server_status": "running",
            "version": "1.0.0",
            "platform": sys.platform,
            
            # Statistics (placeholder - will be implemented when file manager is ready)
            "total_conversations": 0,
            "total_solutions": 0,
            "last_maintenance": None
        }
        
        if ctx:
            await ctx.info(f"Storage information retrieved successfully - Initialized: {storage_status['initialized']}")
        
        return storage_info
        
    except Exception as e:
        if ctx:
            await ctx.error(f"Failed to retrieve storage information: {str(e)}")
        logger.error(f"Failed to retrieve storage information: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to retrieve storage information: {str(e)}")

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