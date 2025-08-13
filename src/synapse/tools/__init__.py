"""
Synapse MCP 工具模块

这个包包含了所有 MCP 工具的实现，包括：
- save_conversation: 保存对话记录的 MCP 工具
- extract_solutions: 提取解决方案的 MCP 工具
- search_knowledge: 搜索知识库的 MCP 工具
- inject_context: 注入上下文的 MCP 工具
- storage_management: 存储管理工具
- data_management: 数据导入导出工具
- backup_management: 备份恢复工具

每个工具都遵循 MCP 协议规范，提供标准化的输入输出接口。
"""

from .save_conversation import SaveConversationTool
from .extract_solutions import ExtractSolutionsTool
from .search_knowledge import SearchKnowledgeTool
from .inject_context import InjectContextTool

__all__ = [
    "SaveConversationTool",
    "ExtractSolutionsTool", 
    "SearchKnowledgeTool",
    "InjectContextTool"
]