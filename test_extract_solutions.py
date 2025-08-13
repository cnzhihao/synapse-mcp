#!/usr/bin/env python3
"""
测试extract-solutions工具的基本功能

这个脚本测试extract-solutions MCP工具是否能正确地：
1. 初始化工具和存储系统
2. 创建测试对话记录（包含解决方案）
3. 使用extract-solutions工具提取解决方案
4. 验证提取结果和文件保存
"""

import asyncio
import sys
sys.path.append('src')

from synapse.models.conversation import ConversationRecord, Solution, create_solution
from synapse.storage.paths import StoragePaths
from synapse.storage.file_manager import FileManager
from synapse.tools.extract_solutions import ExtractSolutionsTool


async def test_extract_solutions():
    """测试extract-solutions工具的完整功能"""
    
    print("🚀 开始测试 extract-solutions 工具...")
    
    # 1. 初始化组件
    print("\n📦 初始化存储系统...")
    storage_paths = StoragePaths()
    file_manager = FileManager(storage_paths)
    extract_tool = ExtractSolutionsTool(storage_paths)
    
    print(f"  - 数据目录: {storage_paths.get_data_dir()}")
    print(f"  - 解决方案目录: {storage_paths.get_solutions_dir()}")
    
    # 2. 创建测试对话记录（包含解决方案）
    print("\n💡 创建测试对话记录...")
    
    # 创建测试解决方案
    test_solutions = [
        create_solution(
            solution_type="code",
            content="def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
            description="递归实现的斐波那契数列函数",
            language="python",
            reusability_score=0.8
        ),
        create_solution(
            solution_type="approach",
            content="使用动态规划优化递归算法，避免重复计算",
            description="动态规划优化方法",
            language=None,
            reusability_score=0.9
        ),
        create_solution(
            solution_type="pattern",
            content="Memoization Pattern: 缓存函数调用结果避免重复计算",
            description="记忆化模式实现",
            language=None,
            reusability_score=0.85
        )
    ]
    
    # 创建测试对话记录
    test_conversation = ConversationRecord(
        title="Python算法优化讨论",
        content="讨论了斐波那契数列的多种实现方式，包括递归、动态规划和记忆化优化。",
        summary="分析了递归算法的性能问题，提供了动态规划和记忆化的优化方案。",
        tags=["python", "algorithm", "optimization", "fibonacci"],
        category="问题解决",
        importance=4,
        solutions=test_solutions
    )
    
    print(f"  - 对话ID: {test_conversation.id}")
    print(f"  - 包含解决方案数: {len(test_conversation.solutions)}")
    
    # 3. 保存测试对话记录
    print("\n💾 保存测试对话记录...")
    save_success = file_manager.save_conversation(test_conversation)
    
    if save_success:
        print("  ✅ 对话记录保存成功")
    else:
        print("  ❌ 对话记录保存失败")
        return False
    
    # 4. 测试解决方案提取
    print("\n🔍 测试解决方案提取...")
    
    # 4.1 测试从指定对话提取
    print("\n  📋 测试从指定对话提取...")
    result1 = await extract_tool.extract_solutions(
        conversation_id=test_conversation.id,
        extract_type="all",
        min_reusability_score=0.7,
        save_solutions=True,
        overwrite_existing=True
    )
    
    if result1["success"]:
        print(f"    ✅ 提取成功: {result1['total_extracted']} 个解决方案")
        print(f"    📊 统计信息: {result1['statistics']}")
        print(f"    📁 文件保存: {len(result1['storage_info']['files_created'])} 个文件")
    else:
        print(f"    ❌ 提取失败: {result1['error']}")
        return False
    
    # 4.2 测试按类型筛选
    print("\n  🎯 测试按类型筛选 (仅代码)...")
    result2 = await extract_tool.extract_solutions(
        conversation_id=test_conversation.id,
        extract_type="code",
        min_reusability_score=0.5,
        save_solutions=False  # 不保存文件，仅提取
    )
    
    if result2["success"]:
        print(f"    ✅ 代码解决方案提取: {result2['total_extracted']} 个")
        code_solutions = [s for s in result2['solutions'] if s['type'] == 'code']
        print(f"    🐍 代码语言: {[s['language'] for s in code_solutions]}")
    else:
        print(f"    ❌ 按类型提取失败: {result2['error']}")
    
    # 4.3 测试批量提取（处理所有对话）
    print("\n  🔄 测试批量提取（所有对话）...")
    result3 = await extract_tool.extract_solutions(
        conversation_id=None,  # 处理所有对话
        extract_type="all",
        min_reusability_score=0.8,  # 高质量阈值
        save_solutions=False  # 不保存，仅统计
    )
    
    if result3["success"]:
        print(f"    ✅ 批量提取完成: {result3['total_extracted']} 个高质量解决方案")
        print(f"    📈 处理了 {result3['conversations_processed']} 个对话")
        print(f"    ⏱️ 处理时间: {result3['processing_time_ms']:.2f}ms")
    else:
        print(f"    ❌ 批量提取失败: {result3['error']}")
    
    # 5. 验证文件输出
    print("\n📄 验证文件输出...")
    solutions_dir = storage_paths.get_solutions_dir()
    if solutions_dir.exists():
        solution_files = list(solutions_dir.glob("extracted_*_solutions_*.json"))
        print(f"  ✅ 找到 {len(solution_files)} 个解决方案文件")
        
        for file_path in solution_files:
            file_size_kb = file_path.stat().st_size / 1024
            print(f"    📄 {file_path.name} ({file_size_kb:.1f} KB)")
    else:
        print("  ⚠️ 解决方案目录不存在")
    
    # 6. 获取提取历史
    print("\n📊 获取提取历史...")
    history = extract_tool.get_extraction_history()
    print(f"  📁 提取文件总数: {history['total_extraction_files']}")
    print(f"  💡 解决方案总数: {history['total_extracted_solutions']}")
    
    print("\n🎉 测试完成！extract-solutions 工具运行正常。")
    return True


async def main():
    """主函数"""
    try:
        success = await test_extract_solutions()
        if success:
            print("\n✅ 所有测试通过！")
            sys.exit(0)
        else:
            print("\n❌ 测试失败！")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())