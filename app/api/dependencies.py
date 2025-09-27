"""
FastAPI 依赖注入
提供数据库会话、服务实例等依赖项
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from app.database import SessionLocal
from app.services.document_processor import DocumentProcessor
from app.services.journal_generator_enhanced import EnhancedJournalGenerationService
from app.services.rag_service import AccountingRAGService
from app.core.config import get_config

logger = logging.getLogger(__name__)

# 安全认证（可选）
security = HTTPBearer(auto_error=False)

# 单例服务实例（避免重复初始化）
_document_processor: Optional[DocumentProcessor] = None
_journal_generator: Optional[EnhancedJournalGenerationService] = None
_rag_service: Optional[AccountingRAGService] = None


def get_db() -> Generator:
    """
    获取数据库会话
    使用yield确保会话在请求结束后正确关闭
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_processor() -> DocumentProcessor:
    """
    获取文档处理器实例（单例模式）
    避免每次请求都重新初始化AI服务
    """
    global _document_processor
    
    if _document_processor is None:
        logger.info("初始化文档处理器...")
        _document_processor = DocumentProcessor()
    
    return _document_processor


def get_journal_generator() -> EnhancedJournalGenerationService:
    """
    获取凭证生成器实例（单例模式）
    """
    global _journal_generator
    
    if _journal_generator is None:
        logger.info("初始化凭证生成器...")
        _journal_generator = EnhancedJournalGenerationService()
    
    return _journal_generator


def get_rag_service() -> AccountingRAGService:
    """
    获取RAG服务实例（单例模式）
    """
    global _rag_service
    
    if _rag_service is None:
        logger.info("初始化RAG服务...")
        _rag_service = AccountingRAGService()
        # 预加载知识库索引
        if not _rag_service.load_and_index_rules():
            logger.warning("RAG服务索引建立失败")
    
    return _rag_service


def get_config_instance():
    """获取配置实例"""
    return get_config()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[dict]:
    """
    获取当前用户（简化版，实际应该验证JWT token）
    
    在生产环境中，这里应该：
    1. 验证JWT token的有效性
    2. 从token中提取用户信息
    3. 检查用户权限
    """
    if not credentials:
        # 如果没有提供认证信息，返回匿名用户
        return {"username": "anonymous", "role": "guest"}
    
    # 简化实现：直接从token中提取用户名
    # 实际应该验证token并解析
    token = credentials.credentials
    
    # 模拟token验证（实际应该用JWT库）
    if token == "demo_token":
        return {"username": "demo_user", "role": "user"}
    elif token == "admin_token":
        return {"username": "admin", "role": "admin"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    需要管理员权限
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


class PaginationDep:
    """
    分页依赖类
    提供统一的分页参数处理
    """
    def __init__(self, skip: int = 0, limit: int = 100):
        self.skip = max(0, skip)
        self.limit = min(max(1, limit), 1000)  # 限制最大返回1000条
    
    @property
    def offset(self) -> int:
        """获取偏移量（与skip相同）"""
        return self.skip
    
    def paginate(self, query):
        """
        应用分页到SQLAlchemy查询
        """
        return query.offset(self.skip).limit(self.limit)


def get_pagination(skip: int = 0, limit: int = 100) -> PaginationDep:
    """获取分页参数"""
    return PaginationDep(skip=skip, limit=limit)


# 清理函数（用于测试或应用关闭时）
def cleanup_services():
    """
    清理所有单例服务实例
    主要用于测试环境
    """
    global _document_processor, _journal_generator, _rag_service
    
    _document_processor = None
    _journal_generator = None
    _rag_service = None
    
    logger.info("已清理所有服务实例")