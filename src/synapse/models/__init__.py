"""
Synapse MCP 数据模型模块

这个包包含了 Synapse MCP 系统中使用的所有数据模型，包括：
- ConversationRecord: 对话记录数据模型
- Solution: 解决方案数据模型

这些模型遵循 MCP 协议要求，使用 Pydantic 进行数据验证和序列化。
"""

from .conversation import ConversationRecord, Solution

__all__ = ["ConversationRecord", "Solution"]