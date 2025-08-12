"""
Save Conversation MCP工具实现模块

本模块实现了完整的对话保存功能，包括：
1. 内容解析和清理 - 处理原始对话内容，移除无用信息
2. 智能标签提取 - 自动识别编程语言、技术栈、问题类型
3. AI摘要生成 - 生成简洁有用的对话摘要
4. 重要性评估 - 基于多个维度自动评分
5. 重复检测 - 识别相似对话，避免冗余存储
6. 文件存储 - 集成FileManager进行安全存储

核心设计理念：
- 智能化：最大程度减少用户手动输入，自动提取有用信息
- 可靠性：完整的错误处理和数据验证
- 效率性：快速处理，优化存储结构
- 扩展性：易于添加新的标签提取规则和摘要算法
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set, Any
from collections import Counter
from difflib import SequenceMatcher

from synapse.models.conversation import ConversationRecord, Solution
from synapse.storage.file_manager import FileManager
from synapse.storage.paths import StoragePaths
from synapse.tools.search_indexer import SearchIndexer

# 配置日志
logger = logging.getLogger(__name__)


class ContentProcessor:
    """
    对话内容处理器
    
    负责清理原始对话内容，提取有用信息，
    移除无关的格式化字符和噪音数据。
    """
    
    @staticmethod
    def clean_content(raw_content: str) -> str:
        """
        清理对话内容
        
        移除多余的空白字符、特殊标记、重复换行等。
        保留代码块和重要的格式信息。
        
        Args:
            raw_content: 原始对话内容
            
        Returns:
            str: 清理后的内容
        """
        if not raw_content:
            return ""
        
        # 1. 移除过多的连续空白字符
        content = re.sub(r'\s+', ' ', raw_content.strip())
        
        # 2. 保留重要的换行符（在代码块和列表中）
        content = re.sub(r'```([^`]+)```', lambda m: '\n```' + m.group(1) + '```\n', content)
        
        # 3. 标准化换行符
        content = re.sub(r'\r\n?', '\n', content)
        
        # 4. 移除重复的换行符（保留最多2个连续换行）
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 5. 移除行首行尾空白
        lines = [line.strip() for line in content.split('\n')]
        content = '\n'.join(lines)
        
        return content.strip()
    
    @staticmethod
    def extract_code_blocks(content: str) -> List[Tuple[str, str]]:
        """
        提取内容中的代码块
        
        Args:
            content: 对话内容
            
        Returns:
            List[Tuple[str, str]]: (语言, 代码) 的元组列表
        """
        code_blocks = []
        
        # 匹配代码块模式：```语言\n代码\n```
        pattern = r'```(\w+)?\n(.*?)\n```'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for language, code in matches:
            # 如果没有指定语言，尝试自动检测
            if not language:
                language = LanguageDetector.detect_language(code)
            
            code_blocks.append((language or 'text', code.strip()))
        
        # 也匹配单行代码：`代码`
        inline_pattern = r'`([^`\n]+)`'
        inline_matches = re.findall(inline_pattern, content)
        
        for code in inline_matches:
            if len(code) > 5:  # 只保留较长的内联代码
                language = LanguageDetector.detect_language(code)
                code_blocks.append((language or 'text', code))
        
        return code_blocks


class LanguageDetector:
    """
    编程语言检测器
    
    基于关键词、语法模式和文件扩展名识别编程语言。
    支持主流编程语言的检测。
    """
    
    # 编程语言关键词模式
    LANGUAGE_PATTERNS = {
        'python': [
            r'\bdef\s+\w+\s*\(',
            r'\bimport\s+\w+',
            r'\bfrom\s+\w+\s+import',
            r'\bclass\s+\w+\s*:',
            r'\bif\s+__name__\s*==\s*["\']__main__["\']',
        ],
        'javascript': [
            r'\bfunction\s+\w+\s*\(',
            r'\bconst\s+\w+\s*=',
            r'\blet\s+\w+\s*=',
            r'\bvar\s+\w+\s*=',
            r'\b=>\s*{',
            r'\brequire\s*\(',
            r'\bimport.*from',
        ],
        'typescript': [
            r':\s*\w+\s*=',
            r'\binterface\s+\w+',
            r'\btype\s+\w+\s*=',
            r'<[A-Z]\w*>',
        ],
        'java': [
            r'\bpublic\s+class\s+\w+',
            r'\bpublic\s+static\s+void\s+main',
            r'\bimport\s+java\.',
            r'\bSystem\.out\.println',
        ],
        'cpp': [
            r'#include\s*<.*?>',
            r'\bstd::\w+',
            r'\busing\s+namespace\s+std',
            r'\bint\s+main\s*\(',
        ],
        'c': [
            r'#include\s*<.*?>',
            r'\bprintf\s*\(',
            r'\bmain\s*\(',
            r'\breturn\s+0',
        ],
        'go': [
            r'\bpackage\s+\w+',
            r'\bfunc\s+\w+\s*\(',
            r'\bimport\s+\(',
            r'\bfmt\.',
        ],
        'rust': [
            r'\bfn\s+\w+\s*\(',
            r'\buse\s+\w+::',
            r'\bmut\s+\w+',
            r'\bprintln!\s*\(',
        ],
        'sql': [
            r'\bSELECT\s+.*\bFROM\b',
            r'\bINSERT\s+INTO\b',
            r'\bUPDATE\s+.*\bSET\b',
            r'\bDELETE\s+FROM\b',
            r'\bCREATE\s+TABLE\b',
        ],
        'html': [
            r'<html.*?>',
            r'<div.*?>',
            r'<script.*?>',
            r'<!DOCTYPE\s+html>',
        ],
        'css': [
            r'\w+\s*{\s*\w+\s*:',
            r'@media\s+\(',
            r'#\w+\s*{',
            r'\.\w+\s*{',
        ],
        'json': [
            r'{\s*"\w+":\s*',
            r'"\w+"\s*:\s*\[',
        ],
        'yaml': [
            r'^\s*\w+:\s*\w+',
            r'^\s*-\s+\w+',
        ],
        'shell': [
            r'#!/bin/(bash|sh)',
            r'\$\w+',
            r'\becho\s+',
            r'\|\s*grep\s+',
        ],
    }
    
    @classmethod
    def detect_language(cls, code: str) -> Optional[str]:
        """
        检测代码的编程语言
        
        Args:
            code: 代码字符串
            
        Returns:
            Optional[str]: 检测到的语言名称，未检测到返回None
        """
        if not code or len(code.strip()) < 3:
            return None
        
        # 计算每种语言的匹配分数
        language_scores = {}
        
        for language, patterns in cls.LANGUAGE_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                    score += 1
            
            if score > 0:
                language_scores[language] = score
        
        # 返回得分最高的语言
        if language_scores:
            return max(language_scores, key=language_scores.get)
        
        return None


class TagExtractor:
    """
    智能标签提取器
    
    从对话内容中自动提取相关标签，包括：
    - 编程语言标签
    - 技术框架标签  
    - 问题类型标签
    - 领域专业标签
    """
    
    # 技术栈关键词映射
    TECH_KEYWORDS = {
        # 前端框架
        'react': ['react', 'jsx', 'usestate', 'useeffect', 'component'],
        'vue': ['vue', 'vuejs', 'v-if', 'v-for', '@click'],
        'angular': ['angular', 'component', 'service', 'ngif', 'ngfor'],
        'svelte': ['svelte', 'sveltejs'],
        
        # 后端框架
        'django': ['django', 'models.py', 'views.py', 'urls.py'],
        'flask': ['flask', 'app.route', '@app.route'],
        'express': ['express', 'app.get', 'app.post', 'middleware'],
        'fastapi': ['fastapi', 'pydantic', '@app.get', '@app.post'],
        'spring': ['spring', '@autowired', '@component', '@service'],
        
        # 数据库
        'mysql': ['mysql', 'innodb', 'select', 'insert'],
        'postgresql': ['postgresql', 'postgres', 'psql'],
        'mongodb': ['mongodb', 'mongo', 'collection', 'document'],
        'redis': ['redis', 'cache', 'key-value'],
        
        # 开发工具
        'git': ['git', 'commit', 'push', 'pull', 'merge'],
        'docker': ['docker', 'dockerfile', 'container', 'image'],
        'kubernetes': ['kubernetes', 'k8s', 'pod', 'deployment'],
        
        # 测试
        'pytest': ['pytest', 'test_', 'assert'],
        'jest': ['jest', 'test(', 'expect('],
        'unittest': ['unittest', 'testcase'],
        
        # 云服务
        'aws': ['aws', 'ec2', 's3', 'lambda'],
        'gcp': ['gcp', 'google cloud', 'gce'],
        'azure': ['azure', 'microsoft'],
    }
    
    # 问题类型关键词
    PROBLEM_TYPE_KEYWORDS = {
        'bug修复': ['bug', 'error', '错误', '异常', 'exception', 'fix', '修复'],
        '性能优化': ['性能', 'performance', 'optimize', '优化', 'slow', '慢'],
        '功能开发': ['功能', 'feature', '新增', '添加', 'implement', '实现'],
        '代码重构': ['重构', 'refactor', '优化代码', 'clean code'],
        '配置问题': ['配置', 'config', 'setup', '安装', 'install'],
        '学习笔记': ['学习', 'learn', '教程', 'tutorial', '笔记', 'note'],
    }
    
    @classmethod
    def extract_tags(cls, title: str, content: str, code_blocks: List[Tuple[str, str]]) -> List[str]:
        """
        从对话内容中提取标签
        
        Args:
            title: 对话标题
            content: 对话内容  
            code_blocks: 代码块列表
            
        Returns:
            List[str]: 提取的标签列表
        """
        tags = set()
        
        # 合并标题和内容进行分析
        full_text = f"{title} {content}".lower()
        
        # 1. 提取编程语言标签
        languages = set()
        for language, _ in code_blocks:
            if language and language != 'text':
                languages.add(language.lower())
        
        tags.update(languages)
        
        # 2. 提取技术栈标签
        for tech, keywords in cls.TECH_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in full_text:
                    tags.add(tech)
                    break
        
        # 3. 提取问题类型标签
        for problem_type, keywords in cls.PROBLEM_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in full_text:
                    tags.add(problem_type)
                    break
        
        # 4. 提取其他常见技术关键词
        tech_terms = [
            'api', 'rest', 'graphql', 'json', 'xml', 'yaml',
            'microservice', '微服务', 'websocket', 'http', 'https',
            'authentication', '认证', 'authorization', '授权',
            'database', '数据库', 'sql', 'orm',
            'frontend', '前端', 'backend', '后端', 'fullstack', '全栈'
        ]
        
        for term in tech_terms:
            if term in full_text:
                tags.add(term)
        
        # 5. 限制标签数量和长度
        filtered_tags = []
        for tag in tags:
            if len(tag) <= 20 and len(filtered_tags) < 15:  # 最多15个标签
                filtered_tags.append(tag)
        
        return sorted(filtered_tags)


class SummaryGenerator:
    """
    AI摘要生成器
    
    基于关键句提取和内容分析生成对话摘要。
    专注于保留技术细节和解决方案要点。
    """
    
    @staticmethod
    def generate_summary(title: str, content: str, code_blocks: List[Tuple[str, str]]) -> str:
        """
        生成对话摘要
        
        Args:
            title: 对话标题
            content: 对话内容
            code_blocks: 代码块列表
            
        Returns:
            str: 生成的摘要
        """
        if not content:
            return title[:100] if title else "空对话"
        
        # 1. 提取关键句子
        sentences = SummaryGenerator._extract_sentences(content)
        key_sentences = SummaryGenerator._select_key_sentences(sentences, title)
        
        # 2. 生成技术点摘要
        tech_summary = SummaryGenerator._generate_tech_summary(code_blocks)
        
        # 3. 组合摘要
        summary_parts = []
        
        # 添加主要内容摘要
        if key_sentences:
            summary_parts.append(" ".join(key_sentences[:2]))  # 最多两个关键句
        
        # 添加技术点摘要
        if tech_summary:
            summary_parts.append(tech_summary)
        
        # 生成最终摘要
        final_summary = " | ".join(summary_parts) if summary_parts else title
        
        # 限制长度在300字符以内
        if len(final_summary) > 300:
            final_summary = final_summary[:297] + "..."
        
        return final_summary or "对话摘要"
    
    @staticmethod
    def _extract_sentences(content: str) -> List[str]:
        """提取句子"""
        # 按标点符号分割句子
        sentences = re.split(r'[.!?。！？\n]', content)
        
        # 清理和过滤句子
        clean_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10 and len(sentence) < 200:  # 合理长度的句子
                clean_sentences.append(sentence)
        
        return clean_sentences
    
    @staticmethod
    def _select_key_sentences(sentences: List[str], title: str) -> List[str]:
        """选择关键句子"""
        if not sentences:
            return []
        
        # 关键词权重
        important_keywords = [
            '解决', '实现', '使用', '可以', '需要', '问题', '方法', 
            'solution', 'implement', 'use', 'problem', 'method',
            '代码', '函数', '方法', 'code', 'function'
        ]
        
        scored_sentences = []
        title_words = set(title.lower().split()) if title else set()
        
        for sentence in sentences:
            score = 0
            sentence_lower = sentence.lower()
            
            # 包含重要关键词加分
            for keyword in important_keywords:
                if keyword in sentence_lower:
                    score += 1
            
            # 包含标题词汇加分
            for word in title_words:
                if word in sentence_lower:
                    score += 2
            
            # 句子长度合适加分
            if 20 <= len(sentence) <= 100:
                score += 1
            
            scored_sentences.append((sentence, score))
        
        # 按分数排序，返回前几个
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        return [sentence for sentence, _ in scored_sentences[:3]]
    
    @staticmethod
    def _generate_tech_summary(code_blocks: List[Tuple[str, str]]) -> str:
        """生成技术点摘要"""
        if not code_blocks:
            return ""
        
        languages = set()
        for language, _ in code_blocks:
            if language and language != 'text':
                languages.add(language)
        
        if languages:
            if len(languages) == 1:
                return f"涉及{list(languages)[0]}代码实现"
            else:
                return f"涉及{', '.join(sorted(languages))}等技术"
        
        return "包含代码示例"


class ImportanceEvaluator:
    """
    对话重要性评估器
    
    基于多个维度自动评估对话的重要性等级：
    1. 内容长度和复杂度
    2. 代码块数量和质量  
    3. 技术深度和广度
    4. 解决方案的完整性
    """
    
    @staticmethod
    def evaluate_importance(
        title: str, 
        content: str, 
        code_blocks: List[Tuple[str, str]],
        tags: List[str]
    ) -> int:
        """
        评估对话重要性
        
        Args:
            title: 标题
            content: 内容
            code_blocks: 代码块
            tags: 标签列表
            
        Returns:
            int: 重要性等级 (1-5)
        """
        score = 0
        
        # 1. 内容长度评分 (0-2分)
        content_length = len(content)
        if content_length > 2000:
            score += 2
        elif content_length > 1000:
            score += 1.5
        elif content_length > 500:
            score += 1
        
        # 2. 代码块评分 (0-2分)
        if len(code_blocks) >= 3:
            score += 2
        elif len(code_blocks) >= 2:
            score += 1.5
        elif len(code_blocks) >= 1:
            score += 1
        
        # 3. 技术标签评分 (0-1分)
        tech_tag_count = len([tag for tag in tags if tag in TagExtractor.TECH_KEYWORDS])
        if tech_tag_count >= 3:
            score += 1
        elif tech_tag_count >= 2:
            score += 0.5
        
        # 4. 问题复杂度评分 (0-1分)
        complex_keywords = [
            '架构', 'architecture', '设计模式', 'design pattern',
            '性能优化', 'performance', '安全', 'security',
            '分布式', 'distributed', '微服务', 'microservice'
        ]
        
        full_text = f"{title} {content}".lower()
        complex_score = sum(1 for keyword in complex_keywords if keyword in full_text)
        if complex_score >= 2:
            score += 1
        elif complex_score >= 1:
            score += 0.5
        
        # 转换为1-5等级
        if score >= 5:
            return 5
        elif score >= 4:
            return 4
        elif score >= 2.5:
            return 3
        elif score >= 1:
            return 2
        else:
            return 1


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
    
    集成所有功能组件，提供完整的对话保存服务：
    - 内容处理和清理
    - 智能标签提取
    - 摘要生成
    - 重要性评估
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
        
    def save_conversation(
        self,
        title: str,
        content: str,
        user_tags: Optional[List[str]] = None,
        user_category: Optional[str] = None,
        user_importance: Optional[int] = None,
        check_duplicates: bool = True
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
            # 1. 内容清理
            cleaned_content = ContentProcessor.clean_content(content)
            if not cleaned_content:
                raise ValueError("对话内容为空")
            
            # 2. 提取代码块
            code_blocks = ContentProcessor.extract_code_blocks(cleaned_content)
            
            # 3. 智能标签提取
            auto_tags = TagExtractor.extract_tags(title, cleaned_content, code_blocks)
            
            # 合并用户标签和自动标签
            all_tags = list(set((user_tags or []) + auto_tags))
            
            # 4. 生成摘要
            summary = SummaryGenerator.generate_summary(title, cleaned_content, code_blocks)
            
            # 5. 评估重要性
            if user_importance is not None:
                importance = max(1, min(5, user_importance))  # 确保在1-5范围内
            else:
                importance = ImportanceEvaluator.evaluate_importance(
                    title, cleaned_content, code_blocks, all_tags
                )
            
            # 6. 检查重复（如果启用）
            duplicates = []
            if check_duplicates:
                # 加载最近的对话记录进行重复检测
                recent_conversations = self._load_recent_conversations(limit=50)
                duplicates = DuplicateDetector.find_duplicates(
                    title, cleaned_content, recent_conversations
                )
            
            # 7. 创建对话记录
            conversation = ConversationRecord(
                title=title,
                content=cleaned_content,
                summary=summary,
                tags=all_tags,
                category=user_category or "general",
                importance=importance
            )
            
            # 8. 保存到文件
            save_success = self.file_manager.save_conversation(conversation)
            
            if not save_success:
                raise RuntimeError("文件保存失败")
            
            # 9. 更新搜索索引
            index_success = self.search_indexer.add_conversation(conversation)
            
            if not index_success:
                logger.warning(f"搜索索引更新失败: {conversation.id}")
            
            logger.info(f"成功保存对话: {conversation.id}")
            
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
                    "code_blocks_count": len(code_blocks),
                    "auto_tags_count": len(auto_tags),
                    "user_tags_count": len(user_tags or [])
                },
                "duplicates_found": len(duplicates),
                "duplicate_ids": [dup.id for dup in duplicates] if duplicates else [],
                "storage_path": str(self.file_manager._get_conversation_file_path(conversation.id, conversation.created_at.date()))
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