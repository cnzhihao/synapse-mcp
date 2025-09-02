# Inject Context 工具改进方案

## 背景

当前的 `inject_context` 工具存在以下问题：
1. 内部重复执行搜索逻辑，与 `search_knowledge` 功能重叠
2. 复杂的相关性评分算法，增加了系统复杂度
3. 结果排序和筛选逻辑复杂，可能遗漏重要信息
4. 最终输出仅为信息总结，未引导 AI 应用到具体问题解决中

## 改进目标

采用"简单粗暴"的策略：
1. **移除复杂逻辑**：删除内部搜索、评分、排序等复杂算法
2. **AI 智能处理**：让调用方 AI 负责语义理解和内容应用
3. **结果导向**：引导 AI 将搜索结果应用到当前问题解决中
4. **无信息遗漏**：处理所有搜索结果，避免因排序限制遗漏重要信息

## 参考实现

借鉴 `sequential-thinking` MCP 工具的设计理念：
- 返回结构化数据引导 AI 后续处理
- 通过 `action_needed` 和 `instruction` 字段明确指导 AI 行为
- 让 MCP 工具成为 AI 推理流程的一部分

## 具体改进方案

### 第一步：移除 search_knowledge 的结果限制

**文件**：`src/synapse/tools/search_knowledge.py`

**修改位置**：第 145 行

```python
# 当前代码：
results = results[:limit]

# 修改为：
# 完全移除限制，返回所有匹配结果
# results = results
```

**同时移除**：
- `limit` 参数相关的验证逻辑（第 128-129 行）
- 函数签名中的 `limit` 参数（第 79 行）

### 第二步：重写 inject_context 工具

**文件**：`src/synapse/tools/inject_context.py`

#### 2.1 修改函数签名

```python
def inject_context(
    self, 
    current_query: str,
    search_results: List[Dict],  # 新增：直接接收搜索结果
    # 删除 max_items 和 relevance_threshold 参数
    include_solutions: bool = True,      # 保留向后兼容性
    include_conversations: bool = True,  # 保留向后兼容性
    ctx: Context = None
) -> Dict[str, Any]:
```

#### 2.2 删除复杂逻辑

删除以下功能模块：
- `_search_candidates()` 方法（第 265-321 行）
- `_calculate_relevance_scores()` 方法（第 323-356 行）
- `_simple_relevance_score()` 方法（第 358-398 行）
- `_select_context_items()` 方法（第 406-459 行）
- 所有相关的评分、排序、筛选逻辑

#### 2.3 新的核心实现

```python
def inject_context(
    self, 
    current_query: str,
    search_results: List[Dict],
    include_solutions: bool = True,
    include_conversations: bool = True,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    为当前查询注入搜索结果上下文，并引导 AI 应用到问题解决中
    
    Args:
        current_query: 当前用户的查询或问题
        search_results: 来自 search_knowledge 工具的搜索结果
        include_solutions: 保留向后兼容性
        include_conversations: 保留向后兼容性
        ctx: MCP 上下文对象
        
    Returns:
        Dict: 引导 AI 进行问题解决应用的结构化数据
    """
    start_time = time.time()
    
    try:
        if ctx:
            await ctx.info(f"开始为查询注入上下文: '{current_query[:50]}'")
            await ctx.info(f"处理 {len(search_results)} 个搜索结果")
        
        # 参数验证
        if not current_query or not current_query.strip():
            raise ValueError("当前查询不能为空")
        
        if not isinstance(search_results, list):
            raise ValueError("search_results 必须是列表类型")
        
        # 格式化搜索结果供 AI 处理
        formatted_results = self._format_search_results_for_ai(search_results)
        
        processing_time = (time.time() - start_time) * 1000
        
        if ctx:
            await ctx.info(f"上下文注入完成，引导 AI 进行问题解决应用")
        
        # 返回引导 AI 进行问题解决应用的结构化数据
        return {
            "content": [{
                "type": "text", 
                "text": json.dumps({
                    "query": current_query,
                    "total_results": len(search_results),
                    "search_results": formatted_results,
                    "action_needed": "apply_context_to_problem",
                    "instruction": f"""请基于以上 {len(search_results)} 个搜索结果，为当前问题 '{current_query}' 提供具体的解决方案：

1. **分析相关性**：从搜索结果中识别与当前问题最相关的解决方案
2. **提取核心方法**：总结可以直接应用的代码片段、方法或模式
3. **具体应用指导**：说明如何将这些解决方案应用到当前问题中
4. **实施建议**：提供具体的实现步骤或代码示例

请直接给出可操作的解决方案，而不仅仅是总结。"""
                }, indent=2, ensure_ascii=False)
            }],
            "processing_time_ms": round(processing_time, 2),
            "total_items": len(search_results),
            "injection_summary": f"已为查询 '{current_query}' 准备 {len(search_results)} 个解决方案供 AI 分析应用"
        }
        
    except Exception as e:
        error_msg = str(e)
        if ctx:
            await ctx.error(f"上下文注入失败: {error_msg}")
        
        logger.error(f"上下文注入失败 - 查询: '{current_query}', 错误: {error_msg}", exc_info=True)
        
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": error_msg,
                    "query": current_query,
                    "action_needed": "handle_error"
                }, indent=2, ensure_ascii=False)
            }],
            "processing_time_ms": (time.time() - start_time) * 1000,
            "total_items": 0,
            "injection_summary": f"注入失败: {error_msg}"
        }

def _format_search_results_for_ai(self, search_results: List[Dict]) -> List[Dict]:
    """
    格式化搜索结果供 AI 处理
    
    简化搜索结果格式，保留 AI 需要的关键信息
    """
    formatted = []
    
    for result in search_results:
        formatted_result = {
            "id": result.get("id", "unknown"),
            "title": result.get("title", "未知标题"),
            "type": result.get("type", "unknown"),
            "language": result.get("language"),
            "content": result.get("snippet", ""),
            "reusability_score": result.get("reusability_score", 0.0),
            "match_reason": result.get("match_reason", ""),
        }
        
        # 移除空值
        formatted_result = {k: v for k, v in formatted_result.items() if v}
        formatted.append(formatted_result)
    
    return formatted
```

### 第三步：更新 MCP 服务器工具定义

**文件**：`src/synapse/server.py`

修改 `inject_context` 工具的参数定义：

```python
@mcp.tool()
async def inject_context(
    current_query: str,
    search_results: list,  # 新增必需参数
    include_solutions: bool = True,
    include_conversations: bool = True,
    ctx: Context = None
) -> dict:
    # 更新文档字符串
    """
    向当前对话注入搜索结果上下文，并引导 AI 应用到问题解决中
    
    Args:
        current_query: 当前用户的查询或问题（必需）
        search_results: 来自 search_knowledge 的搜索结果列表（必需）
        include_solutions: 保留向后兼容性（默认 True）
        include_conversations: 保留向后兼容性（默认 True）
        ctx: MCP 上下文对象
        
    Returns:
        dict: 引导 AI 进行问题解决应用的结构化数据
    """
```

## 新的使用流程

### 调用方式

```python
# 1. 搜索相关内容（无限制）
search_result = search_knowledge("Google AI API Python 实现")

# 2. 注入上下文并引导 AI 应用（直接传入搜索结果）
inject_result = inject_context(
    current_query="如何在 Python 中实现 Google AI API 调用",
    search_results=search_result["results"]
)

# 3. AI 自动看到 inject_result 中的指导，执行问题解决应用
```

### AI 行为预期

调用方 AI 看到 `inject_context` 返回的结果后，会：

1. **自动识别** `action_needed: "apply_context_to_problem"`
2. **阅读** `instruction` 中的四步指导
3. **分析** `search_results` 中的解决方案
4. **输出** 针对 `current_query` 的具体可操作解决方案

## 优势总结

1. **简单高效**：移除复杂算法，处理速度大幅提升
2. **无信息遗漏**：处理所有搜索结果，不受排序和限制影响
3. **AI 智能处理**：充分利用 AI 的语义理解和应用能力
4. **结果导向**：直接输出可操作的解决方案
5. **易于维护**：代码逻辑简单，便于调试和扩展

## 实施计划

1. **第一步**：修改 `search_knowledge.py`，移除结果限制
2. **第二步**：重写 `inject_context.py` 核心逻辑
3. **第三步**：更新 `server.py` 中的工具定义
4. **第四步**：测试新的工作流程
5. **第五步**：更新文档和使用说明

## 风险评估

**低风险**：
- 向后兼容性：保留了 `include_solutions` 和 `include_conversations` 参数
- 错误处理：完整的异常处理机制
- 渐进式改进：可以逐步部署和测试

**注意事项**：
- 大量搜索结果可能导致响应体积较大，需要监控性能
- 依赖调用方 AI 的理解能力，需要清晰的指导文档

---

*计划制定日期：2025-09-02*
*预计实施时间：1-2 天*