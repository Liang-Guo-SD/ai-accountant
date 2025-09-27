"""
文件解析器
支持多种格式的文档解析，包括PDF、Excel等
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pandas as pd
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

logger = logging.getLogger(__name__)


class FileParser:
    """统一文件解析器"""
    
    def __init__(self):
        """初始化文件解析器"""
        self.supported_formats = {
            '.pdf': self._parse_pdf,
            '.xlsx': self._parse_excel,
            '.xls': self._parse_excel,
        }
        
        logger.info("📄 文件解析器初始化完成")
        logger.info(f"支持格式: {list(self.supported_formats.keys())}")
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        解析文件并提取文本内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict: 解析结果，包含success、raw_text、file_size等信息
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {
                'success': False,
                'error': f'文件不存在: {file_path}',
                'raw_text': '',
                'file_size': 0
            }
        
        # 检查文件格式
        file_extension = file_path.suffix.lower()
        if file_extension not in self.supported_formats:
            return {
                'success': False,
                'error': f'不支持的文件格式: {file_extension}',
                'raw_text': '',
                'file_size': file_path.stat().st_size
            }
        
        try:
            logger.info(f"🔍 开始解析文件: {file_path.name}")
            
            # 获取文件大小
            file_size = file_path.stat().st_size
            
            # 调用对应的解析方法
            parser_func = self.supported_formats[file_extension]
            result = parser_func(file_path)
            
            # 添加通用信息
            result['file_size'] = file_size
            result['file_extension'] = file_extension
            
            logger.info(f"✅ 文件解析完成: {file_path.name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 文件解析失败: {file_path.name}, 错误: {e}")
            return {
                'success': False,
                'error': f'解析失败: {str(e)}',
                'raw_text': '',
                'file_size': file_path.stat().st_size,
                'file_extension': file_extension
            }
    
    def _parse_pdf(self, file_path: Path) -> Dict[str, Any]:
        """解析PDF文件"""
        if not PDF_AVAILABLE:
            return {
                'success': False,
                'error': 'pdfplumber未安装，无法解析PDF文件',
                'raw_text': ''
            }
        
        try:
            text_content = []
            page_count = 0
            
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                logger.info(f"📄 PDF页数: {page_count}")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_content.append(f"=== 第{page_num}页 ===\n{page_text}\n")
                        else:
                            logger.warning(f"第{page_num}页无法提取文本")
                    except Exception as e:
                        logger.warning(f"第{page_num}页解析失败: {e}")
                        continue
            
            raw_text = '\n'.join(text_content)
            
            if not raw_text.strip():
                return {
                    'success': False,
                    'error': 'PDF文件中未找到可提取的文本内容',
                    'raw_text': '',
                    'page_count': page_count
                }
            
            return {
                'success': True,
                'raw_text': raw_text.strip(),
                'page_count': page_count,
                'parser_type': 'pdfplumber'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'PDF解析失败: {str(e)}',
                'raw_text': ''
            }
    
    def _parse_excel(self, file_path: Path) -> Dict[str, Any]:
        """解析Excel文件"""
        if not EXCEL_AVAILABLE:
            return {
                'success': False,
                'error': 'pandas未安装，无法解析Excel文件',
                'raw_text': ''
            }
        
        try:
            # 读取Excel文件的所有工作表
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            text_content = []
            
            for sheet_name in sheet_names:
                try:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    # 将DataFrame转换为文本
                    sheet_text = f"=== 工作表: {sheet_name} ===\n"
                    
                    # 添加列名
                    if not df.empty:
                        sheet_text += "列名: " + " | ".join(df.columns.astype(str)) + "\n\n"
                        
                        # 添加数据行
                        for index, row in df.iterrows():
                            row_text = " | ".join([str(cell) if pd.notna(cell) else "" for cell in row])
                            sheet_text += f"行{index + 1}: {row_text}\n"
                    
                    text_content.append(sheet_text + "\n")
                    
                except Exception as e:
                    logger.warning(f"工作表 {sheet_name} 解析失败: {e}")
                    continue
            
            raw_text = '\n'.join(text_content)
            
            if not raw_text.strip():
                return {
                    'success': False,
                    'error': 'Excel文件中未找到可提取的内容',
                    'raw_text': '',
                    'sheet_count': len(sheet_names)
                }
            
            return {
                'success': True,
                'raw_text': raw_text.strip(),
                'sheet_count': len(sheet_names),
                'sheet_names': sheet_names,
                'parser_type': 'pandas'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Excel解析失败: {str(e)}',
                'raw_text': ''
            }
    
    def get_supported_formats(self) -> list:
        """获取支持的文件格式列表"""
        return list(self.supported_formats.keys())
    
    def is_supported(self, file_path: str) -> bool:
        """检查文件格式是否支持"""
        file_extension = Path(file_path).suffix.lower()
        return file_extension in self.supported_formats


def test_file_parser():
    """测试文件解析器"""
    print("🧪 测试文件解析器")
    print("=" * 50)
    
    parser = FileParser()
    
    print(f"支持的文件格式: {parser.get_supported_formats()}")
    print(f"PDF支持: {'是' if PDF_AVAILABLE else '否'}")
    print(f"Excel支持: {'是' if EXCEL_AVAILABLE else '否'}")
    
    # 测试示例文件（如果存在）
    sample_files = [
        "data/invoice_sample.pdf",
        "data/uploads/test.pdf",
        "data/uploads/test.xlsx"
    ]
    
    for file_path in sample_files:
        if os.path.exists(file_path):
            print(f"\n📄 测试文件: {file_path}")
            result = parser.parse_file(file_path)
            
            print(f"解析成功: {result['success']}")
            if result['success']:
                print(f"文本长度: {len(result['raw_text'])} 字符")
                print(f"文件大小: {result['file_size']} 字节")
                if 'page_count' in result:
                    print(f"页数: {result['page_count']}")
                if 'sheet_count' in result:
                    print(f"工作表数: {result['sheet_count']}")
            else:
                print(f"错误: {result['error']}")
        else:
            print(f"⚠️ 文件不存在: {file_path}")


if __name__ == "__main__":
    test_file_parser()
