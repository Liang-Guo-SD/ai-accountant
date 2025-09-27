"""
FastAPI Pydantic 数据模型
用于API请求和响应的数据验证
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    """处理状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    PROCESSING = "processing"


class EntryLineSchema(BaseModel):
    """分录明细行数据模型"""
    account_code: str = Field(..., description="科目编码")
    account_name: str = Field(..., description="科目名称")
    direction: str = Field(..., description="借贷方向", pattern="^(借|贷|DEBIT|CREDIT)$")
    amount: float = Field(..., gt=0, description="金额")
    description: Optional[str] = Field(None, description="摘要")
    
    class Config:
        schema_extra = {
            "example": {
                "account_code": "1001",
                "account_name": "库存现金",
                "direction": "借",
                "amount": 1000.00,
                "description": "收到货款"
            }
        }


class JournalEntryResponse(BaseModel):
    """凭证响应模型"""
    id: Optional[int] = Field(None, description="凭证ID")
    business_description: str = Field(..., description="业务描述")
    entry_date: str = Field(..., description="凭证日期")
    voucher_number: Optional[str] = Field(None, description="凭证号")
    entry_lines: List[EntryLineSchema] = Field(..., description="分录明细")
    total_debit: float = Field(..., description="借方合计")
    total_credit: float = Field(..., description="贷方合计")
    is_balanced: bool = Field(..., description="是否平衡")
    confidence_score: float = Field(..., ge=0, le=1, description="置信度")
    status: str = Field("pending", description="状态")
    needs_review: bool = Field(..., description="需要审核")
    
    @validator('is_balanced', always=True)
    def check_balance(cls, v, values):
        """验证借贷平衡"""
        if 'total_debit' in values and 'total_credit' in values:
            return abs(values['total_debit'] - values['total_credit']) < 0.01
        return v
    
    @classmethod
    def from_journal_entry(cls, entry):
        """从JournalEntry对象创建响应模型"""
        entry_lines = []
        for line in entry.entry_lines:
            entry_lines.append(EntryLineSchema(
                account_code=line.account_code,
                account_name=line.account_name,
                direction=line.direction.value,
                amount=line.amount,
                description=line.description
            ))
        
        return cls(
            business_description=entry.business_description,
            entry_date=entry.entry_date,
            voucher_number=getattr(entry, 'voucher_number', None),
            entry_lines=entry_lines,
            total_debit=entry.total_debit,
            total_credit=entry.total_credit,
            is_balanced=entry.is_balanced,
            confidence_score=entry.confidence_score,
            needs_review=entry.needs_review
        )
    
    class Config:
        schema_extra = {
            "example": {
                "business_description": "收到客户货款",
                "entry_date": "2024-03-20",
                "entry_lines": [
                    {
                        "account_code": "1002",
                        "account_name": "银行存款",
                        "direction": "借",
                        "amount": 11300.00
                    },
                    {
                        "account_code": "6001",
                        "account_name": "主营业务收入",
                        "direction": "贷",
                        "amount": 10000.00
                    },
                    {
                        "account_code": "2221",
                        "account_name": "应交税费-增值税",
                        "direction": "贷",
                        "amount": 1300.00
                    }
                ],
                "total_debit": 11300.00,
                "total_credit": 11300.00,
                "is_balanced": True,
                "confidence_score": 0.95,
                "needs_review": False
            }
        }


class ProcessingRequest(BaseModel):
    """文档处理请求模型"""
    file_path: str = Field(..., description="文件路径")
    entry_date: Optional[str] = Field(None, description="凭证日期", pattern="^\d{4}-\d{2}-\d{2}$")
    allow_complex: bool = Field(True, description="允许生成复合分录")
    
    class Config:
        schema_extra = {
            "example": {
                "file_path": "/uploads/invoice_001.pdf",
                "entry_date": "2024-03-20",
                "allow_complex": True
            }
        }


class ProcessingResponse(BaseModel):
    """文档处理响应模型"""
    file_name: str = Field(..., description="文件名")
    status: str = Field(..., description="处理状态")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    needs_review: bool = Field(..., description="需要审核")
    processing_time: float = Field(..., description="处理时间（秒）")
    journal_entry: Optional[JournalEntryResponse] = Field(None, description="生成的凭证")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    class Config:
        schema_extra = {
            "example": {
                "file_name": "invoice_001.pdf",
                "status": "success",
                "confidence": 0.92,
                "needs_review": False,
                "processing_time": 3.45
            }
        }


class BatchProcessingRequest(BaseModel):
    """批量处理请求模型"""
    file_paths: List[str] = Field(..., description="文件路径列表")
    entry_date: Optional[str] = Field(None, description="统一凭证日期")
    allow_complex: bool = Field(True, description="允许生成复合分录")
    
    class Config:
        schema_extra = {
            "example": {
                "file_paths": [
                    "/uploads/invoice_001.pdf",
                    "/uploads/invoice_002.pdf",
                    "/uploads/receipt_003.pdf"
                ],
                "entry_date": "2024-03-20",
                "allow_complex": True
            }
        }


class JournalApprovalRequest(BaseModel):
    """凭证批准请求模型"""
    approved_by: str = Field(..., description="批准人")
    approval_notes: Optional[str] = Field(None, description="批准备注")
    
    class Config:
        schema_extra = {
            "example": {
                "approved_by": "张会计",
                "approval_notes": "已核对原始凭证，无误"
            }
        }


class SystemStatus(BaseModel):
    """系统状态模型"""
    status: str = Field(..., description="系统状态")
    database: str = Field(..., description="数据库状态")
    ai_service: str = Field(..., description="AI服务状态")
    rag_service: str = Field(..., description="RAG服务状态")
    version: str = Field(..., description="系统版本")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "database": "connected",
                "ai_service": "ready",
                "rag_service": "ready",
                "version": "2.0.0",
                "timestamp": "2024-03-20T10:30:00"
            }
        }


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误信息")
    status_code: int = Field(..., description="HTTP状态码")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    path: Optional[str] = Field(None, description="请求路径")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "文件类型不支持",
                "status_code": 400,
                "timestamp": "2024-03-20T10:30:00",
                "path": "/api/v1/process"
            }
        }


class PaginationParams(BaseModel):
    """分页参数模型"""
    skip: int = Field(0, ge=0, description="跳过记录数")
    limit: int = Field(100, ge=1, le=1000, description="返回记录数")
    
    class Config:
        schema_extra = {
            "example": {
                "skip": 0,
                "limit": 20
            }
        }