"""
AI会计师 FastAPI 后端服务
提供RESTful API接口，支持文件处理、凭证管理等功能
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import List, Optional
import logging
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.api.schemas import (
    ProcessingRequest,
    ProcessingResponse,
    JournalEntryResponse,
    JournalApprovalRequest,
    BatchProcessingRequest,
    SystemStatus,
    ErrorResponse
)
from app.api.dependencies import get_db, get_processor, get_current_user
from app.services.document_processor import DocumentProcessor
from app.database import init_database
from app.core.config import get_config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 获取配置
config = get_config()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时初始化，关闭时清理资源
    """
    # 启动时
    logger.info("🚀 启动AI会计师API服务...")
    
    # 初始化数据库
    try:
        init_database()
        logger.info("✅ 数据库初始化成功")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
    
    # 预热AI模型
    try:
        processor = DocumentProcessor()
        logger.info("✅ AI服务预热完成")
    except Exception as e:
        logger.warning(f"⚠️ AI服务预热失败: {e}")
    
    yield
    
    # 关闭时
    logger.info("👋 关闭API服务...")

# 创建FastAPI应用
app = FastAPI(
    title="AI会计师 API",
    description="智能财务凭证处理系统，支持复合分录",
    version="2.0.0",
    lifespan=lifespan
)

# 配置CORS（允许跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 健康检查接口 ====================

@app.get("/", tags=["Health"])
async def root():
    """API根路径，返回系统信息"""
    return {
        "name": "AI会计师 API",
        "version": "2.0.0",
        "status": "运行中",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=SystemStatus, tags=["Health"])
async def health_check():
    """
    系统健康检查
    检查各个组件的运行状态
    """
    status = SystemStatus(
        status="healthy",
        database="connected",
        ai_service="ready",
        rag_service="ready",
        version="2.0.0"
    )
    
    # 检查数据库连接
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        status.database = "connected"
    except Exception as e:
        status.database = f"error: {str(e)}"
        status.status = "degraded"
    
    return status

# ==================== 文件处理接口 ====================

@app.post("/api/v1/process", response_model=ProcessingResponse, tags=["Processing"])
async def process_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    entry_date: Optional[str] = None,
    allow_complex: bool = True,
    processor: DocumentProcessor = Depends(get_processor)
):
    """
    处理单个文档
    
    - **file**: 要处理的文件（PDF, Excel等）
    - **entry_date**: 凭证日期（可选，格式：YYYY-MM-DD）
    - **allow_complex**: 是否允许生成复合分录
    """
    # 验证文件类型
    allowed_extensions = ['.pdf', '.xlsx', '.xls']
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(allowed_extensions)}"
        )
    
    # 保存上传的文件
    upload_dir = Path(config.app.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / file.filename
    try:
        contents = await file.read()
        with open(file_path, 'wb') as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
    
    # 处理文档
    try:
        result = processor.process_document(file_path, entry_date)
        
        # 构建响应
        response = ProcessingResponse(
            file_name=result.file_name,
            status=result.processing_status.value,
            confidence=result.final_confidence,
            needs_review=result.needs_review,
            processing_time=result.processing_time,
            journal_entry=None
        )
        
        # 如果有生成凭证，添加到响应中
        if result.journal_entry:
            response.journal_entry = JournalEntryResponse.from_journal_entry(result.journal_entry)
        
        # 如果需要审核，添加到后台任务队列
        if result.needs_review:
            background_tasks.add_task(
                log_pending_review,
                file_name=result.file_name,
                confidence=result.final_confidence
            )
        
        return response
        
    except Exception as e:
        logger.error(f"处理文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

@app.post("/api/v1/process/batch", response_model=List[ProcessingResponse], tags=["Processing"])
async def process_batch(
    request: BatchProcessingRequest,
    background_tasks: BackgroundTasks,
    processor: DocumentProcessor = Depends(get_processor)
):
    """
    批量处理多个文档
    
    支持一次性处理多个文件，返回所有处理结果
    """
    results = []
    
    for file_path in request.file_paths:
        try:
            result = processor.process_document(file_path, request.entry_date)
            
            response = ProcessingResponse(
                file_name=Path(file_path).name,
                status=result.processing_status.value,
                confidence=result.final_confidence,
                needs_review=result.needs_review,
                processing_time=result.processing_time,
                journal_entry=None
            )
            
            if result.journal_entry:
                response.journal_entry = JournalEntryResponse.from_journal_entry(result.journal_entry)
            
            results.append(response)
            
        except Exception as e:
            logger.error(f"处理文件 {file_path} 失败: {str(e)}")
            results.append(ProcessingResponse(
                file_name=Path(file_path).name,
                status="failed",
                confidence=0.0,
                needs_review=True,
                processing_time=0.0,
                error_message=str(e)
            ))
    
    return results

# ==================== 凭证管理接口 ====================

@app.get("/api/v1/journals/pending", response_model=List[JournalEntryResponse], tags=["Journals"])
async def get_pending_journals(
    skip: int = 0,
    limit: int = 100,
    db=Depends(get_db)
):
    """
    获取待审核的凭证列表
    
    - **skip**: 跳过的记录数
    - **limit**: 返回的最大记录数
    """
    # 这里需要实现从数据库查询待审核凭证的逻辑
    # 暂时返回模拟数据
    return []

@app.post("/api/v1/journals/{journal_id}/approve", tags=["Journals"])
async def approve_journal(
    journal_id: int,
    request: JournalApprovalRequest,
    db=Depends(get_db)
):
    """
    批准凭证
    
    将凭证状态从待审核改为已批准
    """
    # 这里需要实现更新凭证状态的逻辑
    return {"message": f"凭证 {journal_id} 已批准", "approved_by": request.approved_by}

@app.post("/api/v1/journals/{journal_id}/reject", tags=["Journals"])
async def reject_journal(
    journal_id: int,
    reason: str,
    db=Depends(get_db)
):
    """
    拒绝凭证
    
    将凭证标记为需要重新处理
    """
    return {"message": f"凭证 {journal_id} 已拒绝", "reason": reason}

# ==================== 错误处理 ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """统一的HTTP异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            status_code=exc.status_code,
            path=str(request.url)
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """统一的通用异常处理"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="服务器内部错误",
            status_code=500,
            path=str(request.url)
        ).dict()
    )

# ==================== 辅助函数 ====================

async def log_pending_review(file_name: str, confidence: float):
    """记录需要审核的文件（后台任务）"""
    logger.info(f"📋 文件 {file_name} 需要人工审核，置信度: {confidence:.2%}")

if __name__ == "__main__":
    import uvicorn
    
    # 开发环境配置
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )