"""
Synapse MCP Server 主服务器模块

这个模块包含 MCP (Model Context Protocol) 服务器的完整实现，
提供智能记忆和知识检索功能。

主要功能：
1. 使用FastMCP框架创建MCP服务器
2. 注册所有MCP工具（save-conversation, search-knowledge等）
3. 提供统一的错误处理和响应格式
4. 参数验证和服务器生命周期管理

作为MCP服务器，它遵循MCP协议标准，与Claude等AI助手无缝集成。
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
import sys

from mcp.server.fastmcp import FastMCP, Context

from synapse.models import ConversationRecord, Solution
from synapse.storage.paths import StoragePaths
from synapse.storage.initializer import StorageInitializer, initialize_synapse_storage
from synapse.storage.file_manager import FileManager
from synapse.utils.logging_config import setup_logging
from synapse.tools.save_conversation import SaveConversationTool
from synapse.tools.extract_solutions import ExtractSolutionsTool
from synapse.tools.search_knowledge import SearchKnowledgeTool
from synapse.tools.inject_context import InjectContextTool

# 设置日志
logger = logging.getLogger(__name__)

# Mock数据库类（用于示例）
class Database:
    """Mock数据库类用于演示存储功能"""
    
    @classmethod
    async def connect(cls) -> "Database":
        """连接到数据库"""
        logger.info("数据库连接已建立")
        return cls()
    
    async def disconnect(self) -> None:
        """断开数据库连接"""
        logger.info("数据库连接已断开")
    
    async def save_conversation(self, conversation: ConversationRecord) -> str:
        """保存对话记录（模拟）"""
        logger.info(f"保存对话记录: {conversation.id}")
        return conversation.id
    
    async def search_conversations(self, query: str, limit: int = 10) -> list:
        """搜索对话记录（模拟）"""
        logger.info(f"搜索查询: '{query}', 限制: {limit}")
        return [
            {
                "id": "conv_20240115_001",
                "title": f"关于'{query}'的解决方案",
                "snippet": f"这是一个关于{query}的详细解释和代码示例...",
                "match_score": 0.95,
                "created_at": "2024-01-15T10:30:00Z",
                "tags": [query.lower(), "programming"],
                "type": "conversation"
            }
        ]

@dataclass
class AppContext:
    """应用上下文，包含数据库连接等资源"""
    db: Database
    storage_paths: StoragePaths
    file_manager: FileManager
    save_conversation_tool: SaveConversationTool
    extract_solutions_tool: ExtractSolutionsTool
    search_knowledge_tool: SearchKnowledgeTool
    inject_context_tool: InjectContextTool

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """
    管理应用生命周期
    
    在服务器启动时初始化资源，关闭时清理资源
    """
    logger.info("正在启动 Synapse MCP 服务器...")
    
    # 初始化资源
    try:
        # 初始化存储系统
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, initialize_synapse_storage)
        
        # 连接数据库
        db = await Database.connect()
        
        # 创建存储路径管理器
        storage_paths = StoragePaths()
        
        # 创建文件管理器
        file_manager = FileManager(storage_paths)
        
        # 创建保存对话工具
        save_conversation_tool = SaveConversationTool(storage_paths)
        
        # 创建解决方案提取工具
        extract_solutions_tool = ExtractSolutionsTool(storage_paths)
        
        # 创建搜索知识工具
        search_knowledge_tool = SearchKnowledgeTool(storage_paths, file_manager)
        
        # 创建上下文注入工具
        inject_context_tool = InjectContextTool(storage_paths, file_manager, search_knowledge_tool)
        
        # 创建应用上下文
        app_context = AppContext(
            db=db, 
            storage_paths=storage_paths,
            file_manager=file_manager,
            save_conversation_tool=save_conversation_tool,
            extract_solutions_tool=extract_solutions_tool,
            search_knowledge_tool=search_knowledge_tool,
            inject_context_tool=inject_context_tool
        )
        
        logger.info("Synapse MCP 服务器启动成功")
        
        yield app_context
        
    except Exception as e:
        logger.error(f"服务器启动失败: {str(e)}")
        raise
    finally:
        # 清理资源
        logger.info("正在关闭 Synapse MCP 服务器...")
        if 'db' in locals():
            await db.disconnect()
        logger.info("Synapse MCP 服务器已关闭")

# 创建FastMCP服务器实例
mcp = FastMCP("synapse-mcp", lifespan=app_lifespan)

# ==================== MCP工具实现 ====================

@mcp.tool()
async def save_conversation(
    title: str,
    content: str,
    tags: list[str] = None,
    category: str = None, 
    importance: int = None,
    check_duplicates: bool = True,
    ctx: Context = None
) -> dict:
    """
    保存AI对话记录到知识库中，支持智能标签提取、摘要生成和重复检测
    
    这个工具提供完整的对话保存功能：
    - 自动清理和格式化对话内容
    - 智能提取编程语言、技术栈等标签
    - 基于内容生成有意义的摘要
    - 自动评估对话重要性等级
    - 检测并提醒重复对话
    - 更新搜索索引以支持快速查询
    
    Args:
        title: 对话主题标题（必需）
        content: 完整的对话内容（必需）
        tags: 用户自定义标签列表（可选，将与自动提取的标签合并）
        category: 对话分类（可选，如不指定将自动推断）
        importance: 重要程度 1-5（可选，如不指定将自动评估）
        check_duplicates: 是否检查重复对话（默认True）
        ctx: MCP上下文对象
        
    Returns:
        dict: 详细的保存结果信息，包括：
            - success: 保存是否成功
            - conversation: 保存的对话详细信息
            - duplicates_found: 发现的重复对话数量
            - duplicate_ids: 重复对话的ID列表
            - storage_path: 文件存储路径
    """
    try:
        if ctx:
            await ctx.info(f"开始保存对话: {title}")
        
        # 基础参数验证
        if not title or not title.strip():
            raise ValueError("对话标题不能为空")
        
        if not content or not content.strip():
            raise ValueError("对话内容不能为空")
        
        if importance is not None and (importance < 1 or importance > 5):
            raise ValueError("重要性等级必须在1-5之间")
        
        # 获取保存对话工具实例
        save_tool = None
        if ctx and hasattr(ctx.request_context, 'lifespan_context'):
            save_tool = ctx.request_context.lifespan_context.save_conversation_tool
        
        if not save_tool:
            # 如果无法获取工具实例，创建一个临时实例
            from synapse.storage.paths import StoragePaths
            storage_paths = StoragePaths()
            save_tool = SaveConversationTool(storage_paths)
            logger.warning("使用临时SaveConversationTool实例")
        
        if ctx:
            await ctx.info("正在处理对话内容...")
        
        # 使用SaveConversationTool进行保存
        result = save_tool.save_conversation(
            title=title.strip(),
            content=content.strip(),
            user_tags=tags,
            user_category=category,
            user_importance=importance,
            check_duplicates=check_duplicates
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
                "code_blocks_found": conversation_info.get("code_blocks_count", 0)
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
        if ctx and hasattr(ctx.request_context, 'lifespan_context'):
            search_tool = ctx.request_context.lifespan_context.search_knowledge_tool
        
        if not search_tool:
            # 如果无法获取工具实例，创建一个临时实例
            from synapse.storage.paths import StoragePaths
            from synapse.storage.file_manager import FileManager
            storage_paths = StoragePaths()
            file_manager = FileManager(storage_paths)
            search_tool = SearchKnowledgeTool(storage_paths, file_manager)
            logger.warning("使用临时SearchKnowledgeTool实例")
        
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
async def extract_solutions(
    conversation_id: str,
    extract_type: str = "all",
    auto_tag: bool = True,
    min_reusability_score: float = 0.3,
    save_solutions: bool = False,
    ctx: Context = None
) -> dict:
    """
    从对话记录中智能提取可重用的代码片段、方法和设计模式
    
    这个工具使用先进的文本分析和机器学习技术，从对话记录中自动识别
    和提取有价值的解决方案。支持多种类型的内容提取和质量评估。
    
    Args:
        conversation_id: 要提取解决方案的对话ID（必需）
        extract_type: 提取类型 ("code", "approach", "pattern", "all")
        auto_tag: 是否自动识别和分类标签（默认True）
        min_reusability_score: 最小可重用性阈值 0.0-1.0（默认0.3）
        save_solutions: 是否将提取的解决方案保存到文件系统（默认False）
        ctx: MCP上下文对象
        
    Returns:
        dict: 详细的提取结果，包括：
            - solutions: 提取的解决方案列表
            - statistics: 提取统计信息
            - extraction_summary: 人性化的提取摘要
    """
    try:
        if ctx:
            await ctx.info(f"开始智能提取对话 {conversation_id} 中的解决方案")
        
        # 基础参数验证
        if not conversation_id or not conversation_id.strip():
            raise ValueError("对话ID不能为空")
        
        if extract_type not in ["code", "approach", "pattern", "all"]:
            raise ValueError("提取类型必须是 'code', 'approach', 'pattern' 或 'all'")
        
        if not (0.0 <= min_reusability_score <= 1.0):
            raise ValueError("可重用性阈值必须在0.0-1.0之间")
        
        # 获取解决方案提取工具实例
        extract_tool = None
        if ctx and hasattr(ctx.request_context, 'lifespan_context'):
            extract_tool = ctx.request_context.lifespan_context.extract_solutions_tool
        
        if not extract_tool:
            # 如果无法获取工具实例，创建一个临时实例
            from synapse.storage.paths import StoragePaths
            storage_paths = StoragePaths()
            extract_tool = ExtractSolutionsTool(storage_paths)
            logger.warning("使用临时ExtractSolutionsTool实例")
        
        if ctx:
            await ctx.info(f"开始分析对话内容，提取类型: {extract_type}")
            if min_reusability_score > 0.3:
                await ctx.info(f"使用较高的质量阈值: {min_reusability_score}")
        
        # 使用ExtractSolutionsTool进行智能提取
        result = extract_tool.extract_solutions(
            conversation_id=conversation_id.strip(),
            extract_type=extract_type,
            auto_tag=auto_tag,
            min_reusability_score=min_reusability_score,
            save_solutions=save_solutions
        )
        
        # 检查提取结果
        if not result.get("success", False):
            error_msg = result.get("error", "未知错误")
            raise RuntimeError(f"提取失败: {error_msg}")
        
        solutions_count = result.get("total_extracted", 0)
        statistics = result.get("statistics", {})
        
        if ctx:
            await ctx.info(f"智能提取完成，找到 {solutions_count} 个高质量解决方案")
            
            # 提供详细的统计信息
            if statistics:
                code_blocks = statistics.get("code_blocks_found", 0)
                processing_time = statistics.get("processing_time_ms", 0)
                
                if code_blocks > 0:
                    await ctx.info(f"发现 {code_blocks} 个代码块")
                
                await ctx.info(f"处理时间: {processing_time:.0f}ms")
                
                # 报告质量过滤情况
                raw_extracted = statistics.get("raw_solutions_extracted", 0)
                after_quality = statistics.get("after_quality_filter", 0)
                if raw_extracted > after_quality:
                    await ctx.info(f"质量过滤：{raw_extracted} → {after_quality} 个解决方案")
                
                # 报告保存情况
                if save_solutions:
                    saved_count = statistics.get("solutions_saved", 0)
                    await ctx.info(f"已保存 {saved_count} 个解决方案到文件系统")
        
        # 构建返回结果（保持与原API兼容，同时提供更多信息）
        return {
            # 基本兼容信息
            "solutions": result.get("solutions", []),
            "conversation_id": conversation_id,
            "extract_type": extract_type,
            "total_extracted": solutions_count,
            "auto_tag_enabled": auto_tag,
            
            # 扩展信息
            "extraction_summary": result.get("extraction_summary", ""),
            "statistics": statistics,
            "quality_settings": {
                "min_reusability_score": min_reusability_score,
                "auto_tag": auto_tag,
                "save_solutions": save_solutions
            },
            "success": True
        }
        
    except Exception as e:
        error_msg = str(e)
        if ctx:
            await ctx.error(f"解决方案提取失败: {error_msg}")
        
        logger.error(f"解决方案提取失败 - 对话ID: {conversation_id}, 错误: {error_msg}", exc_info=True)
        
        # 返回错误信息而不是抛出异常，让调用方能够处理
        return {
            "success": False,
            "error": error_msg,
            "error_type": type(e).__name__,
            "conversation_id": conversation_id,
            "extract_type": extract_type,
            "solutions": [],
            "total_extracted": 0,
            "auto_tag_enabled": auto_tag
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
        if ctx and hasattr(ctx.request_context, 'lifespan_context'):
            inject_tool = ctx.request_context.lifespan_context.inject_context_tool
        
        if not inject_tool:
            # 如果无法获取工具实例，创建一个临时实例
            from synapse.storage.paths import StoragePaths
            from synapse.storage.file_manager import FileManager
            from synapse.tools.search_knowledge import SearchKnowledgeTool
            storage_paths = StoragePaths()
            file_manager = FileManager(storage_paths)
            search_tool = SearchKnowledgeTool(storage_paths, file_manager)
            inject_tool = InjectContextTool(storage_paths, file_manager, search_tool)
            logger.warning("使用临时InjectContextTool实例")
        
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
    同步版本的主入口点，用于兼容性
    
    这个函数提供了一个同步接口来启动异步服务器。
    """
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"服务器启动失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    sync_main()