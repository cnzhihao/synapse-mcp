"""
Synapse MCP Server - 智能记忆和知识检索MCP工具

Synapse 是一个 Model Context Protocol (MCP) 服务器，为 AI 编程助手提供
智能记忆和知识检索功能。它能够捕获、存储和检索对话历史、解决方案和
最佳实践，从而增强 AI 的上下文理解能力。

主要功能:
- 对话记录和存储
- 智能解决方案提取
- 基于关键词和标签的知识检索
- 上下文注入和增强

作者: Your Name
版本: 0.1.0
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

# 导出主要组件
from synapse.server import main

__all__ = ["main", "__version__", "__author__", "__email__"]