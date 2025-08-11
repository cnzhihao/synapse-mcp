# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Synapse is a Model Context Protocol (MCP) server built in Python that provides intelligent memory and knowledge retrieval for AI programming assistants. It captures, stores, and enables retrieval of conversation history, solutions, and best practices to enhance AI context understanding.

## Development Context for Beginner MCP Developers

When working on this project, always provide **extremely detailed explanations** for each component as you complete tasks. The developer is new to MCP development and needs comprehensive understanding of:

1. **What each piece of code does** - Explain the purpose and functionality in detail
2. **Why specific MCP patterns are used** - Clarify design decisions and MCP protocol requirements  
3. **How components interact** - Describe data flow and integration points
4. **Implementation significance** - Explain what each function/class contributes to the overall system

## Architecture Overview

### MCP Tools Structure
The project implements 4 core MCP tools:

1. **save-conversation** - Captures AI conversations with metadata (title, tags, importance)
2. **extract-solutions** - Intelligently extracts reusable code snippets and solutions
3. **search-knowledge** - Retrieves relevant historical content using keyword + tag matching
4. **inject-context** - Injects relevant historical context into current conversations

### Storage Architecture
- **Local JSON Files** - Primary storage for conversation records
- **Lightweight Search Index** - Keyword and tag-based indexing (no vector embeddings)
- **Three-Layer Search Strategy**:
  - Exact matching (titles/keywords)
  - Tag filtering (technology stack categories)
  - Fuzzy matching (content fragments)

### Data Models

#### ConversationRecord
Core data structure for storing conversation history:
```python
{
    "id": str,              # Unique identifier
    "title": str,           # Conversation topic
    "content": str,         # Full conversation content
    "summary": str,         # AI-generated summary
    "tags": list[str],      # User + auto-extracted tags
    "category": str,        # Classification (problem-solving, learning, etc.)
    "importance": int,      # 1-5 rating
    "created_at": datetime,
    "updated_at": datetime,
    "solutions": list[Solution]  # Extracted reusable solutions
}
```

#### Solution
Extracted reusable components:
```python
{
    "id": str,
    "type": str,            # "code" | "approach" | "pattern"
    "content": str,         # The actual solution content
    "language": str,        # Programming language (if code)
    "description": str,     # Context and usage
    "reusability_score": float  # 0.0-1.0 reusability rating
}
```

## Python MCP Development Commands

### Setup and Installation
```bash
# Install MCP Python SDK
pip install mcp

# Install additional dependencies for text processing
pip install python-dateutil jieba scikit-learn

# Run the MCP server in development mode
python src/server.py

# Test MCP server locally
mcp test --server python src/server.py
```

### Development Workflow
```bash
# Run tests
python -m pytest tests/

# Type checking (if using mypy)
mypy src/

# Format code
black src/ tests/

# Lint code
flake8 src/ tests/
```

## Key MCP Implementation Patterns

### Server Registration Pattern
```python
from mcp import McpServer
from mcp.types import Tool, TextContent

server = McpServer("synapse-mcp")

@server.tool()
async def save_conversation(
    title: str,
    content: str,
    tags: list[str] = None,
    category: str = None,
    importance: int = 3
) -> dict:
    # Implementation details...
    pass
```

### Search Algorithm Implementation
The search system uses a **three-tier relevance scoring**:
- **Exact Match Weight**: 0.5
- **Tag Match Weight**: 0.3  
- **Content Match Weight**: 0.2

Combined with temporal and importance factors for final ranking.

### File Storage Pattern
Conversations stored as individual JSON files in structured directories:
```
data/
├── conversations/
│   ├── 2024/
│   │   ├── 01/
│   │   │   ├── conv_20240115_001.json
│   │   │   └── conv_20240115_002.json
├── solutions/
│   └── extracted_solutions.json
└── indexes/
    ├── keyword_index.json
    └── tag_index.json
```

## MCP Protocol Integration Points

### Tool Response Formatting
All tools must return MCP-compatible responses:
```python
return {
    "content": [
        TextContent(
            type="text",
            text=result_text
        )
    ]
}
```

### Error Handling Pattern
```python
try:
    result = await process_request(params)
    return success_response(result)
except ValidationError as e:
    return error_response(f"Invalid input: {e}")
except StorageError as e:
    return error_response(f"Storage error: {e}")
```

## Performance Considerations

- **Target Response Time**: < 200ms for search operations
- **Storage Efficiency**: < 50KB per conversation record
- **Search Accuracy**: > 80% relevance matching
- **Memory Usage**: Implement caching for frequently accessed data

## Testing Strategy

### MCP Tool Testing
Each tool should have comprehensive tests covering:
- Parameter validation
- Success scenarios  
- Error handling
- Response format compliance

### Integration Testing
- Full MCP protocol communication
- Storage layer integration
- Search algorithm accuracy
- Performance benchmarks

When implementing any component, always explain in detail what the code does, why it's structured that way, and how it fits into the overall MCP architecture.