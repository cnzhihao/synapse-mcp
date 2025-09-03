# Synapse MCP

An intelligent memory and knowledge retrieval server built with Python MCP (Model Context Protocol) that helps AI programming assistants remember and reuse solutions from previous conversations.

## 🚀 Features

### Core MCP Tools

**🤖 save-conversation** - 智能对话存储
- 自动保存当前对话到知识库，支持AI自动分析和标签提取
- 支持重复对话检测和标签管理  
- 自动生成摘要和重要性评级

**🔍 search-knowledge** - AI语义搜索  
- 使用简单grep搜索策略，让AI负责语义理解和关键词生成
- 建议连续搜索2-3次不同关键词以提高召回率
- 支持多字段搜索（title/content/tags/all）

**🧠 inject-context** - 智能上下文注入
- 基于搜索结果进行上下文注入，引导AI应用到问题解决中  
- 简化处理逻辑，保留关键信息，让AI负责语义理解

**💎 extract-solutions** - 解决方案提取
- 智能识别并提取有价值的代码片段、方法和设计模式
- 自动质量评估和去重，建立可重用解决方案库

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
    "content": "完整对话内容...",
    "summary": "AI生成摘要",
    "tags": ["Python", "async", "programming"],
    "category": "problem-solving",
    "importance": 4,
    "created_at": "2024-01-15T10:30:00Z",
    "solutions": [...]
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

### Basic Usage Flow

```python
# 1. Save current conversation
result = await save_conversation(
    title="Python异步编程问题解决",
    ai_summary="讨论了asyncio错误处理最佳实践",
    ai_tags=["Python", "asyncio", "error-handling"],
    ai_importance=4
)

# 2. Search for related solutions  
search_results = await search_knowledge(
    query="Python async exception handling",
    search_in="all"
)

# 3. Extract solutions from conversations
solutions = await extract_solutions(
    extract_type="code",
    min_reusability_score=0.5
)

# 4. Inject relevant context for current problem
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

- **Search Response**: < 100ms for grep-based searches
- **Context Injection**: < 100ms for simplified processing  
- **Storage Efficiency**: < 50KB per conversation record
- **Search Accuracy**: Relies on AI for semantic understanding and keyword generation

## 🔒 Security & Privacy

- **Local Storage**: All data stored locally, no external services
- **No Cloud Dependencies**: Fully offline capable
- **Privacy First**: Conversations never leave your system
- **Access Control**: File system permissions control access

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
claude mcp add synapse-mcp --scope user -- uv --directory /path/to/synapse-mcp run python3 src/synapse/server.py
```

对于Windows系统：
```bash
claude mcp add synapse-mcp --scope user -- uv --directory E:\\codecourse\\synapse-mcp run python3 src\\synapse\\server.py
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
