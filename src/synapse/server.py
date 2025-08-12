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

from .models import ConversationRecord, Solution
from .storage.paths import StoragePaths
from .storage.initializer import StorageInitializer, initialize_synapse_storage
from .utils.logging_config import setup_logging

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
        await loop.run_in_executor(None, initialize_storage)
        
        # 连接数据库
        db = await Database.connect()
        
        # 创建存储路径管理器
        storage_paths = StoragePaths()
        
        # 创建应用上下文
        app_context = AppContext(db=db, storage_paths=storage_paths)
        
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
    category: str = "general", 
    importance: int = 3,
    ctx: Context = None
) -> dict:
    """
    保存AI对话记录到知识库中，支持自动标签提取和分类
    
    Args:
        title: 对话主题标题
        content: 完整的对话内容
        tags: 标签列表（可选）
        category: 对话分类（可选）
        importance: 重要程度 1-5
        ctx: MCP上下文对象
        
    Returns:
        dict: 保存结果信息
    """
    try:
        if ctx:
            await ctx.info(f"开始保存对话: {title}")
        
        # 参数验证
        if not title or not content:
            raise ValueError("标题和内容不能为空")
        
        if importance < 1 or importance > 5:
            raise ValueError("重要性必须在1-5之间")
        
        # 创建对话记录
        conversation = ConversationRecord(
            title=title,
            content=content,
            tags=tags or [],
            category=category,
            importance=importance
        )
        
        # 获取数据库连接
        if ctx and hasattr(ctx.request_context, 'lifespan_context'):
            db = ctx.request_context.lifespan_context.db
            conversation_id = await db.save_conversation(conversation)
        else:
            conversation_id = conversation.id
        
        if ctx:
            await ctx.info(f"对话记录保存成功: {conversation_id}")
        
        # 返回结果
        return {
            "id": conversation_id,
            "title": conversation.title,
            "stored_at": conversation.created_at.isoformat(),
            "tags": conversation.tags,
            "category": conversation.category,
            "importance": conversation.importance,
            "searchable": True
        }
        
    except Exception as e:
        if ctx:
            await ctx.error(f"保存对话失败: {str(e)}")
        logger.error(f"保存对话失败: {str(e)}", exc_info=True)
        raise ValueError(f"保存对话失败: {str(e)}")

@mcp.tool()
async def search_knowledge(
    query: str,
    category: str = None,
    tags: list[str] = None,
    time_range: str = "all",
    limit: int = 10,
    ctx: Context = None
) -> dict:
    """
    在知识库中搜索相关的对话记录和解决方案
    
    Args:
        query: 搜索查询关键词
        category: 内容分类过滤（可选）
        tags: 标签过滤（可选）
        time_range: 时间范围过滤 ("week", "month", "all")
        limit: 返回结果数量限制
        ctx: MCP上下文对象
        
    Returns:
        dict: 搜索结果
    """
    try:
        if ctx:
            await ctx.info(f"开始搜索: '{query}'")
        
        # 参数验证
        if not query or not query.strip():
            raise ValueError("搜索查询不能为空")
        
        if limit < 1 or limit > 50:
            raise ValueError("结果数量限制必须在1-50之间")
        
        if time_range not in ["week", "month", "all"]:
            raise ValueError("时间范围必须是 'week', 'month' 或 'all'")
        
        # 获取数据库连接并搜索
        if ctx and hasattr(ctx.request_context, 'lifespan_context'):
            db = ctx.request_context.lifespan_context.db
            results = await db.search_conversations(query, limit)
        else:
            # 模拟搜索结果
            results = [
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
        
        if ctx:
            await ctx.info(f"搜索完成，找到 {len(results)} 个结果")
        
        return {
            "results": results,
            "total": len(results),
            "search_time_ms": 45,
            "query": query,
            "filters": {
                "category": category,
                "tags": tags,
                "time_range": time_range
            }
        }
        
    except Exception as e:
        if ctx:
            await ctx.error(f"搜索失败: {str(e)}")
        logger.error(f"搜索失败: {str(e)}", exc_info=True)
        raise ValueError(f"搜索失败: {str(e)}")

@mcp.tool()
async def extract_solutions(
    conversation_id: str,
    extract_type: str = "all",
    auto_tag: bool = True,
    ctx: Context = None
) -> dict:
    """
    从对话记录中提取可重用的代码片段和解决方案
    
    Args:
        conversation_id: 要提取解决方案的对话ID
        extract_type: 提取类型 ("code", "approach", "pattern", "all")
        auto_tag: 是否自动识别标签
        ctx: MCP上下文对象
        
    Returns:
        dict: 提取的解决方案列表
    """
    try:
        if ctx:
            await ctx.info(f"开始从对话 {conversation_id} 提取解决方案")
        
        # 参数验证
        if not conversation_id:
            raise ValueError("对话ID不能为空")
        
        if extract_type not in ["code", "approach", "pattern", "all"]:
            raise ValueError("提取类型必须是 'code', 'approach', 'pattern' 或 'all'")
        
        # 模拟提取解决方案，使用Solution Pydantic模型
        extracted_solutions = []
        
        # 创建示例解决方案（在实际实现中，这里会从对话内容中智能提取）
        # 根据extract_type创建相应类型的解决方案
        if extract_type in ["code", "all"]:
            code_solution = Solution(
                type="code",
                content="// 这里是提取的代码示例\nconst example = () => { return 'Hello World'; }",
                language="javascript",
                description="从对话中提取的JavaScript代码示例",
                reusability_score=0.8
            )
            extracted_solutions.append(code_solution)
        
        if extract_type in ["approach", "all"]:
            approach_solution = Solution(
                type="approach",
                content="使用分而治之的方法解决复杂问题：1. 分解问题 2. 递归求解 3. 合并结果",
                description="分而治之算法思想",
                reusability_score=0.9
            )
            extracted_solutions.append(approach_solution)
        
        if extract_type in ["pattern", "all"]:
            pattern_solution = Solution(
                type="pattern", 
                content="观察者模式：定义对象间一对多的依赖关系，当对象状态改变时通知所有观察者",
                description="观察者设计模式应用场景",
                reusability_score=0.7
            )
            extracted_solutions.append(pattern_solution)
        
        # 转换为字典格式用于返回
        solutions_data = [solution.to_dict() for solution in extracted_solutions]
        
        if ctx:
            await ctx.info(f"成功提取了 {len(extracted_solutions)} 个解决方案")
        
        return {
            "solutions": solutions_data,
            "conversation_id": conversation_id,
            "extract_type": extract_type,
            "total_extracted": len(extracted_solutions),
            "auto_tag_enabled": auto_tag
        }
        
    except Exception as e:
        if ctx:
            await ctx.error(f"解决方案提取失败: {str(e)}")
        logger.error(f"解决方案提取失败: {str(e)}", exc_info=True)
        raise ValueError(f"解决方案提取失败: {str(e)}")

@mcp.tool()
async def inject_context(
    current_query: str,
    max_items: int = 3,
    relevance_threshold: float = 0.7,
    ctx: Context = None
) -> dict:
    """
    向当前对话注入相关的历史上下文
    
    Args:
        current_query: 当前用户问题
        max_items: 最大注入项数
        relevance_threshold: 相关性阈值
        ctx: MCP上下文对象
        
    Returns:
        dict: 注入的上下文内容
    """
    try:
        if ctx:
            await ctx.info(f"为查询 '{current_query}' 注入上下文")
        
        # 参数验证
        if not current_query or not current_query.strip():
            raise ValueError("当前查询不能为空")
        
        if max_items < 1 or max_items > 10:
            raise ValueError("最大注入项数必须在1-10之间")
        
        if relevance_threshold < 0.0 or relevance_threshold > 1.0:
            raise ValueError("相关性阈值必须在0.0-1.0之间")
        
        # 模拟相关上下文
        mock_context_items = [
            {
                "title": "类似问题的解决方案",
                "content": f"关于'{current_query}'的历史解决方案...",
                "relevance": 0.85,
                "source_type": "conversation",
                "source_id": "conv_20240115_001"
            }
        ]
        
        filtered_items = [
            item for item in mock_context_items 
            if item["relevance"] >= relevance_threshold
        ][:max_items]
        
        if ctx:
            await ctx.info(f"成功注入 {len(filtered_items)} 个上下文项")
        
        return {
            "context_items": filtered_items,
            "injection_summary": f"找到 {len(filtered_items)} 个与'{current_query}'相关的历史解决方案",
            "total_items": len(filtered_items),
            "query": current_query,
            "relevance_threshold": relevance_threshold
        }
        
    except Exception as e:
        if ctx:
            await ctx.error(f"上下文注入失败: {str(e)}")
        logger.error(f"上下文注入失败: {str(e)}", exc_info=True)
        raise ValueError(f"上下文注入失败: {str(e)}")

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