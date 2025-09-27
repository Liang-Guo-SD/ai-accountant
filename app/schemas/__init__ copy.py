"""
AI会计师 - 数据结构定义
使用Pydantic定义所有数据结构，确保类型安全
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    """文档类型枚举"""
    SALES_INVOICE = "销售发票"
    PURCHASE_INVOICE = "采购发票"
    RECEIPT = "收据"
    OTHER = "其他"


class BusinessType(str, Enum):
    """业务类型枚举"""
    SALES_INCOME = "销售收款"
    PURCHASE_PAYMENT = "采购付款"
    EXPENSE_PAYMENT = "费用支付"
    ASSET_PURCHASE = "资产购买"
    CAPITAL_TRANSACTION = "资金往来"


class PaymentMethod(str, Enum):
    """支付方式枚举"""
    CASH = "现金收付"
    BANK_TRANSFER = "银行转账"
    ACCOUNTS_RECEIVABLE = "应收应付"


class ProcessingStatus(str, Enum):
    """处理状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


# ================================
# 发票相关数据结构
# ================================

class ExtractedInvoiceInfo(BaseModel):
    """从发票中提取的标准化信息"""
    
    # 基本信息
    document_type: Optional[DocumentType] = Field(None, description="单据类型")
    invoice_number: Optional[str] = Field(None, description="发票号码")
    invoice_date: Optional[str] = Field(None, description="开票日期，格式：YYYY-MM-DD")
    
    # 交易双方
    seller_name: Optional[str] = Field(None, description="销售方/开票方名称")
    buyer_name: Optional[str] = Field(None, description="购买方/受票方名称")
    
    # 金额信息
    amount_before_tax: Optional[float] = Field(None, description="不含税金额")
    tax_amount: Optional[float] = Field(None, description="税额")
    total_amount: Optional[float] = Field(None, description="价税合计/总金额")
    
    # 商品信息
    goods_description: Optional[str] = Field(None, description="货物或服务描述")
    
    # AI分析结果
    business_analysis: Optional[str] = Field(None, description="AI对这笔业务的分析和理解")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="AI提取信息的置信度")
    
    # 处理时间戳
    processed_at: datetime = Field(default_factory=datetime.now, description="处理时间")


# ================================
# 业务标准化数据结构
# ================================

class StandardizedBusiness(BaseModel):
    """标准化业务描述"""
    
    # 核心业务要素
    business_type: BusinessType = Field(description="业务类型分类")
    payment_method: PaymentMethod = Field(description="支付方式")
    business_nature: str = Field(description="业务性质描述")
    amount_info: str = Field(description="金额详细信息")
    
    # 标准化描述
    standardized_description: str = Field(description="标准化的业务描述，使用会计术语")
    key_elements: List[str] = Field(description="关键业务要素列表")
    
    # 检索优化
    search_keywords: List[str] = Field(description="用于RAG检索的关键词")
    confidence_level: float = Field(ge=0.0, le=1.0, description="标准化的置信度")
    
    # 处理时间戳
    processed_at: datetime = Field(default_factory=datetime.now, description="处理时间")


# ================================
# 会计分录数据结构
# ================================

class JournalEntry(BaseModel):
    """会计分录数据结构"""
    
    # 基本信息
    business_description: str = Field(description="业务描述")
    entry_date: str = Field(description="分录日期，格式YYYY-MM-DD")
    
    # 分录明细（简化版：单借单贷）
    debit_account_code: str = Field(description="借方科目编码")
    debit_account_name: str = Field(description="借方科目名称")
    credit_account_code: str = Field(description="贷方科目编码")
    credit_account_name: str = Field(description="贷方科目名称")
    amount: float = Field(gt=0, description="金额")
    
    # AI分析过程
    analysis_process: str = Field(description="AI的分析推理过程")
    applied_rules: str = Field(description="应用的会计准则")
    confidence_score: float = Field(ge=0.0, le=1.0, description="置信度评分")
    
    # 验证信息
    is_balanced: bool = Field(True, description="借贷是否平衡")
    validation_notes: str = Field(description="验证说明")
    needs_review: bool = Field(description="是否需要人工审核")
    
    # 处理时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


# ================================
# 文档处理结果数据结构
# ================================

class DocumentProcessingResult(BaseModel):
    """文档处理结果"""
    
    # 文件信息
    file_name: str = Field(description="文件名")
    file_path: str = Field(description="文件路径")
    file_size: int = Field(description="文件大小（字节）")
    page_count: Optional[int] = Field(None, description="页数（PDF文件）")
    
    # 原始内容
    raw_text: str = Field(description="提取的原始文本")
    
    # 处理结果
    extracted_info: Optional[ExtractedInvoiceInfo] = Field(None, description="提取的发票信息")
    standardized_business: Optional[StandardizedBusiness] = Field(None, description="标准化业务描述")
    journal_entry: Optional[JournalEntry] = Field(None, description="生成的会计分录")
    
    # 状态信息
    processing_status: ProcessingStatus = Field(description="处理状态")
    error_message: Optional[str] = Field(None, description="错误信息")
    final_confidence: float = Field(0.0, ge=0.0, le=1.0, description="最终置信度")
    
    # 审核信息
    needs_review: bool = Field(description="是否需要人工审核")
    review_notes: Optional[str] = Field(None, description="审核备注")
    
    # 时间戳
    processed_at: datetime = Field(default_factory=datetime.now, description="处理完成时间")
    processing_time: Optional[float] = Field(None, description="处理耗时（秒）")


# ================================
# 知识检索结果数据结构
# ================================

class KnowledgeSearchResult(BaseModel):
    """知识检索结果"""
    
    content: str = Field(description="检索到的内容")
    relevance_score: float = Field(ge=0.0, le=1.0, description="相关性评分")
    source: str = Field(description="来源标识")
    metadata: dict = Field(default_factory=dict, description="元数据")


# ================================
# 系统统计数据结构
# ================================

class ProcessingStats(BaseModel):
    """处理统计信息"""
    
    total_processed: int = Field(0, description="总处理数量")
    success_count: int = Field(0, description="成功数量")
    failed_count: int = Field(0, description="失败数量")
    high_confidence_count: int = Field(0, description="高置信度数量")
    needs_review_count: int = Field(0, description="需要审核数量")
    average_confidence: float = Field(0.0, description="平均置信度")
    average_processing_time: float = Field(0.0, description="平均处理时间")
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.success_count / self.total_processed if self.total_processed > 0 else 0.0
    
    @property
    def high_quality_rate(self) -> float:
        """高质量率"""
        return self.high_confidence_count / self.total_processed if self.total_processed > 0 else 0.0


# ================================
# 导出所有数据结构
# ================================

__all__ = [
    # 枚举类型
    "DocumentType",
    "BusinessType", 
    "PaymentMethod",
    "ProcessingStatus",
    
    # 核心数据结构
    "ExtractedInvoiceInfo",
    "StandardizedBusiness",
    "JournalEntry",
    "DocumentProcessingResult",
    "KnowledgeSearchResult",
    "ProcessingStats",
]