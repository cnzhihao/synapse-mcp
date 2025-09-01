# Synapse MCP

智能记忆和知识检索MCP工具，为AI编程助手提供对话历史存储和上下文增强功能。

## 功能介绍

Synapse是一个Model Context Protocol (MCP)服务器，帮助AI助手记忆和利用历史对话内容：

- **对话存储** - 自动保存AI对话记录，包含标签和分类
- **智能搜索** - 基于关键词和标签的三层搜索系统
- **上下文注入** - 自动为当前对话注入相关历史上下文
- **解决方案提取** - 从对话中提取可重用的代码和解决方案
- **数据管理** - 导入导出、备份恢复功能

## 安装使用

### 要求
- Python 3.10+
- uv (推荐) 或 pip

### 安装
```bash
git clone <repository-url>
cd synapse-mcp
uv sync
```

### 运行
```bash
# 使用 uv (推荐)
uv run mcp run src/synapse/server.py


# 开发模式 (带热重载)
uv run mcp dev src/synapse/server.py
```

## MCP 工具

### save-conversation
保存当前对话到知识库
- 参数: title, tags, category, importance等
- 支持AI自动分析和标签提取

### search-knowledge  
搜索历史对话和解决方案
- 参数: query, category, tags, time_range, limit等
- 三层搜索: 精确匹配、标签过滤、内容匹配

### inject-context
为当前对话注入相关历史上下文
- 参数: current_query, max_items, relevance_threshold等
- 智能相关性计算和上下文推荐

### extract-solutions
从对话中提取可重用解决方案
- 参数: conversation_id, extract_type, min_reusability_score等
- 支持代码、方法、模式三种类型提取

### 数据管理工具
- **export-data** - 导出所有数据
- **import-data** - 导入数据
- **backup-data** - 创建备份
- **restore-backup** - 恢复备份
- **get-storage-info** - 查看存储信息

## 配置 MCP 客户端

### 通用 mcp.json 配置

创建 `mcp.json` 配置文件：

```json
{
  "mcpServers": {
    "synapse": {
      "command": "uv",
      "args": ["--directory", "/path/to/synapse-mcp", "run", "mcp", "run", "/path/to/synapse-mcp/src/synapse/server.py"]
      }
  }
}
```

### Claude Code 安装

使用 Claude Code CLI 添加 Synapse MCP：

```bash
claude mcp add synapse-mcp --scope user -- uv --directory /path/to/synapse-mcp run mcp run /path/to/synapse-mcp/src/synapse/server.py
```

替换 `/path/to/synapse-mcp` 为你的实际项目路径。

**注意**: 
- `--scope user` 表示用户级别安装
- 确保项目路径使用绝对路径
- 安装后可通过 `claude mcp list` 查看已安装的 MCP 服务
