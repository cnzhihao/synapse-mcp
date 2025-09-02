"""
Synapse MCP 核心数据模型模块

本模块定义了 Synapse MCP 系统中使用的核心数据模型：
- ConversationRecord: 对话记录数据模型，存储完整的AI对话信息
- Solution: 解决方案数据模型，存储从对话中提取的可重用代码和方案

这些模型使用 Pydantic 进行数据验证、序列化和反序列化，
确保数据类型安全和与MCP协议的兼容性。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
import uuid
import json


class Solution(BaseModel):
    """
    解决方案数据模型
    
    用于存储从对话中提取的可重用代码片段、解决方案和设计模式。
    每个解决方案都有类型分类、内容描述、可重用性评分和引用计数。
    
    Attributes:
        id: 唯一标识符，自动生成UUID格式
        type: 解决方案类型 - "code"(代码), "approach"(方法), "pattern"(模式)
        content: 解决方案的实际内容
        language: 编程语言（仅对代码类型有效）
        description: 解决方案的描述和使用场景
        tags: 标签列表，用于分类和搜索，与ConversationRecord保持一致
        reusability_score: 可重用性评分，0.0-1.0之间，越高表示越容易重用
        reference_count: 引用计数，追踪解决方案被上下文注入使用的次数
        last_referenced: 最后引用时间，用于时间权重计算
    """
    
    id: str = Field(default_factory=lambda: f"sol_{uuid.uuid4().hex[:8]}")
    type: Literal["code", "approach", "pattern"] = Field(..., description="解决方案类型")
    content: str = Field(..., min_length=1, description="解决方案内容")
    language: Optional[str] = Field(None, description="编程语言（代码类型时使用）")
    description: str = Field(..., min_length=1, description="解决方案描述")
    tags: List[str] = Field(default_factory=list, description="标签列表，用于分类和搜索")
    reusability_score: float = Field(..., ge=0.0, le=1.0, description="可重用性评分")
    reference_count: int = Field(default=0, ge=0, description="引用计数")
    last_referenced: Optional[datetime] = Field(default=None, description="最后引用时间")
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """
        验证和清理标签
        
        - 移除重复标签
        - 转换为小写
        - 移除空字符串
        - 限制标签长度
        """
        if not v:
            return []
        
        # 清理标签：去重、小写化、移除空白
        cleaned_tags = []
        seen = set()
        
        for tag in v:
            if isinstance(tag, str):
                clean_tag = tag.strip().lower()
                if clean_tag and len(clean_tag) <= 50 and clean_tag not in seen:
                    cleaned_tags.append(clean_tag)
                    seen.add(clean_tag)
        
        return cleaned_tags
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v, info):
        """
        验证编程语言字段
        
        如果类型是"code"，则language字段不能为空。
        如果类型不是"code"，则language应该为None。
        """
        solution_type = info.data.get('type') if info.data else None
        if solution_type == 'code' and not v:
            raise ValueError('代码类型的解决方案必须指定编程语言')
        if solution_type != 'code' and v:
            # 非代码类型的解决方案不需要语言字段
            return None
        return v
    
    @field_validator('reusability_score')
    @classmethod
    def validate_reusability_score(cls, v):
        """验证可重用性评分在有效范围内"""
        if v < 0.0 or v > 1.0:
            raise ValueError('可重用性评分必须在0.0-1.0之间')
        return round(v, 2)  # 保留2位小数
    
    def increment_reference(self) -> None:
        """
        增加引用计数
        
        当解决方案被上下文注入系统使用时调用此方法。
        同时更新最后引用时间。
        """
        self.reference_count += 1
        self.last_referenced = datetime.now()
    
    def get_reference_weight(self, max_references: int = 100) -> float:
        """
        简化的引用计数权重计算
        
        Returns:
            float: 直接返回引用计数，不再做复杂的数学变换
        """
        return float(self.reference_count)
    
    def get_recency_weight(self, max_days: int = 365) -> float:
        """
        简化的新鲜度权重计算
        
        Returns:
            float: 简单地返回是否有最近引用：有为1.0，无为0.0
        """
        return 1.0 if self.last_referenced else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """将Solution对象转换为字典格式"""
        data = self.model_dump()
        # 确保datetime字段正确序列化
        if self.last_referenced:
            data['last_referenced'] = self.last_referenced.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Solution':
        """从字典创建Solution对象"""
        data_copy = data.copy()
        
        # 处理datetime字段的反序列化
        if 'last_referenced' in data_copy and data_copy['last_referenced']:
            if isinstance(data_copy['last_referenced'], str):
                data_copy['last_referenced'] = datetime.fromisoformat(data_copy['last_referenced'])
        
        # 确保向后兼容：为没有新字段的旧数据设置默认值
        if 'reference_count' not in data_copy:
            data_copy['reference_count'] = 0
        if 'last_referenced' not in data_copy:
            data_copy['last_referenced'] = None
        if 'tags' not in data_copy:
            data_copy['tags'] = []
            
        return cls(**data_copy)


class ConversationRecord(BaseModel):
    """
    对话记录数据模型
    
    存储完整的AI助手对话信息，包括内容、元数据、分类和提取的解决方案。
    支持自动生成摘要、标签分类和重要性评级。
    
    Attributes:
        id: 唯一标识符，格式为 conv_YYYYMMDD_NNN
        title: 对话主题标题
        content: 完整的对话内容
        summary: AI生成的对话摘要
        tags: 标签列表，用于分类和搜索
        category: 对话分类（problem-solving, learning, debugging等）
        importance: 重要程度，1-5级别，5最重要
        created_at: 创建时间戳
        updated_at: 最后更新时间戳
        solutions: 从对话中提取的解决方案列表
    """
    
    id: str = Field(default_factory=lambda: f"conv_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:3]}")
    title: str = Field(..., min_length=1, max_length=200, description="对话主题")
    content: str = Field(..., min_length=1, description="完整对话内容")
    summary: str = Field(default="", description="AI生成的摘要")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    category: str = Field(default="general", description="对话分类")
    importance: int = Field(default=3, ge=1, le=5, description="重要程度 1-5")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    solutions: List[Solution] = Field(default_factory=list, description="提取的解决方案")
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """
        验证和清理标签
        
        - 移除重复标签
        - 转换为小写
        - 移除空字符串
        - 限制标签长度
        """
        if not v:
            return []
        
        # 清理标签：去重、小写化、移除空白
        cleaned_tags = []
        seen = set()
        
        for tag in v:
            if isinstance(tag, str):
                clean_tag = tag.strip().lower()
                if clean_tag and len(clean_tag) <= 50 and clean_tag not in seen:
                    cleaned_tags.append(clean_tag)
                    seen.add(clean_tag)
        
        return cleaned_tags
    
    @field_validator('importance')
    @classmethod
    def validate_importance(cls, v):
        """验证重要性等级在1-5范围内"""
        if v < 1 or v > 5:
            raise ValueError('重要性等级必须在1-5之间')
        return v
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        """验证和标准化分类"""
        if not v or not isinstance(v, str):
            return "general"
        
        # 定义标准分类
        standard_categories = {
            "problem-solving": "问题解决",
            "learning": "学习",
            "debugging": "调试",
            "code-review": "代码审查",
            "architecture": "架构设计",
            "performance": "性能优化",
            "general": "一般对话"
        }
        
        clean_category = v.strip().lower()
        
        # 如果是标准分类，返回对应的中文名称
        if clean_category in standard_categories:
            return standard_categories[clean_category]
        
        # 否则返回清理后的分类
        return clean_category if len(clean_category) <= 50 else "general"
    
    def add_solution(self, solution: Solution) -> None:
        """
        向对话记录添加解决方案
        
        Args:
            solution: 要添加的解决方案对象
        """
        if solution not in self.solutions:
            self.solutions.append(solution)
            self.updated_at = datetime.now()
    
    def remove_solution(self, solution_id: str) -> bool:
        """
        从对话记录中移除解决方案
        
        Args:
            solution_id: 要移除的解决方案ID
            
        Returns:
            bool: 成功移除返回True，未找到返回False
        """
        for i, solution in enumerate(self.solutions):
            if solution.id == solution_id:
                self.solutions.pop(i)
                self.updated_at = datetime.now()
                return True
        return False
    
    def get_solution_by_id(self, solution_id: str) -> Optional[Solution]:
        """
        根据ID获取解决方案
        
        Args:
            solution_id: 解决方案ID
            
        Returns:
            Solution对象或None
        """
        for solution in self.solutions:
            if solution.id == solution_id:
                return solution
        return None
    
    def update_summary(self, new_summary: str) -> None:
        """
        更新对话摘要
        
        Args:
            new_summary: 新的摘要内容
        """
        if new_summary and isinstance(new_summary, str):
            self.summary = new_summary.strip()
            self.updated_at = datetime.now()
    
    def add_tags(self, new_tags: List[str]) -> None:
        """
        添加新标签（避免重复）
        
        Args:
            new_tags: 要添加的新标签列表
        """
        current_tags = set(self.tags)
        for tag in new_tags:
            if isinstance(tag, str):
                clean_tag = tag.strip().lower()
                if clean_tag and clean_tag not in current_tags:
                    self.tags.append(clean_tag)
                    current_tags.add(clean_tag)
        
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将ConversationRecord对象转换为字典格式
        
        用于JSON序列化和存储。
        处理datetime对象的序列化。
        
        Returns:
            Dict[str, Any]: 包含所有字段的字典
        """
        data = self.model_dump()
        
        # 处理datetime字段的序列化
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        
        # 处理solutions字段的序列化
        data['solutions'] = [solution.to_dict() for solution in self.solutions]
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationRecord':
        """
        从字典创建ConversationRecord对象
        
        用于从JSON数据反序列化。
        处理datetime字段的反序列化。
        
        Args:
            data: 包含对话记录数据的字典
            
        Returns:
            ConversationRecord: 创建的对话记录对象
        """
        # 复制数据以避免修改原始数据
        data_copy = data.copy()
        
        # 处理datetime字段的反序列化
        if 'created_at' in data_copy and isinstance(data_copy['created_at'], str):
            data_copy['created_at'] = datetime.fromisoformat(data_copy['created_at'])
        
        if 'updated_at' in data_copy and isinstance(data_copy['updated_at'], str):
            data_copy['updated_at'] = datetime.fromisoformat(data_copy['updated_at'])
        
        # 处理solutions字段的反序列化
        if 'solutions' in data_copy:
            solutions_data = data_copy['solutions']
            if isinstance(solutions_data, list):
                data_copy['solutions'] = [
                    Solution.from_dict(sol_data) if isinstance(sol_data, dict) else sol_data
                    for sol_data in solutions_data
                ]
        
        return cls(**data_copy)
    
    def to_json(self, indent: int = 2) -> str:
        """
        将对话记录转换为JSON字符串
        
        Args:
            indent: JSON缩进级别
            
        Returns:
            str: JSON格式的字符串
        """
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ConversationRecord':
        """
        从JSON字符串创建ConversationRecord对象
        
        Args:
            json_str: JSON格式的字符串
            
        Returns:
            ConversationRecord: 创建的对话记录对象
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_search_keywords(self) -> List[str]:
        """
        获取用于搜索的关键词列表
        
        从标题、标签和摘要中提取关键词，用于搜索索引。
        
        Returns:
            List[str]: 关键词列表
        """
        keywords = []
        
        # 添加标题中的关键词（分词）
        if self.title:
            title_words = self.title.lower().split()
            keywords.extend(title_words)
        
        # 添加所有标签
        keywords.extend(self.tags)
        
        # 添加摘要中的关键词（取前10个词）
        if self.summary:
            summary_words = self.summary.lower().split()[:10]
            keywords.extend(summary_words)
        
        # 去重并过滤空字符串
        return list(set(word.strip() for word in keywords if word.strip()))
    
    def __str__(self) -> str:
        """返回对话记录的字符串表示"""
        return f"ConversationRecord(id='{self.id}', title='{self.title}', solutions={len(self.solutions)})"
    
    def __repr__(self) -> str:
        """返回对话记录的详细字符串表示"""
        return (f"ConversationRecord(id='{self.id}', title='{self.title}', "
                f"category='{self.category}', importance={self.importance}, "
                f"tags={len(self.tags)}, solutions={len(self.solutions)})")


# 导出的工具函数
def create_conversation_record(
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    category: str = "general",
    importance: int = 3
) -> ConversationRecord:
    """
    创建对话记录的便利函数
    
    Args:
        title: 对话标题
        content: 对话内容
        tags: 标签列表
        category: 分类
        importance: 重要性
        
    Returns:
        ConversationRecord: 创建的对话记录
    """
    return ConversationRecord(
        title=title,
        content=content,
        tags=tags or [],
        category=category,
        importance=importance
    )


def create_solution(
    solution_type: Literal["code", "approach", "pattern"],
    content: str,
    description: str,
    language: Optional[str] = None,
    tags: Optional[List[str]] = None,
    reusability_score: float = 0.5
) -> Solution:
    """
    创建解决方案的便利函数
    
    Args:
        solution_type: 解决方案类型
        content: 内容
        description: 描述
        language: 编程语言（代码类型时必需）
        tags: 标签列表，用于分类和搜索
        reusability_score: 可重用性评分
        
    Returns:
        Solution: 创建的解决方案
    """
    return Solution(
        type=solution_type,
        content=content,
        description=description,
        language=language,
        tags=tags or [],
        reusability_score=reusability_score
    )