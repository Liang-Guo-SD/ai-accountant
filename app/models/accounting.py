"""
会计数据模型
定义会计科目、凭证等核心数据结构
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, Text, Boolean
from datetime import datetime
from app.database import Base


class Account(Base):
    """
    会计科目表
    这是会计系统的基础，定义了所有可用的会计科目
    """
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, index=True, nullable=False, comment="科目编码，如1001")
    name = Column(String(100), nullable=False, comment="科目名称，如库存现金")
    category = Column(String(20), nullable=False, comment="科目类别：资产/负债/权益/收入/费用")
    parent_code = Column(String(10), nullable=True, comment="上级科目编码")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Account(code='{self.code}', name='{self.name}')>"
    
    @property 
    def full_name(self):
        """返回完整的科目名称：编码 + 名称"""
        return f"{self.code} {self.name}"