# Synapse MCP 工具 PRD

## 项目概述

Synapse 是一个基于 Model Context Protocol (MCP) 的智能记忆和知识检索工具，专为增强 AI 编程助手的上下文理解能力而设计。该工具将用户的对话历史、解决方案、最佳实践等信息转化为可复用的知识库，并提供智能检索能力。

### 核心价值主张
- **记忆沉淀** - 将与AI的宝贵对话转化为可复用的解决方案
- **知识复用** - 快速找到之前解决过的类似问题
- **学习强化** - 从历史交互中提取最佳实践和模式
- **上下文增强** - 为AI提供更丰富的历史背景信息

## 目标用户

**主要用户**：频繁使用 AI 编程助手的开发者
- 需要在项目间复用解决方案的工程师
- 希望建立个人知识库的学习者
- 团队中需要知识共享的技术领导者

**使用场景**：
- 遇到相似问题时快速找到之前的解决方案
- 整理和管理AI对话中的有价值内容
- 团队知识共享和最佳实践传承
- 项目经验总结和复用

## 核心功能

### 1. 对话记忆管理 (Conversation Memory)

**功能描述**：自动捕获、分析和存储与AI的对话内容

**MCP 工具**：`save-conversation`

**输入参数**：
- `title` (string): 对话主题
- `content` (string): 对话内容
- `tags` (array): 相关标签，如 ["react", "performance", "hooks"]
- `category` (string): 分类，如 "problem-solving", "learning", "code-review"
- `importance` (number): 重要程度评分 (1-5)

**输出格式**：
```json
{
  "id": "conv_20240115_001",
  "title": "React性能优化方案",
  "summary": "使用React.memo和useCallback优化重渲染",
  "stored_at": "2024-01-15T10:30:00Z",
  "tags": ["react", "performance", "optimization"],
  "searchable": true
}
```

### 2. 解决方案提取 (Solution Extraction)

**功能描述**：从对话中智能提取可复用的解决方案和代码片段

**MCP 工具**：`extract-solutions`

**输入参数**：
- `conversation_id` (string): 对话ID
- `extract_type` (string): 提取类型 "code" | "solution" | "pattern" | "all"
- `auto_tag` (boolean): 自动标签识别

**输出格式**：
```json
{
  "solutions": [
    {
      "id": "sol_001",
      "type": "code",
      "title": "防抖Hook实现",
      "content": "const useDebounce = (value, delay) => { ... }",
      "language": "javascript",
      "context": "用于搜索输入优化",
      "reusability_score": 0.9
    }
  ]
}
```

### 3. 智能知识检索 (Knowledge Retrieval)

**功能描述**：基于Context7启发的简洁检索架构，快速找到相关历史内容

**MCP 工具**：`search-knowledge`

**检索策略**：
- **关键词匹配** - 基于用户查询的直接匹配
- **标签过滤** - 技术栈和问题类型标签
- **相关性评分** - 内容匹配度 × 0.4 + 时效性 × 0.3 + 重要度 × 0.3

**输入参数**：
- `query` (string): 搜索查询
- `category` (string, optional): 内容分类过滤
- `tags` (array, optional): 标签过滤
- `time_range` (string, optional): 时间范围 "week" | "month" | "all"
- `limit` (number): 返回结果数量，默认 10

**输出格式**：
```json
{
  "results": [
    {
      "id": "conv_20240115_001",
      "title": "React性能优化方案",
      "snippet": "使用React.memo避免不必要的重渲染...",
      "match_score": 0.95,
      "created_at": "2024-01-15T10:30:00Z",
      "tags": ["react", "performance"],
      "type": "conversation"
    }
  ],
  "total": 15,
  "search_time_ms": 120
}
```

### 4. 上下文注入 (Context Injection)

**功能描述**：将相关历史内容注入当前AI对话

**MCP 工具**：`inject-context`

**输入参数**：
- `current_query` (string): 当前用户问题
- `max_items` (number): 最大注入项数，默认 3
- `relevance_threshold` (number): 相关性阈值，默认 0.7

**输出格式**：
```json
{
  "context_items": [
    {
      "title": "类似问题的解决方案",
      "content": "...",
      "relevance": 0.85,
      "source_type": "conversation"
    }
  ],
  "injection_summary": "找到3个相关历史解决方案"
}
```

## 技术架构

### 系统架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    AI 编程助手客户端                          │
│              (Cursor, VS Code, Claude, etc.)               │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Synapse MCP Server                         │
├─────────────────────┬───────────┬───────────┬───────────────┤
│  save-conversation  │ extract-  │ search-   │ inject-       │
│                     │ solutions │ knowledge │ context       │
└─────────────────────┼───────────┼───────────┼───────────────┘
                      │           │           │
                      ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────┐
│                    本地存储层                                │
├─────────────────────┬───────────────────┬───────────────────┤
│    对话存储          │     解决方案库     │    搜索索引        │
│   (JSON Files)      │   (Structured)    │  (Keywords/Tags)  │
└─────────────────────┴───────────────────┴───────────────────┘
```

### 用户数据存储规范

为了确保用户数据的安全性、可移植性和多用户兼容性，Synapse 遵循操作系统标准的用户数据存储规范：

#### 存储位置

**macOS / Linux**：
```
~/.local/share/synapse-mcp/          # 主要数据目录
├── conversations/                   # 对话记录存储
│   └── YYYY/MM/                    # 按年月分层存储
│       └── conv_YYYYMMDD_NNN.json
├── solutions/                      # 解决方案库
│   └── extracted_solutions.json
└── indexes/                        # 搜索索引
    ├── keyword_index.json
    └── tag_index.json

~/.config/synapse-mcp/               # 配置目录
└── config.json                     # 用户配置文件

~/.cache/synapse-mcp/                # 缓存目录
└── search_cache/                   # 搜索结果缓存
```

**Windows**：
```
%APPDATA%\synapse\synapse-mcp\       # 数据目录
├── conversations\
├── solutions\
└── indexes\

%LOCALAPPDATA%\synapse\synapse-mcp\  # 缓存目录
```

#### 存储特性

- **跨平台兼容**: 使用 `platformdirs` 库自动识别各操作系统的标准目录
- **用户隔离**: 每个用户拥有独立的数据目录，避免冲突
- **权限安全**: 存储在用户目录，无需管理员权限
- **升级安全**: 包更新不影响用户数据
- **易于备份**: 用户可轻松定位和备份自己的数据

#### 初始化机制

首次运行时自动创建存储结构：
```json
{
  "max_conversations": 10000,
  "auto_backup": true,
  "search_cache_size": 1000,
  "log_level": "INFO",
  "storage_location": "auto"
}
```

### 核心组件实现

#### 1. MCP 服务器层
```typescript
const server = new McpServer({
  name: "synapse-mcp",
  version: "1.0.0"
});

// 对话保存工具
server.registerTool("save-conversation", {
  description: "保存AI对话到本地知识库",
  inputSchema: {
    title: z.string(),
    content: z.string(),
    tags: z.array(z.string()).optional(),
    category: z.string().optional(),
    importance: z.number().min(1).max(5).default(3)
  }
}, async (params) => {
  const conversation = await saveConversation(params);
  await updateSearchIndex(conversation);
  return { success: true, id: conversation.id };
});

// 知识搜索工具
server.registerTool("search-knowledge", {
  description: "搜索历史知识和解决方案",
  inputSchema: {
    query: z.string(),
    category: z.string().optional(),
    tags: z.array(z.string()).optional(),
    limit: z.number().default(10)
  }
}, async (params) => {
  return await searchKnowledgeBase(params);
});
```

#### 2. 简化检索引擎
- **存储方案**：本地JSON文件 + 轻量级索引
- **搜索策略**：关键词匹配 + 标签过滤，避免复杂的向量化
- **排序算法**：多因子评分（相关性、时效性、重要度）
- **性能优化**：内存缓存 + 增量索引更新

#### 3. 内容管理
```typescript
interface ConversationRecord {
  id: string;
  title: string;
  content: string;
  summary: string;           // AI生成的摘要
  tags: string[];           // 用户标签 + 自动提取
  category: string;         // 问题分类
  importance: number;       // 重要程度
  created_at: Date;
  updated_at: Date;
  solutions: Solution[];    // 提取的解决方案
}

interface Solution {
  id: string;
  type: "code" | "approach" | "pattern";
  content: string;
  language?: string;
  description: string;
  reusability_score: number;
}
```

## 改进的检索方案

### 为什么放弃Embedding方案

基于对Context7的研究，我们发现**简单有效胜过复杂精确**：

1. **性能优势**：关键词匹配比向量搜索快10倍以上
2. **维护简单**：无需复杂的模型和向量数据库
3. **结果可控**：用户更容易理解和优化搜索结果
4. **资源友好**：低内存占用，适合本地部署

### 新检索架构

**三层搜索策略**：
1. **精确匹配**：标题和关键词的直接匹配
2. **标签过滤**：基于技术标签的分类检索  
3. **模糊匹配**：内容片段的部分匹配

**评分算法**：
```
relevance_score = (
  exact_match * 0.5 +
  tag_match * 0.3 + 
  content_match * 0.2
) * importance_factor * recency_factor
```

## 技术依赖

### 核心依赖库

```toml
[project]
dependencies = [
    "mcp[cli]>=1.12.4",          # MCP Python SDK (最新稳定版本)
    "platformdirs>=4.3.0",      # 跨平台目录规范
    "pydantic>=2.11.0",         # 数据验证和序列化 (性能优化版本)
    "python-dateutil>=2.9.0",   # 日期时间处理
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",            # 测试框架
    "pytest-asyncio>=0.21.0",   # 异步测试支持
    "black>=23.0.0",            # 代码格式化
    "mypy>=1.0.0",              # 类型检查
    "ruff>=0.1.0",              # 快速代码检查
]
```

### 外部服务依赖

- **无外部服务依赖**: 完全本地化运行，无需API Key或云服务
- **无数据库依赖**: 使用JSON文件存储，降低部署复杂度
- **跨平台支持**: macOS、Linux、Windows全平台兼容

## 实现路线图

### Phase 1: 核心记忆功能 (3周)
- [x] MCP服务器基础架构
- [ ] 对话保存和管理
- [ ] 基础标签系统
- [ ] 简单关键词搜索

### Phase 2: 智能检索 (3周)  
- [ ] 多维度搜索算法
- [ ] 解决方案自动提取
- [ ] 上下文注入机制
- [ ] 搜索结果排序优化

### Phase 3: 增强功能 (4周)
- [ ] 团队知识共享
- [ ] 导入导出功能
- [ ] 搜索分析和优化
- [ ] 与主流IDE集成

## 预期效果

### 用户价值
- **效率提升**：相似问题解决时间减少70%
- **知识积累**：个人技术知识库逐步建立
- **学习强化**：从历史经验中持续学习

### 技术指标
- **响应速度**：搜索响应时间 < 200ms
- **准确率**：相关结果匹配度 > 80%
- **存储效率**：单个对话记录 < 50KB

通过这个改进方案，Synapse将成为一个轻量级但功能强大的AI编程助手增强工具，帮助开发者更好地管理和复用知识。