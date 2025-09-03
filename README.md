# Synapse MCP

An intelligent memory and knowledge retrieval server built with Python MCP (Model Context Protocol) that helps AI programming assistants remember and reuse solutions from previous conversations.

## 🔑 核心特点

- **解决方案为中心**: 主要存储和检索的是从对话中提取的解决方案，不是完整对话
- **简单可靠**: 使用grep文本搜索策略，快速、稳定、易理解
- **AI引导工作流**: 工具提供结构化数据，AI负责语义理解和应用
- **分层存储**: 对话摘要和解决方案分开管理，便于维护和查询

## 🚀 Features

### Core MCP Tools

**🤖 save-conversation** - 对话摘要存储
- 保存AI分析生成的对话摘要、标签和元数据到知识库
- 如果未提供AI分析，会基于标题关键词自动生成基础分析
- 支持重复检测和用户自定义标签
- 存储格式：摘要+元数据，不保存完整对话内容

**💎 extract-solutions** - 解决方案提取
- 从已保存的对话记录中提取解决方案并单独存储
- 支持按类型（code/approach/pattern）和质量评分过滤
- 解决方案去重和质量评估，建立独立的解决方案库

**🔍 search-knowledge** - 文本搜索  
- 简单grep搜索，在解决方案库中搜索关键词匹配
- 支持多字段搜索（title/content/tags/all），按时间倒序返回
- 提供搜索建议，引导AI尝试不同关键词组合
- 搜索对象：solutions（解决方案），不是完整对话

**🧠 inject-context** - 结果格式化
- 接收搜索结果并格式化为结构化JSON数据
- 返回AI应用指导，帮助AI理解如何使用搜索到的解决方案
- 简单的数据转换工具，不进行复杂的语义处理

### Core MCP Tools

**🤖 save-conversation** - 对话摘要存储
- 保存AI分析生成的对话摘要、标签和元数据到知识库
- 如果未提供AI分析，会基于标题关键词自动生成基础分析
- 支持重复检测和用户自定义标签
- 存储格式：摘要+元数据，不保存完整对话内容

**💎 extract-solutions** - 解决方案提取
- 从已保存的对话记录中提取解决方案并单独存储
- 支持按类型（code/approach/pattern）和质量评分过滤
- 解决方案去重和质量评估，建立独立的解决方案库

**🔍 search-knowledge** - 文本搜索  
- 简单grep搜索，在解决方案库中搜索关键词匹配
- 支持多字段搜索（title/content/tags/all），按时间倒序返回
- 提供搜索建议，引导AI尝试不同关键词组合
- 搜索对象：solutions（解决方案），不是完整对话

**🧠 inject-context** - 结果格式化
- 接收搜索结果并格式化为结构化JSON数据
- 返回AI应用指导，帮助AI理解如何使用搜索到的解决方案
- 简单的数据转换工具，不进行复杂的语义处理



### 数据管理工具

**📤 export-data** - 数据导出
- 导出对话记录、解决方案和索引到指定目录
- 支持备份文件和缓存的可选导出

**📥 import-data** - 数据导入  
- 从导出目录导入数据，支持追加和覆盖模式
- 内置数据验证和预导入备份功能

**📊 get-storage-info** - 存储系统信息
- 获取存储目录状态、使用统计和系统健康信息
- 提供维护建议和备份状态

**💾 backup-data** - 手动备份
- 创建完整的数据备份，包含会话、解决方案和索引
- 支持自定义备份名称和可选压缩

**🔄 restore-backup** - 备份恢复
- 从备份恢复数据，支持完整性验证和预恢复备份
- 灵活的恢复模式（追加/覆盖）

## 📋 Requirements

- Python 3.8+
- MCP (Model Context Protocol) compatible client
- Dependencies managed with `uv`

## 🛠 Installation & Setup

### 1. Clone and Install Dependencies

```bash
git clone <repository-url>
cd synapse-mcp

# Install dependencies using uv (recommended)
uv sync

# Alternative: Direct pip installation
pip3 install -r requirements.txt
```

### 2. Run the MCP Server

```bash
# Using uv (recommended)
uv run python3 src/synapse/server.py

# Alternative: Direct execution  
python3 src/synapse/server.py
```

### 3. Development Mode

```bash
# Run with hot reload and debugging
uv run mcp dev src/synapse/server.py

# Run with additional dependencies
uv run mcp dev src/synapse/server.py --with pandas --with numpy
```

## 🏗 Architecture

### 核心工作流程

```
用户对话 → save_conversation(保存摘要+标签) → extract_solutions(提取解决方案) 
                                               ↓
用户问题 → search_knowledge(grep搜索解决方案) → inject_context(格式化结果)
```

### 系统设计理念

- **解决方案为中心**：主要操作对象是解决方案（solutions），不是完整对话
- **简单有效**：使用grep文本搜索，快速可靠，让AI负责语义理解
- **分层存储**：对话摘要和解决方案分开存储，独立管理
- **AI引导**：工具提供结构化数据，AI负责智能应用

### Storage Structure
```
data/
├── conversations/           # 对话记录存储
│   └── 2024/
│       └── 01/
│           ├── conv_20240115_001.json
│           └── conv_20240115_002.json
├── solutions/              # 提取的解决方案
│   ├── sol_python_001.json
│   └── sol_javascript_002.json
├── indexes/                # 搜索索引
│   ├── keyword_index.json
│   ├── tag_index.json
│   └── metadata.json
├── backups/                # 备份存储
│   └── backup_20240115/
└── logs/                   # 日志文件
```

### Data Models

#### ConversationRecord
```python
{
    "id": "conv_20240115_001",
    "title": "Python异步编程最佳实践",
    "content": "AI生成的对话摘要...",  # 注意：不保存完整对话内容
    "summary": "AI生成摘要",
    "tags": ["Python", "async", "programming"],
    "category": "problem-solving",
    "importance": 4,
    "created_at": "2024-01-15T10:30:00Z",
    "solutions": [...]  # 包含的解决方案
}
```

#### Solution
```python
{
    "id": "sol_b5b6377d",
    "type": "code",
    "content": "class ThreadSafeSingleton: ...",
    "language": "python", 
    "description": "线程安全单例模式实现",
    "reusability_score": 0.9,
    "tags": ["singleton", "thread-safe", "design-pattern"]
}
```

## 🔧 Usage Examples

### 实际使用流程

```python
# 1. 保存对话摘要（不是完整对话）
result = await save_conversation(
    title="Python异步编程问题解决",
    ai_summary="讨论了asyncio错误处理最佳实践",
    ai_tags=["Python", "asyncio", "error-handling"],
    ai_importance=4
)

# 2. 从对话中提取解决方案（必须先执行）
solutions = await extract_solutions(
    extract_type="code",
    min_reusability_score=0.5
)

# 3. 在解决方案库中搜索（grep文本匹配）
search_results = await search_knowledge(
    query="Python async exception handling",
    search_in="all"
)

# 4. 格式化搜索结果为AI可理解的数据
context = await inject_context(
    current_query="如何在async/await中处理多个异常？",
    search_results=search_results['results']
)
```

### Data Management

```python
# Export all data
export_result = await export_data(
    export_path="/path/to/export",
    include_backups=True
)

# Import data from export
import_result = await import_data(
    import_path="/path/to/import", 
    merge_mode="append",
    create_backup=True
)

# Get storage information
storage_info = await get_storage_info()
print(f"Total conversations: {storage_info['total_conversations']}")
print(f"Total solutions: {storage_info['total_solutions']}")
```

## ⚡ Performance

- **搜索响应**: < 100ms 的grep文本搜索速度
- **结果格式化**: < 100ms 的简单数据处理  
- **存储效率**: 每个对话摘要记录 < 50KB
- **搜索精度**: 依赖AI进行语义理解和关键词生成，工具只负责简单匹配

## 🔒 Security & Privacy

- **本地存储**: 所有数据本地存储，无外部服务依赖
- **无云依赖**: 完全离线可用
- **隐私优先**: 对话摘要不会离开你的系统（注意：不存储完整对话内容）
- **访问控制**: 文件系统权限控制访问

## 配置 MCP 客户端

### 通用 mcp.json 配置

创建 `mcp.json` 配置文件：

```json
{
  "mcpServers": {
    "synapse": {
      "command": "uv",
      "args": ["--directory", "/path/to/synapse-mcp", "run", "python3", "src/synapse/server.py"]
    }
  }
}
```

### Claude Code 安装

使用 Claude Code CLI 添加 Synapse MCP：

对于Mac/Linux系统：

```bash
claude mcp add synapse-mcp --scope user -- uv --directory /path/to/synapse-mcp run mcp run src/synapse/server.py
```

对于Windows系统：
```bash
claude mcp add synapse-mcp --scope user -- uv --directory E:\\codecourse\\synapse-mcp run mcp run src\\synapse\\server.py
```

替换路径为你的实际项目路径。

**注意**: 
- `--scope user` 表示用户级别安装
- 确保项目路径使用绝对路径
- 安装后可通过 `claude mcp list` 查看已安装的 MCP 服务

## 🧪 Testing

```bash
# Run test suite
uv run python3 -m pytest tests/

# Run with coverage
uv run python3 -m pytest tests/ --cov=src/synapse

# Type checking
uv run mypy src/

# Linting  
uv run flake8 src/ tests/
```

## 🛠 Development

### MCP Python SDK Patterns Used

- **FastMCP Server**: Modern MCP server framework with lifespan management
- **Context Usage**: Progress reporting, logging, and resource access
- **Tool Registration**: Type-safe tool definitions with validation
- **Error Handling**: Comprehensive error handling and user feedback

### Key Implementation Details

- **Absolute Imports**: All imports use absolute paths for MCP compatibility
- **Storage Architecture**: JSON-based local storage with lightweight indexing  
- **Search Algorithm**: Simple grep-based search, letting AI handle semantics
- **Memory Efficient**: Streaming JSON processing for large datasets

## 📝 Contributing

1. Follow existing code style and patterns
2. Use absolute imports only (required for MCP compatibility)
3. Add comprehensive tests for new features
4. Update documentation when adding tools or changing APIs
5. Test with `uv run mcp dev` before submitting

## 📄 License

MIT License - see LICENSE file for details

## 🔗 Links

- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
- [FastMCP Framework](https://github.com/modelcontextprotocol/python-sdk)
- [Issue Tracker](https://github.com/your-repo/synapse-mcp/issues)
