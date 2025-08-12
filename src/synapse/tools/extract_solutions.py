"""
Extract Solutions MCP工具实现模块

本模块实现了智能解决方案提取功能，从对话记录中识别、分类和评估可重用的代码片段、方法和模式。

主要功能组件：
1. CodeBlockExtractor - 代码块识别和提取
2. SolutionClassifier - 解决方案分类器 
3. ReusabilityEvaluator - 可重用性评分算法
4. SolutionDeduplicator - 去重机制
5. QualityAssessor - 质量评估器
6. ExtractSolutionsTool - 主工具类

核心设计理念：
- 智能化：自动识别和分类不同类型的解决方案
- 质量导向：多维度评估确保提取内容的实用性
- 可扩展性：模块化设计便于功能扩展和维护
- 性能优化：高效算法确保快速响应
"""

import re
import logging
import ast
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set, Any
from collections import Counter
from difflib import SequenceMatcher
import hashlib

from synapse.models.conversation import ConversationRecord, Solution
from synapse.storage.file_manager import FileManager
from synapse.storage.paths import StoragePaths
from synapse.tools.save_conversation import ContentProcessor, LanguageDetector

# 配置日志
logger = logging.getLogger(__name__)


class CodeBlockExtractor:
    """
    代码块提取器
    
    负责从对话内容中识别和提取各种类型的代码块，
    包括markdown格式的代码块和内联代码片段。
    复用现有的ContentProcessor和LanguageDetector组件。
    """
    
    @staticmethod
    def extract_all_code_blocks(content: str) -> List[Dict[str, Any]]:
        """
        提取所有类型的代码块
        
        Args:
            content: 对话内容
            
        Returns:
            List[Dict]: 代码块信息列表
        """
        code_blocks = []
        
        # 1. 提取markdown代码块
        markdown_blocks = ContentProcessor.extract_code_blocks(content)
        for language, code in markdown_blocks:
            code_blocks.append({
                'type': 'markdown',
                'language': language,
                'content': code.strip(),
                'start_pos': content.find(code),
                'length': len(code)
            })
        
        # 2. 提取内联代码片段（增强版）
        inline_blocks = CodeBlockExtractor._extract_inline_code(content)
        code_blocks.extend(inline_blocks)
        
        # 3. 提取可能的纯文本代码
        text_blocks = CodeBlockExtractor._extract_text_code(content)
        code_blocks.extend(text_blocks)
        
        # 4. 去重和排序
        return CodeBlockExtractor._deduplicate_and_sort(code_blocks)
    
    @staticmethod
    def _extract_inline_code(content: str) -> List[Dict[str, Any]]:
        """提取内联代码片段"""
        inline_blocks = []
        
        # 匹配内联代码模式：`代码`
        pattern = r'`([^`\n]{3,100})`'  # 3-100字符，不跨行
        matches = re.finditer(pattern, content)
        
        for match in matches:
            code = match.group(1)
            
            # 过滤掉明显不是代码的内容
            if CodeBlockExtractor._looks_like_code(code):
                language = LanguageDetector.detect_language(code)
                inline_blocks.append({
                    'type': 'inline',
                    'language': language or 'text',
                    'content': code.strip(),
                    'start_pos': match.start(),
                    'length': len(code)
                })
        
        return inline_blocks
    
    @staticmethod
    def _extract_text_code(content: str) -> List[Dict[str, Any]]:
        """从纯文本中提取可能的代码片段"""
        text_blocks = []
        
        # 分行处理
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # 跳过太短或太长的行
            if len(line) < 10 or len(line) > 200:
                continue
            
            # 检查是否像代码行
            if CodeBlockExtractor._looks_like_code_line(line):
                language = LanguageDetector.detect_language(line)
                if language and language != 'text':
                    text_blocks.append({
                        'type': 'text',
                        'language': language,
                        'content': line,
                        'start_pos': i,  # 行号
                        'length': len(line)
                    })
        
        return text_blocks
    
    @staticmethod
    def _looks_like_code(text: str) -> bool:
        """判断文本是否像代码"""
        code_indicators = [
            r'[=();{}[\]]',  # 常见代码符号
            r'\b(function|def|class|import|from|return|if|else|for|while)\b',  # 关键词
            r'[a-zA-Z_][a-zA-Z0-9_]*\s*\(',  # 函数调用
            r'\w+\.\w+',  # 对象属性
            r'\$\w+',  # 变量引用
            r'=>|->|\+=|-=|\*=',  # 操作符
        ]
        
        # 至少匹配一个代码特征
        for pattern in code_indicators:
            if re.search(pattern, text):
                return True
        
        return False
    
    @staticmethod
    def _looks_like_code_line(line: str) -> bool:
        """判断一行文本是否像代码"""
        # 更严格的代码行检测
        strong_indicators = [
            r'^\s*(function|def|class|import|from)\s+',  # 定义语句
            r'^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=',  # 赋值语句
            r'^\s*(if|else|elif|for|while|try|catch|finally)\s*[\(\:]',  # 控制语句
            r'^\s*[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\(',  # 方法调用
            r'^\s*console\.(log|error|warn)',  # 控制台输出
            r'^\s*print\s*\(',  # Python print
            r'^\s*echo\s+',  # Shell echo
        ]
        
        for pattern in strong_indicators:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def _deduplicate_and_sort(code_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重和排序代码块"""
        seen_content = set()
        unique_blocks = []
        
        # 按长度倒序排序，优先保留较长的代码块
        sorted_blocks = sorted(code_blocks, key=lambda x: x['length'], reverse=True)
        
        for block in sorted_blocks:
            content_hash = hashlib.md5(block['content'].encode()).hexdigest()
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_blocks.append(block)
        
        return unique_blocks


class SolutionClassifier:
    """
    解决方案分类器
    
    将提取的内容分类为：
    - code: 可执行代码片段
    - approach: 方法论和解决策略
    - pattern: 设计模式和最佳实践
    """
    
    # 分类关键词模式
    CLASSIFICATION_PATTERNS = {
        'code': {
            'strong_indicators': [
                r'\b(function|def|class|method|procedure)\s+\w+',
                r'^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=',  # 赋值
                r'\b(import|from|include|require)\s+',
                r'\b(return|yield|throw|raise)\s+',
                r'[{}();]',  # 代码符号
            ],
            'weak_indicators': [
                r'\b(variable|parameter|argument|function)\b',
                r'\b(syntax|expression|statement)\b',
            ]
        },
        'approach': {
            'strong_indicators': [
                r'\b(方法|method|approach|strategy|technique|solution)\b',
                r'\b(步骤|step|process|procedure|workflow)\b',
                r'\b(算法|algorithm|logic|思路|idea)\b',
                r'\b(首先|然后|接下来|最后|first|then|next|finally)\b',
            ],
            'weak_indicators': [
                r'\b(可以|should|need to|建议|recommend)\b',
                r'\b(考虑|consider|think|analyze)\b',
            ]
        },
        'pattern': {
            'strong_indicators': [
                r'\b(pattern|模式|design pattern|设计模式)\b',
                r'\b(singleton|factory|observer|策略|单例|工厂|观察者)\b',
                r'\b(architecture|架构|structure|结构)\b',
                r'\b(best practice|最佳实践|convention|约定)\b',
            ],
            'weak_indicators': [
                r'\b(principle|原则|guideline|准则)\b',
                r'\b(standard|标准|规范|specification)\b',
            ]
        }
    }
    
    @classmethod
    def classify_solution(cls, content: str, code_blocks: List[Dict[str, Any]]) -> Tuple[str, float]:
        """
        分类解决方案类型
        
        Args:
            content: 解决方案内容
            code_blocks: 关联的代码块
            
        Returns:
            Tuple[str, float]: (类型, 置信度)
        """
        scores = {
            'code': 0.0,
            'approach': 0.0,
            'pattern': 0.0
        }
        
        text = content.lower()
        
        # 1. 基于关键词的评分
        for solution_type, patterns in cls.CLASSIFICATION_PATTERNS.items():
            score = 0.0
            
            # 强指示器
            for pattern in patterns['strong_indicators']:
                matches = len(re.findall(pattern, text, re.IGNORECASE))
                score += matches * 0.3
            
            # 弱指示器
            for pattern in patterns['weak_indicators']:
                matches = len(re.findall(pattern, text, re.IGNORECASE))
                score += matches * 0.1
            
            scores[solution_type] = score
        
        # 2. 基于代码块的评分调整
        if code_blocks:
            # 有代码块时，增加code类型的分数
            scores['code'] += len(code_blocks) * 0.5
            
            # 检查代码块的完整性
            total_code_length = sum(block['length'] for block in code_blocks)
            if total_code_length > 100:  # 较长的代码更可能是完整解决方案
                scores['code'] += 0.3
        
        # 3. 基于内容长度的调整
        content_length = len(content)
        if content_length > 500:
            # 长文本更可能是approach
            scores['approach'] += 0.2
        elif content_length < 100:
            # 短文本更可能是code或pattern
            if any(word in text for word in ['pattern', '模式']):
                scores['pattern'] += 0.2
            else:
                scores['code'] += 0.1
        
        # 4. 语法完整性检查（仅对code类型）
        if scores['code'] > 0:
            syntax_score = cls._check_code_syntax(content, code_blocks)
            scores['code'] += syntax_score
        
        # 选择最高分的类型
        best_type = max(scores, key=scores.get)
        confidence = min(scores[best_type] / 2.0, 1.0)  # 归一化置信度
        
        # 如果置信度太低，默认为approach
        if confidence < 0.3:
            return 'approach', 0.3
        
        return best_type, confidence
    
    @classmethod
    def _check_code_syntax(cls, content: str, code_blocks: List[Dict[str, Any]]) -> float:
        """检查代码语法完整性"""
        syntax_score = 0.0
        
        for block in code_blocks:
            language = block.get('language', '')
            code = block['content']
            
            if language == 'python':
                syntax_score += cls._check_python_syntax(code)
            elif language in ['javascript', 'typescript']:
                syntax_score += cls._check_js_syntax(code)
            else:
                # 通用语法检查
                syntax_score += cls._check_generic_syntax(code)
        
        return min(syntax_score, 0.5)  # 最多贡献0.5分
    
    @classmethod
    def _check_python_syntax(cls, code: str) -> float:
        """检查Python语法"""
        try:
            ast.parse(code)
            return 0.3  # 语法正确
        except SyntaxError:
            # 检查是否是代码片段（可能不完整但有效）
            if any(keyword in code for keyword in ['def ', 'class ', 'import ', 'from ']):
                return 0.1
            return 0.0
    
    @classmethod
    def _check_js_syntax(cls, code: str) -> float:
        """检查JavaScript语法（简单启发式）"""
        # JavaScript语法检查比较复杂，使用启发式方法
        js_patterns = [
            r'function\s+\w+\s*\([^)]*\)\s*{',
            r'\w+\s*=\s*\([^)]*\)\s*=>\s*{',
            r'const\s+\w+\s*=',
            r'let\s+\w+\s*=',
        ]
        
        for pattern in js_patterns:
            if re.search(pattern, code):
                return 0.2
        
        return 0.1 if '{' in code and '}' in code else 0.0
    
    @classmethod
    def _check_generic_syntax(cls, code: str) -> float:
        """通用语法检查"""
        # 检查是否有配对的括号
        brackets = {'(': ')', '[': ']', '{': '}'}
        stack = []
        
        for char in code:
            if char in brackets:
                stack.append(brackets[char])
            elif char in brackets.values():
                if not stack or stack.pop() != char:
                    return 0.0
        
        # 完全配对得分更高
        return 0.2 if not stack else 0.1


class ReusabilityEvaluator:
    """
    可重用性评估器
    
    基于多个维度评估解决方案的可重用性，计算0.0-1.0的评分：
    - 代码完整性 (0.3权重)
    - 通用性 (0.25权重)  
    - 文档质量 (0.2权重)
    - 复杂度适中 (0.15权重)
    - 实用性 (0.1权重)
    """
    
    @staticmethod
    def evaluate_reusability(
        solution_type: str,
        content: str,
        language: Optional[str],
        code_blocks: List[Dict[str, Any]]
    ) -> float:
        """
        评估解决方案的可重用性
        
        Args:
            solution_type: 解决方案类型
            content: 内容
            language: 编程语言
            code_blocks: 代码块信息
            
        Returns:
            float: 可重用性评分 (0.0-1.0)
        """
        scores = {
            'completeness': 0.0,  # 完整性
            'generality': 0.0,    # 通用性
            'documentation': 0.0,  # 文档质量
            'complexity': 0.0,    # 复杂度适中
            'practicality': 0.0   # 实用性
        }
        
        # 1. 完整性评估
        scores['completeness'] = ReusabilityEvaluator._evaluate_completeness(
            solution_type, content, code_blocks
        )
        
        # 2. 通用性评估
        scores['generality'] = ReusabilityEvaluator._evaluate_generality(content)
        
        # 3. 文档质量评估
        scores['documentation'] = ReusabilityEvaluator._evaluate_documentation(content)
        
        # 4. 复杂度评估
        scores['complexity'] = ReusabilityEvaluator._evaluate_complexity(content, code_blocks)
        
        # 5. 实用性评估
        scores['practicality'] = ReusabilityEvaluator._evaluate_practicality(
            solution_type, content
        )
        
        # 加权计算最终分数
        weights = {
            'completeness': 0.3,
            'generality': 0.25,
            'documentation': 0.2,
            'complexity': 0.15,
            'practicality': 0.1
        }
        
        final_score = sum(scores[aspect] * weights[aspect] for aspect in scores)
        return min(max(final_score, 0.0), 1.0)
    
    @staticmethod
    def _evaluate_completeness(solution_type: str, content: str, code_blocks: List[Dict[str, Any]]) -> float:
        """评估完整性"""
        if solution_type == 'code':
            # 代码类型：检查语法完整性和功能完整性
            score = 0.0
            
            # 基于代码块长度
            total_length = sum(block['length'] for block in code_blocks)
            if total_length > 200:
                score += 0.5
            elif total_length > 50:
                score += 0.3
            else:
                score += 0.1
            
            # 检查是否有函数定义
            if any(re.search(r'\b(function|def|class)\s+\w+', block['content']) 
                   for block in code_blocks):
                score += 0.3
            
            # 检查是否有文档说明
            if len(content) > total_length * 1.5:  # 有额外的说明文字
                score += 0.2
                
        elif solution_type == 'approach':
            # 方法类型：检查步骤完整性
            step_indicators = ['步骤', 'step', '首先', 'first', '然后', 'then', '最后', 'finally']
            step_count = sum(content.lower().count(indicator) for indicator in step_indicators)
            
            if step_count >= 3:
                score = 0.8
            elif step_count >= 2:
                score = 0.6
            else:
                score = 0.4
                
        else:  # pattern
            # 模式类型：检查结构和应用场景说明
            pattern_elements = ['定义', 'definition', '应用', 'application', '优缺点', 'pros', 'cons']
            element_count = sum(1 for element in pattern_elements if element in content.lower())
            
            score = min(element_count * 0.25, 1.0)
        
        return min(score, 1.0)
    
    @staticmethod
    def _evaluate_generality(content: str) -> float:
        """评估通用性"""
        score = 0.5  # 基础分
        
        # 检查参数化程度
        param_indicators = [
            r'\{[^}]+\}',  # 模板参数
            r'\$\w+',      # 变量
            r'参数|param|argument|variable',
            r'配置|config|setting|option'
        ]
        
        param_count = 0
        for pattern in param_indicators:
            param_count += len(re.findall(pattern, content, re.IGNORECASE))
        
        if param_count > 5:
            score += 0.3
        elif param_count > 2:
            score += 0.2
        elif param_count > 0:
            score += 0.1
        
        # 检查通用性关键词
        generic_keywords = [
            '通用', 'generic', '适用于', 'applicable', '可以用于',
            '灵活', 'flexible', '可配置', 'configurable'
        ]
        
        for keyword in generic_keywords:
            if keyword in content.lower():
                score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def _evaluate_documentation(content: str) -> float:
        """评估文档质量"""
        score = 0.0
        
        # 基础长度评分
        if len(content) > 500:
            score += 0.3
        elif len(content) > 200:
            score += 0.2
        else:
            score += 0.1
        
        # 检查注释和说明
        comment_patterns = [
            r'#.*',      # Python注释
            r'//.*',     # JS注释
            r'/\*.*?\*/',  # 块注释
            r'""".*?"""',  # Python文档字符串
        ]
        
        comment_count = 0
        for pattern in comment_patterns:
            comment_count += len(re.findall(pattern, content, re.DOTALL))
        
        if comment_count > 3:
            score += 0.4
        elif comment_count > 0:
            score += 0.2
        
        # 检查结构化说明
        structure_indicators = ['说明', 'description', '用法', 'usage', '示例', 'example']
        for indicator in structure_indicators:
            if indicator in content.lower():
                score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def _evaluate_complexity(content: str, code_blocks: List[Dict[str, Any]]) -> float:
        """评估复杂度适中性（适中的复杂度得分更高）"""
        # 基于内容长度
        total_length = len(content)
        
        if 100 <= total_length <= 1000:
            length_score = 0.5  # 适中长度
        elif 50 <= total_length < 100 or 1000 < total_length <= 2000:
            length_score = 0.3  # 略短或略长
        else:
            length_score = 0.1  # 过短或过长
        
        # 基于代码块复杂度
        code_complexity = 0.0
        if code_blocks:
            for block in code_blocks:
                # 计算圈复杂度的近似值
                complexity_indicators = ['if', 'for', 'while', 'switch', 'case', 'try', 'catch']
                complexity = sum(block['content'].lower().count(indicator) 
                               for indicator in complexity_indicators)
                
                if 2 <= complexity <= 10:
                    code_complexity += 0.3
                elif 1 <= complexity < 2 or 10 < complexity <= 20:
                    code_complexity += 0.2
                else:
                    code_complexity += 0.1
        
        return min(length_score + code_complexity, 1.0)
    
    @staticmethod
    def _evaluate_practicality(solution_type: str, content: str) -> float:
        """评估实用性"""
        # 检查是否解决实际问题
        practical_indicators = [
            '解决', 'solve', '修复', 'fix', '优化', 'optimize',
            '实现', 'implement', '提高', 'improve', '避免', 'avoid'
        ]
        
        practical_count = sum(1 for indicator in practical_indicators 
                            if indicator in content.lower())
        
        base_score = min(practical_count * 0.2, 0.6)
        
        # 根据类型调整
        if solution_type == 'code':
            # 代码类型检查是否有实际功能
            if any(keyword in content.lower() for keyword in 
                   ['function', '函数', 'method', '方法', 'api', '接口']):
                base_score += 0.2
        elif solution_type == 'approach':
            # 方法类型检查是否有具体步骤
            if any(keyword in content.lower() for keyword in 
                   ['步骤', 'step', '操作', 'action', '执行', 'execute']):
                base_score += 0.2
        
        return min(base_score + 0.2, 1.0)  # 基础实用性分


class SolutionDeduplicator:
    """
    解决方案去重器
    
    基于内容相似度和语义特征进行去重，
    避免存储重复的解决方案。
    """
    
    @staticmethod
    def find_duplicates(
        new_solution: Dict[str, Any],
        existing_solutions: List[Solution],
        similarity_threshold: float = 0.8
    ) -> List[Solution]:
        """
        查找重复的解决方案
        
        Args:
            new_solution: 新的解决方案信息
            existing_solutions: 已有的解决方案列表
            similarity_threshold: 相似度阈值
            
        Returns:
            List[Solution]: 重复的解决方案列表
        """
        duplicates = []
        new_content = new_solution.get('content', '')
        new_type = new_solution.get('type', '')
        
        for existing in existing_solutions:
            # 只比较同类型的解决方案
            if existing.type != new_type:
                continue
            
            # 计算内容相似度
            content_similarity = SolutionDeduplicator._calculate_content_similarity(
                new_content, existing.content
            )
            
            # 计算语义相似度
            semantic_similarity = SolutionDeduplicator._calculate_semantic_similarity(
                new_solution, existing
            )
            
            # 综合相似度
            overall_similarity = content_similarity * 0.7 + semantic_similarity * 0.3
            
            if overall_similarity >= similarity_threshold:
                duplicates.append(existing)
        
        return duplicates
    
    @staticmethod
    def _calculate_content_similarity(content1: str, content2: str) -> float:
        """计算内容相似度"""
        if not content1 or not content2:
            return 0.0
        
        # 使用SequenceMatcher计算相似度
        matcher = SequenceMatcher(None, content1.lower(), content2.lower())
        return matcher.ratio()
    
    @staticmethod
    def _calculate_semantic_similarity(solution1: Dict[str, Any], solution2: Solution) -> float:
        """计算语义相似度"""
        similarity = 0.0
        
        # 比较语言
        lang1 = solution1.get('language', '')
        lang2 = solution2.language or ''
        if lang1 and lang2 and lang1 == lang2:
            similarity += 0.3
        
        # 比较描述
        desc1 = solution1.get('description', '')
        desc2 = solution2.description
        if desc1 and desc2:
            desc_similarity = SequenceMatcher(None, desc1.lower(), desc2.lower()).ratio()
            similarity += desc_similarity * 0.4
        
        # 比较关键词
        keywords1 = SolutionDeduplicator._extract_keywords(solution1.get('content', ''))
        keywords2 = SolutionDeduplicator._extract_keywords(solution2.content)
        
        if keywords1 and keywords2:
            common_keywords = keywords1.intersection(keywords2)
            keyword_similarity = len(common_keywords) / max(len(keywords1), len(keywords2))
            similarity += keyword_similarity * 0.3
        
        return min(similarity, 1.0)
    
    @staticmethod
    def _extract_keywords(content: str) -> Set[str]:
        """提取关键词"""
        # 简单的关键词提取
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', content.lower())
        
        # 过滤常见词汇
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'should', 'could', 'can', 'may',
            'this', 'that', 'these', 'those', 'a', 'an'
        }
        
        keywords = {word for word in words if len(word) > 2 and word not in stop_words}
        return keywords


class QualityAssessor:
    """
    质量评估器
    
    对提取的解决方案进行质量评估和过滤，
    确保只有高质量的解决方案被保存。
    """
    
    @staticmethod
    def assess_quality(
        solution_type: str,
        content: str,
        language: Optional[str],
        reusability_score: float
    ) -> Tuple[bool, float, List[str]]:
        """
        评估解决方案质量
        
        Args:
            solution_type: 解决方案类型
            content: 内容
            language: 编程语言
            reusability_score: 可重用性评分
            
        Returns:
            Tuple[bool, float, List[str]]: (是否通过, 质量分数, 问题列表)
        """
        issues = []
        quality_score = 0.0
        
        # 1. 基本长度检查
        if len(content.strip()) < 10:
            issues.append("内容过短")
            return False, 0.0, issues
        
        if len(content) > 10000:
            issues.append("内容过长")
            quality_score -= 0.2
        
        # 2. 内容质量检查
        content_quality = QualityAssessor._check_content_quality(content)
        quality_score += content_quality * 0.4
        
        if content_quality < 0.3:
            issues.append("内容质量过低")
        
        # 3. 安全性检查
        security_score, security_issues = QualityAssessor._check_security(content)
        quality_score += security_score * 0.2
        issues.extend(security_issues)
        
        # 4. 实用性检查
        utility_score = QualityAssessor._check_utility(solution_type, content)
        quality_score += utility_score * 0.2
        
        if utility_score < 0.3:
            issues.append("实用性不足")
        
        # 5. 可重用性权重
        quality_score += reusability_score * 0.2
        
        # 决定是否通过
        min_score = 0.5
        passes = quality_score >= min_score and len([issue for issue in issues 
                                                    if not issue.startswith("警告")]) == 0
        
        return passes, quality_score, issues
    
    @staticmethod
    def _check_content_quality(content: str) -> float:
        """检查内容质量"""
        score = 0.5  # 基础分
        
        # 检查是否有有意义的文本
        meaningful_chars = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', content))
        total_chars = len(content)
        
        if total_chars > 0:
            meaningful_ratio = meaningful_chars / total_chars
            if meaningful_ratio > 0.7:
                score += 0.3
            elif meaningful_ratio > 0.5:
                score += 0.2
            else:
                score -= 0.1
        
        # 检查是否有结构化内容
        structure_indicators = [
            r'\n.*\n',  # 多行
            r'[.!?。！？]',  # 句号
            r'[:：]',    # 冒号
        ]
        
        for pattern in structure_indicators:
            if re.search(pattern, content):
                score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def _check_security(content: str) -> Tuple[float, List[str]]:
        """安全性检查"""
        score = 1.0
        issues = []
        
        # 危险模式检查
        dangerous_patterns = [
            (r'\beval\s*\(', "包含eval函数调用"),
            (r'\bexec\s*\(', "包含exec函数调用"),
            (r'__import__\s*\(', "包含动态导入"),
            (r'\bos\.system\s*\(', "包含系统命令执行"),
            (r'\bsubprocess\.\w+', "包含子进程调用"),
            (r'\brm\s+-rf\s+/', "包含危险的删除命令"),
            (r'DROP\s+TABLE', "包含数据库删除操作"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score -= 0.3
                issues.append(f"安全警告: {message}")
        
        # 敏感信息检查
        sensitive_patterns = [
            (r'\bpassword\s*=\s*["\'][^"\']+["\']', "可能包含密码"),
            (r'\bapi[_-]?key\s*=\s*["\'][^"\']+["\']', "可能包含API密钥"),
            (r'\btoken\s*=\s*["\'][^"\']{20,}["\']', "可能包含认证令牌"),
        ]
        
        for pattern, message in sensitive_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                score -= 0.1
                issues.append(f"警告: {message}")
        
        return max(score, 0.0), issues
    
    @staticmethod
    def _check_utility(solution_type: str, content: str) -> float:
        """检查实用性"""
        if solution_type == 'code':
            # 代码类型：检查是否有实际功能
            utility_indicators = [
                r'\breturn\s+',  # 有返回值
                r'\bprint\s*\(',  # 输出
                r'\bconsole\.log',  # 日志
                r'function\s+\w+',  # 函数定义
                r'class\s+\w+',    # 类定义
            ]
            
            score = 0.2  # 基础分
            for pattern in utility_indicators:
                if re.search(pattern, content, re.IGNORECASE):
                    score += 0.2
                    
        elif solution_type == 'approach':
            # 方法类型：检查是否有具体步骤
            step_patterns = [
                r'\d+[.、]\s*',  # 编号步骤
                r'步骤\s*\d+',   # 步骤关键词
                r'首先|然后|最后|接下来',  # 顺序词
            ]
            
            score = 0.3
            for pattern in step_patterns:
                if re.search(pattern, content):
                    score += 0.2
                    
        else:  # pattern
            # 模式类型：检查是否有清晰的结构
            pattern_indicators = [
                r'定义|definition',
                r'结构|structure', 
                r'应用|application',
                r'优点|缺点|pros|cons',
            ]
            
            score = 0.3
            for pattern in pattern_indicators:
                if re.search(pattern, content, re.IGNORECASE):
                    score += 0.15
        
        return min(score, 1.0)


class ExtractSolutionsTool:
    """
    解决方案提取工具主类
    
    整合所有功能组件，提供完整的解决方案提取服务。
    从对话记录中智能提取、分类、评估和存储可重用的解决方案。
    """
    
    def __init__(self, storage_paths: StoragePaths):
        """
        初始化提取工具
        
        Args:
            storage_paths: 存储路径管理器
        """
        self.storage_paths = storage_paths
        self.file_manager = FileManager(storage_paths)
    
    def extract_solutions(
        self,
        conversation_id: str,
        extract_type: str = "all",
        auto_tag: bool = True,
        min_reusability_score: float = 0.3,
        save_solutions: bool = False
    ) -> Dict[str, Any]:
        """
        从对话中提取解决方案
        
        Args:
            conversation_id: 对话ID
            extract_type: 提取类型 ("code", "approach", "pattern", "all")
            auto_tag: 是否自动标记
            min_reusability_score: 最小可重用性阈值
            save_solutions: 是否保存解决方案到文件
            
        Returns:
            Dict[str, Any]: 提取结果
        """
        try:
            start_time = datetime.now()
            
            # 1. 加载对话记录
            conversation = self.file_manager.load_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"对话记录未找到: {conversation_id}")
            
            # 2. 提取代码块
            code_blocks = CodeBlockExtractor.extract_all_code_blocks(conversation.content)
            
            # 3. 分析和提取解决方案
            extracted_solutions = []
            
            # 从代码块中提取
            for block in code_blocks:
                solutions = self._process_code_block(
                    block, conversation, extract_type, min_reusability_score
                )
                extracted_solutions.extend(solutions)
            
            # 从文本中提取非代码解决方案
            if extract_type in ["approach", "pattern", "all"]:
                text_solutions = self._extract_from_text(
                    conversation, extract_type, min_reusability_score
                )
                extracted_solutions.extend(text_solutions)
            
            # 4. 去重
            deduplicated_solutions = self._deduplicate_solutions(extracted_solutions)
            
            # 5. 质量过滤
            quality_filtered_solutions = []
            quality_issues = []
            
            for solution_data in deduplicated_solutions:
                passes, quality_score, issues = QualityAssessor.assess_quality(
                    solution_data['type'],
                    solution_data['content'],
                    solution_data.get('language'),
                    solution_data['reusability_score']
                )
                
                if passes:
                    solution_data['quality_score'] = quality_score
                    quality_filtered_solutions.append(solution_data)
                else:
                    quality_issues.extend(issues)
            
            # 6. 创建Solution对象
            solution_objects = []
            for solution_data in quality_filtered_solutions:
                try:
                    solution = Solution(
                        type=solution_data['type'],
                        content=solution_data['content'],
                        language=solution_data.get('language'),
                        description=solution_data['description'],
                        reusability_score=solution_data['reusability_score']
                    )
                    solution_objects.append(solution)
                except Exception as e:
                    logger.warning(f"创建Solution对象失败: {e}")
            
            # 7. 可选保存解决方案
            saved_count = 0
            if save_solutions:
                for solution in solution_objects:
                    if self.file_manager.save_solution(solution):
                        saved_count += 1
            
            # 8. 构建返回结果
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = {
                "success": True,
                "conversation_id": conversation_id,
                "extract_type": extract_type,
                "solutions": [solution.to_dict() for solution in solution_objects],
                "total_extracted": len(solution_objects),
                "auto_tag_enabled": auto_tag,
                "statistics": {
                    "code_blocks_found": len(code_blocks),
                    "raw_solutions_extracted": len(extracted_solutions),
                    "after_deduplication": len(deduplicated_solutions),
                    "after_quality_filter": len(quality_filtered_solutions),
                    "quality_issues": quality_issues,
                    "solutions_saved": saved_count,
                    "processing_time_ms": round(processing_time, 2),
                    "min_reusability_threshold": min_reusability_score
                },
                "extraction_summary": self._generate_extraction_summary(
                    solution_objects, code_blocks, processing_time
                )
            }
            
            logger.info(f"解决方案提取完成: {conversation_id}, 提取了{len(solution_objects)}个解决方案")
            return result
            
        except Exception as e:
            logger.error(f"解决方案提取失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "conversation_id": conversation_id,
                "extract_type": extract_type,
                "solutions": [],
                "total_extracted": 0
            }
    
    def _process_code_block(
        self,
        block: Dict[str, Any],
        conversation: ConversationRecord,
        extract_type: str,
        min_score: float
    ) -> List[Dict[str, Any]]:
        """处理单个代码块"""
        solutions = []
        
        # 只处理code类型或all类型
        if extract_type not in ["code", "all"]:
            return solutions
        
        content = block['content']
        language = block['language']
        
        # 分类解决方案
        solution_type, confidence = SolutionClassifier.classify_solution(content, [block])
        
        # 只处理分类为code的解决方案
        if solution_type != 'code':
            return solutions
        
        # 评估可重用性
        reusability_score = ReusabilityEvaluator.evaluate_reusability(
            solution_type, content, language, [block]
        )
        
        # 应用阈值过滤
        if reusability_score < min_score:
            return solutions
        
        # 生成描述
        description = self._generate_description(content, language, conversation.title)
        
        solution_data = {
            'type': solution_type,
            'content': content,
            'language': language,
            'description': description,
            'reusability_score': reusability_score,
            'confidence': confidence,
            'source_block': block
        }
        
        solutions.append(solution_data)
        return solutions
    
    def _extract_from_text(
        self,
        conversation: ConversationRecord,
        extract_type: str,
        min_score: float
    ) -> List[Dict[str, Any]]:
        """从文本中提取非代码解决方案"""
        solutions = []
        
        # 按段落分割内容
        paragraphs = [p.strip() for p in conversation.content.split('\n\n') if p.strip()]
        
        for paragraph in paragraphs:
            if len(paragraph) < 50:  # 过滤过短的段落
                continue
            
            # 分类解决方案
            solution_type, confidence = SolutionClassifier.classify_solution(paragraph, [])
            
            # 检查是否符合提取类型
            if extract_type != "all" and solution_type != extract_type:
                continue
            
            # 跳过code类型（这里只处理approach和pattern）
            if solution_type == 'code':
                continue
            
            # 评估可重用性
            reusability_score = ReusabilityEvaluator.evaluate_reusability(
                solution_type, paragraph, None, []
            )
            
            # 应用阈值过滤
            if reusability_score < min_score:
                continue
            
            # 生成描述
            description = self._generate_description(paragraph, None, conversation.title)
            
            solution_data = {
                'type': solution_type,
                'content': paragraph,
                'language': None,
                'description': description,
                'reusability_score': reusability_score,
                'confidence': confidence,
                'source_paragraph': True
            }
            
            solutions.append(solution_data)
        
        return solutions
    
    def _deduplicate_solutions(self, solutions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """解决方案去重"""
        if len(solutions) <= 1:
            return solutions
        
        unique_solutions = []
        
        for solution in solutions:
            # 检查是否与已有解决方案重复
            is_duplicate = False
            
            for existing in unique_solutions:
                # 同类型比较
                if existing['type'] == solution['type']:
                    content_similarity = SolutionDeduplicator._calculate_content_similarity(
                        solution['content'], existing['content']
                    )
                    
                    if content_similarity > 0.85:  # 高相似度阈值
                        # 保留可重用性分数更高的
                        if solution['reusability_score'] > existing['reusability_score']:
                            unique_solutions.remove(existing)
                            unique_solutions.append(solution)
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_solutions.append(solution)
        
        return unique_solutions
    
    def _generate_description(self, content: str, language: Optional[str], title: str) -> str:
        """生成解决方案描述"""
        # 基于内容和标题生成描述
        if language:
            desc = f"从对话'{title}'中提取的{language}代码解决方案"
        else:
            desc = f"从对话'{title}'中提取的解决方案"
        
        # 尝试从内容中提取关键信息
        content_lower = content.lower()
        
        # 识别主要功能
        if 'function' in content_lower or 'def ' in content:
            desc += "，包含函数定义"
        elif 'class' in content_lower:
            desc += "，包含类定义"
        elif '算法' in content or 'algorithm' in content_lower:
            desc += "，涉及算法实现"
        elif '优化' in content or 'optimize' in content_lower:
            desc += "，关于性能优化"
        elif '方法' in content or 'method' in content_lower:
            desc += "，描述解决方法"
        
        # 限制描述长度
        if len(desc) > 200:
            desc = desc[:197] + "..."
        
        return desc
    
    def _generate_extraction_summary(
        self,
        solutions: List[Solution],
        code_blocks: List[Dict[str, Any]],
        processing_time: float
    ) -> str:
        """生成提取摘要"""
        if not solutions:
            return "未找到符合条件的解决方案"
        
        # 按类型统计
        type_counts = Counter(solution.type for solution in solutions)
        
        summary_parts = []
        if type_counts['code'] > 0:
            summary_parts.append(f"{type_counts['code']}个代码解决方案")
        if type_counts['approach'] > 0:
            summary_parts.append(f"{type_counts['approach']}个方法解决方案") 
        if type_counts['pattern'] > 0:
            summary_parts.append(f"{type_counts['pattern']}个模式解决方案")
        
        summary = f"成功提取{len(solutions)}个解决方案：" + "、".join(summary_parts)
        summary += f"，处理时间{processing_time:.0f}ms"
        
        # 添加质量信息
        avg_reusability = sum(s.reusability_score for s in solutions) / len(solutions)
        summary += f"，平均可重用性评分{avg_reusability:.2f}"
        
        return summary