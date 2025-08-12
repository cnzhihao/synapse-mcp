# Synapse MCP 开发任务清单

## 项目概述
Synapse 是一个基于 Model Context Protocol (MCP) 的智能记忆和知识检索工具，专为增强 AI 编程助手的上下文理解能力而设计。

## 开发阶段划分

### Phase 1: 基础架构搭建 (第1-2周)

#### 任务1: 设置标准MCP项目目录结构和配置文件
**优先级**: 🔴 高
**状态**: ✅ 已完成
**预估时间**: 2-3小时

**详细任务**:
- [x] 创建标准的MCP服务器项目目录结构
  ```
  src/
  ├── synapse/
  │   ├── __init__.py
  │   ├── server.py          # MCP服务器主文件
  │   ├── models/            # 数据模型
  │   ├── tools/             # MCP工具实现
  │   ├── storage/           # 存储系统
  │   │   ├── paths.py       # 存储路径管理
  │   │   └── initializer.py # 存储初始化
  │   └── utils/             # 工具函数
  tests/                     # 测试文件
  ```
- [x] 更新 pyproject.toml 配置依赖包
  - 添加 mcp[cli]>=1.12.4 (MCP Python SDK - 最新稳定版本)
  - 添加 platformdirs>=4.3.0 (跨平台目录 - 最新稳定版)
  - 添加 pydantic>=2.11.0 (数据验证 - 性能优化版本)
  - 添加 python-dateutil>=2.9.0 (日期处理 - 最新版本)
- [x] 创建开发环境配置文件
- [x] 设置日志配置文件

**注意**: 用户数据将存储在系统标准目录，而不是项目源码目录

**验收标准**:
- 项目目录结构符合MCP标准
- 所有必要的配置文件已创建
- 可以正常导入项目模块

---

#### 任务2: 实现ConversationRecord和Solution核心数据模型
**优先级**: 🔴 高
**状态**: ✅ 已完成
**预估时间**: 3-4小时

**详细任务**:
- [x] 创建 `src/synapse/models/__init__.py`
- [x] 实现 `ConversationRecord` 数据类
  - id: str (唯一标识符)
  - title: str (对话主题)
  - content: str (完整对话内容)
  - summary: str (AI生成的摘要)
  - tags: List[str] (标签列表)
  - category: str (分类)
  - importance: int (1-5重要程度)
  - created_at: datetime
  - updated_at: datetime
  - solutions: List[Solution]
- [x] 实现 `Solution` 数据类
  - id: str
  - type: str ("code" | "approach" | "pattern")
  - content: str
  - language: Optional[str]
  - description: str
  - reusability_score: float (0.0-1.0)
- [x] 添加数据验证和序列化方法
- [x] 创建JSON转换工具函数

**验收标准**:
- 数据模型定义完整且类型安全
- 支持JSON序列化和反序列化
- 包含数据验证逻辑
- 有基本的单元测试

---

#### 任务3: 配置MCP服务器基础架构和工具注册
**优先级**: 🔴 高  
**状态**: ✅ 已完成
**预估时间**: 4-5小时

**详细任务**:
- [x] 创建 `src/synapse/server.py` 主服务器文件
- [x] 初始化MCP服务器实例
- [x] 设置工具注册装饰器模式
- [x] 实现标准化的错误处理
- [x] 添加输入参数验证机制
- [x] 创建统一的响应格式
- [x] 实现服务器启动和关闭逻辑

**实现要点**:
- 使用 FastMCP 框架创建 MCP 服务器实例
- 实现了 5 个核心 MCP 工具：save-conversation、search-knowledge、extract-solutions、inject-context、get-storage-info
- 集成应用生命周期管理，包含数据库连接和存储系统初始化
- 每个工具都有完整的参数验证、错误处理和 Context 支持
- 支持 stdio 传输协议，与 Claude 等 AI 助手兼容

**验收标准**:
- [x] MCP服务器可以正常启动
- [x] 支持工具注册和路由
- [x] 有完整的错误处理机制
- [x] 输入验证工作正常

---

#### 任务4: 实现跨平台存储路径管理系统
**优先级**: 🔴 高
**状态**: ✅ 已完成
**预估时间**: 2-3小时

**详细任务**:
- [x] 创建 `src/synapse/storage/paths.py`
- [x] 实现 `StoragePaths` 类，使用 platformdirs 库
  - get_data_dir(): 获取用户数据目录
  - get_config_dir(): 获取配置目录
  - get_cache_dir(): 获取缓存目录
  - get_conversations_dir(): 对话存储目录
  - get_solutions_dir(): 解决方案目录
  - get_indexes_dir(): 索引目录
- [x] 创建 `src/synapse/storage/initializer.py`
- [x] 实现首次运行初始化逻辑
  - 自动创建目录结构
  - 生成默认配置文件
  - 显示存储位置信息
- [x] 添加存储位置查询工具

**存储位置规范**:
- **macOS/Linux**: `~/.local/share/synapse-mcp/`
- **Windows**: `%APPDATA%\synapse\synapse-mcp\`
- **配置**: `~/.config/synapse-mcp/` (Unix) 或同数据目录 (Windows)

**验收标准**:
- [x] 支持所有主流操作系统
- [x] 自动创建必要的目录结构
- [x] 首次运行时显示存储位置
- [x] 配置文件正确生成

**实现要点**:
- 使用 platformdirs 库实现跨平台路径管理，遵循各操作系统的标准目录规范
- 创建了完整的 StoragePaths 类，提供8个核心目录的路径管理方法
- 实现了 StorageInitializer 类，包含完整的首次运行初始化逻辑
- 自动创建目录结构、生成默认配置文件（config.json、logging.json）和索引文件
- 集成到 MCP 服务器的 get-storage-info 工具中，提供完整的存储状态查询功能
- 包含权限验证、存储大小统计和健康检查功能

---

#### 任务5: 创建JSON文件存储和目录管理系统
**优先级**: 🔴 高
**状态**: ⏳ 待办
**预估时间**: 3-4小时

**详细任务**:
- [x] 创建 `src/synapse/storage/` 目录
- [x] 实现 `FileManager` 类处理文件操作
- [x] 创建对话存储的日期目录结构 (YYYY/MM/)
- [x] 实现JSON文件的读写操作
- [x] 添加文件锁机制避免并发冲突
- [x] 实现备份和恢复功能
- [x] 创建存储空间使用监控

**验收标准**:
- 可以安全地读写JSON文件
- 支持按日期组织的目录结构
- 有并发访问保护
- 存储操作有错误恢复机制

---

### Phase 2: 核心MCP工具实现 (第3-5周)

#### 任务6: 实现save-conversation MCP工具
**优先级**: 🟡 中等
**状态**: ⏳ 待办
**预估时间**: 6-8小时

**详细任务**:
- [ ] 创建 `src/synapse/tools/save_conversation.py`
- [ ] 实现对话内容解析和清理
- [ ] 添加自动标签提取算法
- [ ] 实现AI摘要生成功能
- [ ] 创建对话重要性评估逻辑
- [ ] 实现文件存储和索引更新
- [ ] 添加重复对话检测机制

**输入参数**:
- title: str (对话主题)
- content: str (对话内容)  
- tags: Optional[List[str]] (标签)
- category: Optional[str] (分类)
- importance: int = 3 (重要程度)

**输出格式**:
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

**验收标准**:
- 可以成功保存对话记录
- 自动标签提取准确率>70%
- 生成的摘要质量良好
- 索引更新正常工作

---

#### 任务7: 实现extract-solutions MCP工具
**优先级**: 🟡 中等
**状态**: ⏳ 待办
**预估时间**: 8-10小时

**详细任务**:
- [ ] 创建 `src/synapse/tools/extract_solutions.py`
- [ ] 实现代码块识别算法
- [ ] 开发解决方案分类逻辑
- [ ] 创建可重用性评分算法
- [ ] 实现编程语言自动检测
- [ ] 添加解决方案去重机制
- [ ] 创建解决方案质量评估

**输入参数**:
- conversation_id: str (对话ID)
- extract_type: str = "all" ("code" | "solution" | "pattern" | "all")
- auto_tag: bool = True (自动标签识别)

**输出格式**:
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

**验收标准**:
- 能准确识别和提取代码块
- 解决方案分类准确
- 可重用性评分合理
- 支持多种编程语言检测

---

#### 任务8: 实现search-knowledge MCP工具和搜索引擎
**优先级**: 🟡 中等
**状态**: ⏳ 待办
**预估时间**: 10-12小时

**详细任务**:
- [ ] 创建 `src/synapse/tools/search_knowledge.py`
- [ ] 实现三层搜索策略：
  - 精确匹配 (标题和关键词)
  - 标签过滤 (技术标签分类)
  - 模糊匹配 (内容片段)
- [ ] 开发多因子评分算法
- [ ] 实现搜索结果排序系统
- [ ] 创建搜索性能优化
- [ ] 添加搜索结果缓存机制

**评分算法**:
```
relevance_score = (
  exact_match * 0.5 +
  tag_match * 0.3 + 
  content_match * 0.2
) * importance_factor * recency_factor
```

**输入参数**:
- query: str (搜索查询)
- category: Optional[str] (内容分类过滤)
- tags: Optional[List[str]] (标签过滤)
- time_range: str = "all" ("week" | "month" | "all")
- limit: int = 10 (返回结果数量)

**输出格式**:
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

**验收标准**:
- 搜索响应时间 < 200ms
- 搜索结果相关性 > 80%
- 支持多种搜索策略组合
- 结果排序算法合理

---

#### 任务9: 实现inject-context MCP工具
**优先级**: 🟡 中等
**状态**: ⏳ 待办
**预估时间**: 4-6小时

**详细任务**:
- [ ] 创建 `src/synapse/tools/inject_context.py`
- [ ] 实现智能相关性计算算法
- [ ] 开发上下文选择和过滤逻辑
- [ ] 创建上下文内容格式化
- [ ] 添加上下文质量评估
- [ ] 实现上下文注入摘要生成

**输入参数**:
- current_query: str (当前用户问题)
- max_items: int = 3 (最大注入项数)
- relevance_threshold: float = 0.7 (相关性阈值)

**输出格式**:
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

**验收标准**:
- 相关性计算准确
- 注入的上下文质量高
- 摘要信息有用
- 性能满足要求

---

#### 任务10: 实现存储管理和数据导入导出工具
**优先级**: 🟡 中等
**状态**: ⏳ 待办
**预估时间**: 4-5小时

**详细任务**:
- [ ] 创建 `get-storage-info` MCP工具
  - 显示存储位置信息
  - 统计对话数量和存储大小
  - 显示配置信息
- [ ] 创建 `export-data` MCP工具
  - 导出用户数据到指定路径
  - 支持JSON格式导出
  - 包含完整的索引信息
- [ ] 创建 `import-data` MCP工具
  - 从指定路径导入数据
  - 验证数据格式和完整性
  - 更新索引和配置
- [ ] 添加数据备份和恢复功能

**输入输出格式**:

**get-storage-info**:
```json
{
  "data_directory": "/Users/user/.local/share/synapse-mcp",
  "config_directory": "/Users/user/.config/synapse-mcp",
  "total_conversations": 156,
  "storage_size_mb": 12.5,
  "last_backup": "2024-01-15T10:30:00Z"
}
```

**export-data**:
- 输入: `export_path: str`, `include_cache: bool = False`
- 输出: 导出状态和文件路径

**import-data**:
- 输入: `import_path: str`, `merge_mode: str = "append"`
- 输出: 导入统计和状态

**验收标准**:
- 存储信息显示准确
- 数据导入导出功能完整
- 支持数据迁移和备份
- 错误处理完善

---

### Phase 3: 索引和优化 (第6-7周)

#### 任务11: 编写测试套件和使用文档
**优先级**: 🟢 低
**状态**: ⏳ 待办
**预估时间**: 8-10小时

**详细任务**:
- [ ] 创建单元测试套件
- [ ] 编写集成测试
- [ ] 添加MCP协议兼容性测试
- [ ] 创建性能基准测试
- [ ] 编写API使用文档
- [ ] 创建部署指南
- [ ] 添加故障排除文档

---

#### 任务12: 性能优化和基准测试  
**优先级**: 🟢 低
**状态**: ⏳ 待办
**预估时间**: 6-8小时

**详细任务**:
- [ ] 实现内存缓存机制
- [ ] 优化搜索算法性能
- [ ] 添加并发处理支持
- [ ] 进行性能基准测试
- [ ] 优化存储空间使用
- [ ] 创建监控和指标收集

---

## 技术目标

### 性能指标
- 🎯 搜索响应时间 < 200ms
- 🎯 搜索结果准确率 > 80%
- 🎯 单个对话记录存储 < 50KB
- 🎯 支持10,000+对话记录

### 质量标准
- 📋 单元测试覆盖率 > 80%
- 📋 所有MCP工具通过兼容性测试
- 📋 错误处理覆盖所有异常情况
- 📋 完整的API文档和使用示例

## 开发约定

### 代码规范
- 使用 Python 类型注解
- 遵循 PEP 8 代码风格
- 所有公共函数必须有文档字符串
- 错误信息要清晰易懂

### 提交规范
- 每个任务完成后单独提交
- 提交信息格式: `feat: 实现xxx功能` 或 `fix: 修复xxx问题`
- 重要功能点要有详细的提交说明

### 测试要求
- 新功能必须有对应测试
- 修复bug时要添加回归测试
- 性能敏感的代码需要基准测试

## 里程碑检查点

- [ ] **Week 2**: Phase 1 完成，基础架构和存储系统搭建完毕 (任务1-5)
- [ ] **Week 5**: Phase 2 完成，所有MCP工具实现完毕 (任务6-10)
- [ ] **Week 7**: Phase 3 完成，测试和优化完成 (任务11-12)
- [ ] **Week 8**: 项目完成，准备部署和发布

---

*最后更新时间: 2024-01-15*
*文档版本: 1.0*