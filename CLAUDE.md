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
# Install MCP Python SDK (FastMCP)
pip install mcp

# Install additional dependencies for text processing
pip install python-dateutil jieba scikit-learn

# Run the MCP server in development mode
python src/synapse/server.py

# Run with uv (recommended)
uv run python src/synapse/server.py

# Test MCP server with different transports
uv run python src/synapse/server.py  # stdio (default)
uv run python src/synapse/server.py --transport sse --port 8000  # SSE
uv run python src/synapse/server.py --transport streamable-http --port 8001  # Streamable HTTP
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

# Run in development with hot reload
uv run mcp dev src/synapse/server.py

# Add dependencies on the fly
uv run mcp dev src/synapse/server.py --with pandas --with numpy

# Mount local code in editable mode
uv run mcp dev src/synapse/server.py --with-editable .
```

### Official MCP Python SDK Patterns

#### 1. FastMCP Server Creation
```python
from mcp.server.fastmcp import FastMCP

# Basic server
mcp = FastMCP("my-server-name")

# Server with lifespan management
mcp = FastMCP("my-server-name", lifespan=app_lifespan)

# Stateless HTTP server
mcp = FastMCP("my-server-name", stateless_http=True)

# Stateless with JSON responses (no SSE stream)
mcp = FastMCP("my-server-name", stateless_http=True, json_response=True)
```

#### 2. Tool Registration Patterns
```python
# Basic tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    return a + b

# Tool with optional parameters
@mcp.tool()
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get weather for a city"""
    return f"Weather in {city}: 22 degrees {unit[0].upper()}"

# Async tool with context
@mcp.tool()
async def long_task(name: str, ctx: Context) -> str:
    """Execute a long-running task with progress"""
    await ctx.info(f"Starting task: {name}")
    await ctx.report_progress(0.5, message="Halfway done")
    return f"Completed: {name}"
```

#### 3. Server Execution Patterns
```python
# Direct execution (simplest)
if __name__ == "__main__":
    mcp.run()

# With transport specification
if __name__ == "__main__":
    mcp.run(transport="stdio")  # Default
    # mcp.run(transport="sse")
    # mcp.run(transport="streamable-http")

# Async main function
async def main():
    mcp.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## Key MCP Implementation Patterns

### FastMCP Server Pattern (Official SDK)
```python
from mcp.server.fastmcp import FastMCP, Context

# Create FastMCP server with lifespan management
mcp = FastMCP("synapse-mcp", lifespan=app_lifespan)

@mcp.tool()
async def save_conversation(
    title: str,
    content: str,
    tags: list[str] = None,
    category: str = "general",
    importance: int = 3,
    ctx: Context = None
) -> dict:
    """Save AI conversation record to knowledge base"""
    if ctx:
        await ctx.info(f"Saving conversation: {title}")
    # Implementation details...
    return {"id": "conv_001", "status": "saved"}
```

### Server Lifespan Management
```python
from contextlib import asynccontextmanager
from dataclasses import dataclass

@dataclass
class AppContext:
    """Application context with typed dependencies"""
    db: Database
    storage_paths: StoragePaths

@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Manage application lifecycle with type-safe context"""
    # Initialize on startup
    db = await Database.connect()
    storage_paths = StoragePaths()
    try:
        yield AppContext(db=db, storage_paths=storage_paths)
    finally:
        # Cleanup on shutdown
        await db.disconnect()
```

### Context Usage in Tools
```python
@mcp.tool()
async def search_knowledge(
    query: str,
    limit: int = 10,
    ctx: Context = None
) -> dict:
    """Search knowledge base with progress reporting"""
    if ctx:
        await ctx.info(f"Starting search: '{query}'")
        
        # Access lifespan resources
        if hasattr(ctx.request_context, 'lifespan_context'):
            db = ctx.request_context.lifespan_context.db
            results = await db.search_conversations(query, limit)
        
        await ctx.info(f"Found {len(results)} results")
    
    return {"results": results, "query": query}
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

### Tool Response Formatting (FastMCP)
FastMCP automatically handles response formatting. Simply return Python objects:
```python
@mcp.tool()
async def get_weather(city: str) -> dict:
    """Get weather for a city"""
    # FastMCP automatically converts dict to proper MCP response
    return {
        "city": city,
        "temperature": "22°C",
        "condition": "sunny"
    }
```

### Error Handling Pattern (FastMCP)
```python
@mcp.tool()
async def risky_operation(data: str, ctx: Context = None) -> dict:
    """Operation that might fail"""
    try:
        result = await process_data(data)
        return {"result": result}
    except ValueError as e:
        if ctx:
            await ctx.error(f"Validation failed: {str(e)}")
        # FastMCP automatically converts exceptions to MCP error responses
        raise ValueError(f"Invalid input: {e}")
    except Exception as e:
        if ctx:
            await ctx.error(f"Operation failed: {str(e)}")
        raise RuntimeError(f"Processing error: {e}")
```

### Progress Reporting with Context
```python
@mcp.tool()
async def long_running_task(
    task_name: str,
    steps: int = 5,
    ctx: Context = None
) -> str:
    """Execute a task with progress updates"""
    if ctx:
        await ctx.info(f"Starting: {task_name}")

    for i in range(steps):
        progress = (i + 1) / steps
        if ctx:
            await ctx.report_progress(
                progress=progress,
                total=1.0,
                message=f"Step {i + 1}/{steps}",
            )
            await ctx.debug(f"Completed step {i + 1}")

    return f"Task '{task_name}' completed"
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

## MCP Python SDK Best Practices

### 1. Tool Design Principles
```python
# Good: Clear, specific tool with type hints
@mcp.tool()
async def save_conversation(
    title: str,
    content: str,
    tags: list[str] = None,
    importance: int = 3
) -> dict:
    """Save AI conversation with metadata
    
    Args:
        title: Conversation topic (required)
        content: Full conversation text (required)
        tags: Optional list of classification tags
        importance: Priority level 1-5 (default: 3)
    
    Returns:
        dict: Save result with ID and metadata
    """
    # Validate inputs
    if not title.strip():
        raise ValueError("Title cannot be empty")
    
    # Process and return structured result
    return {
        "id": generate_id(),
        "title": title,
        "saved_at": datetime.now().isoformat(),
        "searchable": True
    }
```

### 2. Context Usage Best Practices
```python
# Use Context for logging, progress, and resource access
@mcp.tool()
async def complex_operation(
    data: str,
    ctx: Context = None  # Always optional with default None
) -> dict:
    """Perform complex operation with full context support"""
    
    # Log operation start
    if ctx:
        await ctx.info(f"Starting complex operation")
    
    try:
        # Access lifespan resources
        if ctx and hasattr(ctx.request_context, 'lifespan_context'):
            db = ctx.request_context.lifespan_context.db
            result = await db.process(data)
        else:
            # Fallback for testing or standalone use
            result = mock_process(data)
        
        # Report progress for long operations
        if ctx:
            await ctx.report_progress(0.5, message="Processing...")
        
        # Log success
        if ctx:
            await ctx.info("Operation completed successfully")
        
        return {"result": result, "status": "success"}
        
    except Exception as e:
        # Log errors
        if ctx:
            await ctx.error(f"Operation failed: {str(e)}")
        # Re-raise for FastMCP to handle
        raise
```

### 3. Resource and Prompt Integration
```python
# Resources provide dynamic content
@mcp.resource("conversation://{conversation_id}")
def get_conversation(conversation_id: str) -> str:
    """Get conversation content by ID"""
    return f"Conversation {conversation_id} content..."

# Prompts provide reusable templates
@mcp.prompt("analyze-conversation")
def analyze_conversation_prompt(
    conversation_id: str,
    focus: str = "summary"
) -> list:
    """Generate analysis prompt for conversation"""
    return [
        {
            "role": "user",
            "content": f"Analyze conversation {conversation_id} focusing on {focus}"
        }
    ]
```

### 4. Transport Configuration
```python
# Stdio for Claude Desktop integration
if __name__ == "__main__":
    mcp.run()  # Default: stdio

# SSE for web applications
if __name__ == "__main__":
    mcp.run(transport="sse", port=8000)

# Streamable HTTP for advanced web integration
if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8001)
```

### 5. Testing MCP Tools
```python
import pytest
from mcp.server.fastmcp import Context

@pytest.mark.asyncio
async def test_save_conversation():
    """Test conversation saving functionality"""
    
    # Test with valid data
    result = await save_conversation(
        title="Test Conversation",
        content="Test content",
        tags=["test"],
        importance=3
    )
    
    assert result["title"] == "Test Conversation"
    assert result["searchable"] is True
    assert "id" in result

@pytest.mark.asyncio
async def test_save_conversation_with_context():
    """Test conversation saving with context"""
    
    # Mock context for testing
    class MockContext:
        async def info(self, message): pass
        async def error(self, message): pass
    
    ctx = MockContext()
    result = await save_conversation(
        title="Test",
        content="Content",
        ctx=ctx
    )
    
    assert result is not None
```

### 6. Error Handling Strategy
```python
# Custom exceptions for better error reporting
class ConversationError(Exception):
    """Base exception for conversation operations"""
    pass

class ConversationNotFoundError(ConversationError):
    """Conversation not found"""
    pass

@mcp.tool()
async def get_conversation(conversation_id: str, ctx: Context = None) -> dict:
    """Retrieve conversation by ID with proper error handling"""
    
    try:
        if not conversation_id:
            raise ValueError("Conversation ID is required")
        
        # Attempt to find conversation
        conversation = await find_conversation(conversation_id)
        if not conversation:
            raise ConversationNotFoundError(f"Conversation {conversation_id} not found")
        
        return conversation.to_dict()
        
    except ConversationNotFoundError as e:
        if ctx:
            await ctx.error(str(e))
        raise  # FastMCP will convert to proper MCP error
    except ValueError as e:
        if ctx:
            await ctx.error(f"Invalid input: {str(e)}")
        raise
    except Exception as e:
        if ctx:
            await ctx.error(f"Unexpected error: {str(e)}")
        raise RuntimeError(f"Failed to retrieve conversation: {str(e)}")
```

When implementing any component, always explain in detail what the code does, why it's structured that way, and how it fits into the overall MCP architecture.