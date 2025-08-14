"""
Extract Solutions MCP工具实现模块

本模块实现了从已保存对话中提取解决方案并单独保存的功能，包括：
1. 对话解决方案提取 - 从现有对话记录中提取所有解决方案
2. 解决方案去重和质量评估 - 确保解决方案质量和唯一性
3. 独立存储管理 - 将解决方案保存到独立的solutions目录
4. 解决方案索引更新 - 更新搜索索引以支持解决方案查找

核心设计理念：
- 后处理方式：从已保存的对话中提取解决方案，不影响对话保存流程
- 质量导向：确保提取的解决方案具有高可重用性和实用性
- 独立管理：解决方案作为独立实体管理，支持单独查询和使用
- 性能优化：批量处理和智能缓存，提供高效的提取性能
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from synapse.models.conversation import ConversationRecord, Solution
from synapse.storage.file_manager import FileManager
from synapse.storage.paths import StoragePaths

# 配置日志
logger = logging.getLogger(__name__)


class SolutionExtractor:
    """
    解决方案提取器
    
    从对话记录中提取解决方案，提供智能的解决方案识别、
    质量评估和去重功能。
    """
    
    def __init__(self):
        """初始化解决方案提取器"""
        self.extracted_solutions: Dict[str, Solution] = {}
        self.quality_threshold = 0.3  # 最低质量阈值
        
    def extract_from_conversation(
        self, 
        conversation: ConversationRecord,
        extract_type: str = "all",
        min_reusability_score: float = 0.3
    ) -> List[Solution]:
        """
        从单个对话记录中提取解决方案
        
        Args:
            conversation: 对话记录对象
            extract_type: 提取类型 ("code", "approach", "pattern", "all")
            min_reusability_score: 最小可重用性分数阈值
            
        Returns:
            List[Solution]: 提取的解决方案列表
        """
        if not conversation.solutions:
            return []
        
        extracted = []
        
        for solution in conversation.solutions:
            # 应用类型过滤
            if extract_type != "all" and solution.type != extract_type:
                continue
            
            # 应用质量过滤
            if solution.reusability_score < min_reusability_score:
                continue
            
            # 检查去重
            solution_key = self._generate_solution_key(solution)
            if solution_key in self.extracted_solutions:
                # 如果已存在相同解决方案，选择质量更高的
                existing = self.extracted_solutions[solution_key]
                if solution.reusability_score > existing.reusability_score:
                    self.extracted_solutions[solution_key] = solution
                    # 更新列表中的解决方案
                    for i, ext_sol in enumerate(extracted):
                        if self._generate_solution_key(ext_sol) == solution_key:
                            extracted[i] = solution
                            break
                continue
            
            # 添加新解决方案
            self.extracted_solutions[solution_key] = solution
            extracted.append(solution)
        
        return extracted
    
    def _generate_solution_key(self, solution: Solution) -> str:
        """
        生成解决方案的唯一键用于去重
        
        Args:
            solution: 解决方案对象
            
        Returns:
            str: 解决方案的唯一标识键
        """
        # 基于内容和类型生成键
        content_hash = hash(solution.content.strip().lower())
        type_lang = f"{solution.type}_{solution.language or 'none'}"
        return f"{type_lang}_{content_hash}"
    
    def get_extraction_statistics(self) -> Dict[str, Any]:
        """
        获取提取统计信息
        
        Returns:
            Dict[str, Any]: 详细的提取统计信息
        """
        solutions = list(self.extracted_solutions.values())
        
        # 按类型统计
        type_counts = {"code": 0, "approach": 0, "pattern": 0}
        language_counts = {}
        
        total_reusability = 0.0
        quality_levels = {"high": 0, "medium": 0, "low": 0}
        
        for solution in solutions:
            # 类型统计
            type_counts[solution.type] += 1
            
            # 语言统计
            lang = solution.language or "none"
            language_counts[lang] = language_counts.get(lang, 0) + 1
            
            # 质量统计
            total_reusability += solution.reusability_score
            if solution.reusability_score >= 0.8:
                quality_levels["high"] += 1
            elif solution.reusability_score >= 0.6:
                quality_levels["medium"] += 1
            else:
                quality_levels["low"] += 1
        
        return {
            "total_solutions": len(solutions),
            "by_type": type_counts,
            "by_language": language_counts,
            "average_reusability": round(total_reusability / max(len(solutions), 1), 3),
            "quality_distribution": quality_levels,
            "unique_languages": len([lang for lang in language_counts.keys() if lang != "none"])
        }


class ExtractSolutionsTool:
    """
    提取解决方案工具的主要实现类
    
    提供完整的解决方案提取服务：
    - 从已保存的对话记录中提取解决方案
    - 解决方案去重和质量评估
    - 独立存储和索引管理
    """
    
    def __init__(self, storage_paths: StoragePaths):
        """
        初始化提取解决方案工具
        
        Args:
            storage_paths: 存储路径管理器
        """
        self.storage_paths = storage_paths
        self.file_manager = FileManager(storage_paths)
        self.extractor = SolutionExtractor()
        
        # 确保solutions目录存在
        self.solutions_dir = storage_paths.get_solutions_dir()
        self.solutions_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("ExtractSolutionsTool 初始化完成")
    
    async def extract_solutions(
        self,
        conversation_id: Optional[str] = None,
        extract_type: str = "all",
        min_reusability_score: float = 0.3,
        save_solutions: bool = True,
        overwrite_existing: bool = False,
        ctx = None
    ) -> Dict[str, Any]:
        """
        从对话记录中提取解决方案
        
        Args:
            conversation_id: 指定对话ID，为None时处理所有对话
            extract_type: 提取类型 ("code", "approach", "pattern", "all")
            min_reusability_score: 最小可重用性分数阈值
            save_solutions: 是否保存解决方案到文件系统
            overwrite_existing: 是否覆盖已存在的解决方案文件
            ctx: MCP上下文对象
            
        Returns:
            Dict[str, Any]: 提取结果和统计信息
        """
        try:
            if ctx:
                await ctx.info(f"开始提取解决方案 - 对话ID: {conversation_id or 'ALL'}")
            
            # 参数验证
            if extract_type not in ["code", "approach", "pattern", "all"]:
                raise ValueError("extract_type必须是 'code', 'approach', 'pattern' 或 'all'")
            
            if not isinstance(min_reusability_score, (int, float)) or min_reusability_score < 0 or min_reusability_score > 1:
                raise ValueError("min_reusability_score必须在0.0-1.0之间")
            
            # 重置提取器
            self.extractor = SolutionExtractor()
            
            # 确定要处理的对话
            conversations_to_process = []
            
            if conversation_id:
                # 处理指定对话
                if ctx:
                    await ctx.info(f"加载指定对话: {conversation_id}")
                
                conversation = self.file_manager.load_conversation(conversation_id)
                if not conversation:
                    raise ValueError(f"找不到指定的对话记录: {conversation_id}")
                
                conversations_to_process = [conversation]
                
            else:
                # 处理所有对话
                if ctx:
                    await ctx.info("加载所有对话记录...")
                
                conversation_ids = self.file_manager.list_conversations()
                
                if ctx:
                    await ctx.info(f"找到 {len(conversation_ids)} 个对话记录")
                
                for i, conv_id in enumerate(conversation_ids):
                    if ctx and i % 50 == 0:  # 每50个对话报告一次进度
                        progress = i / len(conversation_ids)
                        await ctx.report_progress(progress, f"加载对话 {i+1}/{len(conversation_ids)}")
                    
                    conv = self.file_manager.load_conversation(conv_id)
                    if conv:
                        conversations_to_process.append(conv)
            
            if ctx:
                await ctx.info(f"开始从 {len(conversations_to_process)} 个对话中提取解决方案...")
            
            # 执行解决方案提取
            all_solutions = []
            conversations_with_solutions = 0
            
            for i, conversation in enumerate(conversations_to_process):
                if ctx and len(conversations_to_process) > 10 and i % 10 == 0:
                    progress = i / len(conversations_to_process)
                    await ctx.report_progress(progress, f"提取进度 {i+1}/{len(conversations_to_process)}")
                
                extracted = self.extractor.extract_from_conversation(
                    conversation, extract_type, min_reusability_score
                )
                
                if extracted:
                    conversations_with_solutions += 1
                    all_solutions.extend(extracted)
                    
                    logger.debug(f"从对话 {conversation.id} 提取了 {len(extracted)} 个解决方案")
            
            # 获取统计信息
            stats = self.extractor.get_extraction_statistics()
            
            if ctx:
                await ctx.info(f"提取完成 - 总计 {stats['total_solutions']} 个解决方案")
            
            # 保存解决方案到文件系统（如果启用）
            saved_files = []
            if save_solutions and all_solutions:
                if ctx:
                    await ctx.info("开始保存解决方案到文件系统...")
                
                saved_files = await self._save_solutions_to_files(
                    all_solutions, overwrite_existing, ctx
                )
            
            # 构建详细的返回结果
            result = {
                "success": True,
                "solutions": [sol.to_dict() for sol in all_solutions],
                "total_extracted": len(all_solutions),
                "conversations_processed": len(conversations_to_process),
                "conversations_with_solutions": conversations_with_solutions,
                "extraction_summary": self._generate_extraction_summary(stats, extract_type),
                "statistics": {
                    **stats,
                    "processing_time_ms": 0,  # 会在调用方计算
                    "extraction_parameters": {
                        "extract_type": extract_type,
                        "min_reusability_score": min_reusability_score,
                        "target_conversation": conversation_id
                    }
                },
                "storage_info": {
                    "solutions_saved": len(saved_files) if save_solutions else 0,
                    "save_enabled": save_solutions,
                    "files_created": saved_files if save_solutions else [],
                    "overwrite_mode": overwrite_existing
                }
            }
            
            logger.info(f"解决方案提取完成 - 提取了 {len(all_solutions)} 个解决方案")
            return result
            
        except Exception as e:
            logger.error(f"解决方案提取失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "solutions": [],
                "total_extracted": 0,
                "extraction_summary": f"提取失败: {str(e)}"
            }
    
    async def _save_solutions_to_files(
        self, 
        solutions: List[Solution], 
        overwrite_existing: bool,
        ctx = None
    ) -> List[str]:
        """
        将解决方案保存到文件系统
        
        Args:
            solutions: 解决方案列表
            overwrite_existing: 是否覆盖已存在的文件
            ctx: MCP上下文对象
            
        Returns:
            List[str]: 保存的文件路径列表
        """
        saved_files = []
        
        # 按类型分组保存
        grouped_solutions = {"code": [], "approach": [], "pattern": []}
        
        for solution in solutions:
            grouped_solutions[solution.type].append(solution)
        
        # 为每种类型创建单独的文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for solution_type, type_solutions in grouped_solutions.items():
            if not type_solutions:
                continue
            
            filename = f"extracted_{solution_type}_solutions_{timestamp}.json"
            file_path = self.solutions_dir / filename
            
            # 检查文件是否存在
            if file_path.exists() and not overwrite_existing:
                logger.warning(f"解决方案文件已存在，跳过保存: {filename}")
                continue
            
            # 准备文件内容
            file_content = {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "solution_type": solution_type,
                    "total_solutions": len(type_solutions),
                    "extraction_source": "conversation_records",
                    "format_version": "1.0"
                },
                "solutions": [sol.to_dict() for sol in type_solutions]
            }
            
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(file_content, f, indent=2, ensure_ascii=False)
                
                saved_files.append(str(file_path))
                
                if ctx:
                    await ctx.info(f"保存 {len(type_solutions)} 个 {solution_type} 解决方案到: {filename}")
                
                logger.info(f"成功保存解决方案文件: {file_path}")
                
            except Exception as e:
                logger.error(f"保存解决方案文件失败 {file_path}: {e}")
                if ctx:
                    await ctx.info(f"保存文件失败: {filename} - {str(e)}")
        
        return saved_files
    
    def _generate_extraction_summary(
        self, 
        stats: Dict[str, Any], 
        extract_type: str
    ) -> str:
        """
        生成提取结果摘要
        
        Args:
            stats: 统计信息
            extract_type: 提取类型
            
        Returns:
            str: 人性化的提取摘要
        """
        total = stats["total_solutions"]
        
        if total == 0:
            return f"未找到符合条件的{extract_type}解决方案"
        
        # 基础摘要
        summary_parts = [f"成功提取 {total} 个解决方案"]
        
        # 类型分布
        type_counts = stats["by_type"]
        type_descriptions = []
        
        if type_counts["code"] > 0:
            type_descriptions.append(f"{type_counts['code']} 个代码解决方案")
        if type_counts["approach"] > 0:
            type_descriptions.append(f"{type_counts['approach']} 个方法论解决方案")
        if type_counts["pattern"] > 0:
            type_descriptions.append(f"{type_counts['pattern']} 个模式解决方案")
        
        if type_descriptions:
            summary_parts.append("包含: " + "、".join(type_descriptions))
        
        # 质量信息
        avg_quality = stats["average_reusability"]
        quality_desc = "高质量" if avg_quality >= 0.8 else "中等质量" if avg_quality >= 0.6 else "基础质量"
        summary_parts.append(f"平均质量: {quality_desc} (评分 {avg_quality})")
        
        # 语言信息
        if stats["unique_languages"] > 0:
            summary_parts.append(f"涉及 {stats['unique_languages']} 种编程语言")
        
        return "；".join(summary_parts)
    
    def get_extraction_history(self) -> Dict[str, Any]:
        """
        获取解决方案提取历史记录
        
        Returns:
            Dict[str, Any]: 提取历史信息
        """
        try:
            history_files = list(self.solutions_dir.glob("extracted_*_solutions_*.json"))
            
            history = []
            total_solutions = 0
            
            for file_path in sorted(history_files, key=lambda x: x.stat().st_mtime, reverse=True):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_data = json.load(f)
                    
                    metadata = file_data.get("metadata", {})
                    solutions_count = len(file_data.get("solutions", []))
                    total_solutions += solutions_count
                    
                    history.append({
                        "filename": file_path.name,
                        "file_path": str(file_path),
                        "created_at": metadata.get("created_at"),
                        "solution_type": metadata.get("solution_type"),
                        "solutions_count": solutions_count,
                        "file_size_kb": round(file_path.stat().st_size / 1024, 2)
                    })
                    
                except Exception as e:
                    logger.warning(f"读取解决方案文件失败 {file_path}: {e}")
                    continue
            
            return {
                "total_extraction_files": len(history),
                "total_extracted_solutions": total_solutions,
                "extraction_history": history,
                "solutions_directory": str(self.solutions_dir),
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取提取历史失败: {e}")
            return {
                "total_extraction_files": 0,
                "total_extracted_solutions": 0,
                "extraction_history": [],
                "error": str(e)
            }