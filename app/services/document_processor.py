"""
AI会计师 - 统一文档处理服务
整合所有文档处理流程，提供一站式服务
"""

import time
from pathlib import Path
from typing import Union, Optional
import logging

from app.core.config import get_config
from app.schemas import (
    DocumentProcessingResult, 
    ExtractedInvoiceInfo,
    ProcessingStatus
)
from app.utils.file_parser import FileParser
from app.services.ai_service import AIExtractionService
from app.services.business_standardizer import BusinessStandardizerService
from app.services.rag_service import AccountingRAGService
from app.services.journal_generator import JournalGenerationService

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    统一文档处理器
    负责协调整个处理流水线
    """
    
    def __init__(self):
        """初始化文档处理器"""
        self.config = get_config()
        
        # 初始化各个服务组件
        self.file_parser = FileParser()
        self.invoice_extractor = AIExtractionService()
        self.business_analyzer = BusinessStandardizerService()
        self.knowledge_retriever = AccountingRAGService()
        self.journal_generator = JournalGenerationService()
        
        logger.info("📋 统一文档处理器初始化完成")
    
    def process_document(self, file_path: Union[str, Path], 
                        entry_date: Optional[str] = None) -> DocumentProcessingResult:
        """
        处理单个文档的完整流程
        
        Args:
            file_path: 文档文件路径
            entry_date: 会计分录日期
            
        Returns:
            DocumentProcessingResult: 完整的处理结果
        """
        start_time = time.time()
        file_path = Path(file_path)
        
        try:
            logger.info(f"🚀 开始处理文档: {file_path.name}")
            
            # 第一阶段：文件解析
            logger.info("📄 阶段1: 解析文件内容...")
            file_info = self.file_parser.parse_file(file_path)
            
            if not file_info['success']:
                return self._create_failed_result(
                    file_path, f"文件解析失败: {file_info.get('error', '未知错误')}"
                )
            
            # 第二阶段：AI信息提取
            logger.info("🤖 阶段2: AI信息提取...")
            extracted_info = self.invoice_extractor.extract_invoice_info(
                file_info['raw_text']
            )
            
            if extracted_info.confidence_score < 0.3:
                logger.warning("⚠️ AI信息提取置信度过低")
            
            # 第三阶段：业务标准化
            logger.info("📊 阶段3: 业务标准化分析...")
            standardized_business = self.business_analyzer.standardize_business(
                extracted_info
            )
            
            # 第四阶段：知识检索
            logger.info("🔍 阶段4: 知识检索...")
            relevant_rules = self.knowledge_retriever.search_relevant_rules(
                standardized_business.standardized_description
            )
            
            # 第五阶段：生成会计分录
            logger.info("⚙️ 阶段5: 生成会计分录...")
            journal_entry = self.journal_generator.generate_journal_entry(
                business_description=standardized_business.standardized_description,
                amount=extracted_info.total_amount or 0.0,
                entry_date=entry_date
            )
            
            # 计算最终置信度
            final_confidence = self._calculate_final_confidence(
                extracted_info, standardized_business, journal_entry
            )
            
            # 判断是否需要审核
            needs_review = self._determine_review_requirement(final_confidence, journal_entry)
            
            processing_time = time.time() - start_time
            
            # 统一为字典以匹配 app.schemas 下的目标模型
            std_business_payload = (
                standardized_business.model_dump() if hasattr(standardized_business, "model_dump") else standardized_business
            )
            journal_entry_payload = (
                journal_entry.model_dump() if hasattr(journal_entry, "model_dump") else journal_entry
            )

            # 构建成功结果
            result = DocumentProcessingResult(
                file_name=file_path.name,
                file_path=str(file_path),
                file_size=file_info['file_size'],
                page_count=file_info.get('page_count'),
                raw_text=file_info['raw_text'],
                extracted_info=extracted_info,
                standardized_business=std_business_payload,
                journal_entry=journal_entry_payload,
                processing_status=ProcessingStatus.SUCCESS,
                final_confidence=final_confidence,
                needs_review=needs_review,
                processing_time=processing_time
            )
            
            logger.info(f"✅ 文档处理完成: {file_path.name}, 置信度: {final_confidence:.3f}")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ 文档处理失败: {str(e)}")
            return self._create_failed_result(file_path, str(e), processing_time)
    
    def _calculate_final_confidence(self, extracted_info: ExtractedInvoiceInfo,
                                   standardized_business, journal_entry) -> float:
        """计算最终置信度"""
        confidences = [
            extracted_info.confidence_score,
            standardized_business.confidence_level,
            journal_entry.confidence_score
        ]
        
        # 使用加权平均，会计分录生成的置信度权重最高
        weights = [0.2, 0.3, 0.5]
        final_confidence = sum(c * w for c, w in zip(confidences, weights))
        
        return round(final_confidence, 3)
    
    def _determine_review_requirement(self, confidence: float, journal_entry) -> bool:
        """判断是否需要人工审核"""
        if confidence < self.config.app.confidence_threshold_medium:
            return True
        
        if journal_entry and not journal_entry.is_balanced:
            return True
        
        if journal_entry and "错误" in journal_entry.validation_notes:
            return True
        
        return False
    
    def _create_failed_result(self, file_path: Path, error_message: str, 
                             processing_time: float = 0) -> DocumentProcessingResult:
        """创建失败结果"""
        return DocumentProcessingResult(
            file_name=file_path.name,
            file_path=str(file_path),
            file_size=file_path.stat().st_size if file_path.exists() else 0,
            raw_text="",
            processing_status=ProcessingStatus.FAILED,
            error_message=error_message,
            final_confidence=0.0,
            needs_review=True,
            processing_time=processing_time
        )
    
    def process_batch(self, file_paths: list, entry_date: Optional[str] = None) -> list:
        """
        批量处理多个文档
        
        Args:
            file_paths: 文档文件路径列表
            entry_date: 统一的会计分录日期
            
        Returns:
            list: 处理结果列表
        """
        logger.info(f"📦 开始批量处理 {len(file_paths)} 个文档")
        
        results = []
        for i, file_path in enumerate(file_paths, 1):
            logger.info(f"处理进度: {i}/{len(file_paths)}")
            result = self.process_document(file_path, entry_date)
            results.append(result)
        
        # 统计处理结果
        success_count = sum(1 for r in results if r.processing_status == ProcessingStatus.SUCCESS)
        logger.info(f"📊 批量处理完成: 成功 {success_count}/{len(file_paths)} 个文档")
        
        return results


class DocumentProcessorFactory:
    """文档处理器工厂类"""
    
    _instance: Optional[DocumentProcessor] = None
    
    @classmethod
    def get_processor(cls) -> DocumentProcessor:
        """获取文档处理器实例（单例模式）"""
        if cls._instance is None:
            cls._instance = DocumentProcessor()
        return cls._instance
    
    @classmethod
    def create_processor(cls) -> DocumentProcessor:
        """创建新的文档处理器实例"""
        return DocumentProcessor()


# 便捷函数
def process_single_document(file_path: Union[str, Path], 
                           entry_date: Optional[str] = None) -> DocumentProcessingResult:
    """处理单个文档的便捷函数"""
    processor = DocumentProcessorFactory.get_processor()
    return processor.process_document(file_path, entry_date)


def process_multiple_documents(file_paths: list, 
                              entry_date: Optional[str] = None) -> list:
    """批量处理文档的便捷函数"""
    processor = DocumentProcessorFactory.get_processor()
    return processor.process_batch(file_paths, entry_date)


# 测试函数
def test_document_processor():
    """测试文档处理器"""
    print("🧪 测试统一文档处理器")
    print("=" * 60)
    
    try:
        processor = DocumentProcessor()
        
        # 模拟测试（因为没有真实PDF文件）
        print("📄 模拟文档处理测试...")
        
        # 这里可以放置真实的PDF文件路径进行测试
        # result = processor.process_document("path/to/your/invoice.pdf")
        
        print("✅ 文档处理器初始化成功")
        print(f"📊 配置信息:")
        print(f"   - 高置信度阈值: {processor.config.app.confidence_threshold_high}")
        print(f"   - 中等置信度阈值: {processor.config.app.confidence_threshold_medium}")
        print(f"   - 支持的文件格式: {processor.config.app.supported_formats}")
        
        # 提示如何使用
        print("\n💡 使用方法:")
        print("1. processor.process_document('path/to/invoice.pdf')")
        print("2. process_single_document('path/to/invoice.pdf')  # 便捷函数")
        print("3. process_multiple_documents([file1, file2, ...])  # 批量处理")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_document_processor()