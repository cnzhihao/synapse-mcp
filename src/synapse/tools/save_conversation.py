"""
Save Conversation MCP工具实现模块

本模块实现了基于AI的对话保存功能，包括：
1. AI分析结果处理 - 接收并处理AI生成的摘要、标签、分类等
2. 重复检测 - 识别相似对话，避免冗余存储
3. 文件存储 - 集成FileManager进行安全存储

核心设计理念：
- AI驱动：完全依赖AI分析结果，无硬编码处理逻辑
- 可靠性：完整的错误处理和数据验证
- 效率性：快速处理，优化存储结构
- 扩展性：支持多种AI分析结果格式
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher

from synapse.models.conversation import ConversationRecord, Solution
from synapse.storage.file_manager import FileManager
from synapse.storage.paths import StoragePaths
from synapse.tools.search_indexer import SearchIndexer

# 配置日志
logger = logging.getLogger(__name__)




class DuplicateDetector:
    """
    重复对话检测器
    
    基于标题相似度和内容指纹检测重复对话，
    避免存储重复内容。
    """
    
    @staticmethod
    def find_duplicates(
        new_title: str,
        new_content: str,
        existing_conversations: List[ConversationRecord],
        similarity_threshold: float = 0.85
    ) -> List[ConversationRecord]:
        """
        检测重复对话
        
        Args:
            new_title: 新对话标题
            new_content: 新对话内容
            existing_conversations: 现有对话列表
            similarity_threshold: 相似度阈值
            
        Returns:
            List[ConversationRecord]: 检测到的重复对话列表
        """
        duplicates = []
        
        for conv in existing_conversations:
            # 计算标题相似度
            title_similarity = DuplicateDetector._calculate_similarity(
                new_title.lower(), conv.title.lower()
            )
            
            # 计算内容相似度（使用前500字符避免太长）
            content_similarity = DuplicateDetector._calculate_similarity(
                new_content[:500].lower(), 
                conv.content[:500].lower()
            )
            
            # 综合相似度（标题权重更高）
            overall_similarity = title_similarity * 0.6 + content_similarity * 0.4
            
            if overall_similarity >= similarity_threshold:
                duplicates.append(conv)
        
        return duplicates
    
    @staticmethod
    def _calculate_similarity(text1: str, text2: str) -> float:
        """计算两个文本的相似度"""
        if not text1 or not text2:
            return 0.0
        
        # 使用SequenceMatcher计算相似度
        matcher = SequenceMatcher(None, text1, text2)
        return matcher.ratio()


class SaveConversationTool:
    """
    保存对话工具的主要实现类
    
    基于AI分析结果，提供完整的对话保存服务：
    - AI分析结果处理（摘要、标签、分类、解决方案）
    - 重复检测
    - 文件存储和索引更新
    """
    
    def __init__(self, storage_paths: StoragePaths):
        """
        初始化保存对话工具
        
        Args:
            storage_paths: 存储路径管理器
        """
        self.storage_paths = storage_paths
        self.file_manager = FileManager(storage_paths)
        self.search_indexer = SearchIndexer(storage_paths)
        
    async def save_conversation(
        self,
        title: str,
        content: str,
        user_tags: Optional[List[str]] = None,
        user_category: Optional[str] = None,
        user_importance: Optional[int] = None,
        check_duplicates: bool = True,
        # 新增：接收AI分析结果的参数
        ai_summary: Optional[str] = None,
        ai_tags: Optional[List[str]] = None,
        ai_importance: Optional[int] = None,
        ai_category: Optional[str] = None,
        ai_solutions: Optional[List[Dict[str, Any]]] = None,
        ctx = None
    ) -> Dict[str, Any]:
        """
        保存对话记录
        
        Args:
            title: 对话标题
            content: 对话内容
            user_tags: 用户指定的标签（可选）
            user_category: 用户指定的分类（可选）
            user_importance: 用户指定的重要性（可选）
            check_duplicates: 是否检查重复
            
        Returns:
            Dict[str, Any]: 保存结果
        """
        try:
            if ctx:
                await ctx.info(f"开始保存对话: {title}")
            
            # 1. 基础内容验证
            if not content or not content.strip():
                raise ValueError("对话内容为空")
            
            # 直接使用原始内容，让AI处理内容清理
            cleaned_content = content.strip()
            
            # 2-5. 使用AI分析结果
            if not ai_summary:
                raise ValueError("需要AI分析结果才能保存对话。请先调用conversation_analysis_prompt获取分析结果。")
            
            if ctx:
                await ctx.info("使用AI分析结果进行处理...")
            
            # 使用AI分析结果
            summary = ai_summary
            auto_tags = ai_tags or []
            importance = user_importance if user_importance is not None else (ai_importance or 3)
            category = user_category or ai_category or "general"
            
            # 合并用户标签和自动标签
            all_tags = list(set((user_tags or []) + auto_tags))
            
            # 6. 检查重复（如果启用）
            duplicates = []
            if check_duplicates:
                if ctx:
                    await ctx.info("检查重复对话...")
                # 加载最近的对话记录进行重复检测
                recent_conversations = self._load_recent_conversations(limit=50)
                duplicates = DuplicateDetector.find_duplicates(
                    title, cleaned_content, recent_conversations
                )
                if ctx and duplicates:
                    await ctx.info(f"发现 {len(duplicates)} 个重复对话")
            
            # 7. 创建对话记录
            conversation = ConversationRecord(
                title=title,
                content=cleaned_content,
                summary=summary,
                tags=all_tags,
                category=category,
                importance=importance
            )
            
            # 添加AI提取的解决方案
            if ai_solutions:
                conversation.solutions = [
                    Solution(**sol) for sol in ai_solutions
                ]
            
            # 8. 保存到文件
            save_success = self.file_manager.save_conversation(conversation)
            
            if not save_success:
                raise RuntimeError("文件保存失败")
            
            # 9. 更新搜索索引
            if ctx:
                await ctx.info("更新搜索索引...")
            index_success = self.search_indexer.add_conversation(conversation)
            
            if not index_success:
                logger.warning(f"搜索索引更新失败: {conversation.id}")
                if ctx:
                    await ctx.info("搜索索引更新失败，但对话已保存")
            
            logger.info(f"成功保存对话: {conversation.id}")
            if ctx:
                await ctx.info(f"对话保存完成: {conversation.id}")
            
            # 10. 返回结果
            return {
                "success": True,
                "conversation": {
                    "id": conversation.id,
                    "title": conversation.title,
                    "summary": conversation.summary,
                    "tags": conversation.tags,
                    "category": conversation.category,
                    "importance": conversation.importance,
                    "created_at": conversation.created_at.isoformat(),
                    "solutions_count": len(conversation.solutions),
                    "auto_tags_count": len(auto_tags),
                    "user_tags_count": len(user_tags or [])
                },
                "duplicates_found": len(duplicates),
                "duplicate_ids": [dup.id for dup in duplicates] if duplicates else [],
                "storage_path": str(self.file_manager._get_conversation_file_path(conversation.id, conversation.created_at.date())),
                "ai_processing": {
                    "solutions_extracted": len(conversation.solutions),
                    "analysis_quality": "AI-powered"
                }
            }
            
        except Exception as e:
            logger.error(f"保存对话失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    
    def _load_recent_conversations(self, limit: int = 50) -> List[ConversationRecord]:
        """
        加载最近的对话记录用于重复检测
        
        Args:
            limit: 加载数量限制
            
        Returns:
            List[ConversationRecord]: 最近的对话记录列表
        """
        try:
            # 获取最近的对话ID列表
            conversation_ids = self.file_manager.list_conversations(limit=limit)
            
            # 加载对话记录
            conversations = []
            for conv_id in conversation_ids:
                conv = self.file_manager.load_conversation(conv_id)
                if conv:
                    conversations.append(conv)
            
            return conversations
            
        except Exception as e:
            logger.warning(f"加载最近对话记录失败: {e}")
            return []