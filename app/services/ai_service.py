"""
AI信息提取服务
使用GPT和LangChain从文档中提取结构化信息
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any
import json
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import OutputParserException
from langchain.output_parsers import PydanticOutputParser
from dotenv import load_dotenv
import logging

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入我们定义的数据结构
from app.schemas import ExtractedInvoiceInfo
from app.core.config import get_ai_config

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class AIExtractionService:
    """AI信息提取服务"""
    
    def __init__(self):
        """初始化AI服务"""
        # 使用配置管理模块
        config = get_ai_config()
        
        logger.info(f"🤖 初始化AI服务 - 模型: {config.openai_model}, 温度: {config.openai_temperature}")
        
        # 初始化GPT模型
        self.llm = ChatOpenAI(
            model=config.openai_model,
            temperature=config.openai_temperature,
            openai_api_key=config.openai_api_key,
            timeout=config.timeout,
            max_tokens=config.max_tokens
        )
        
        # 创建解析器
        self.invoice_parser = PydanticOutputParser(pydantic_object=ExtractedInvoiceInfo)
        
        logger.info("✅ AI信息提取服务初始化完成")
    
    def extract_invoice_info(self, raw_text: str) -> ExtractedInvoiceInfo:
        """
        从发票文本中提取结构化信息
        
        Args:
            raw_text: PDF提取的原始文本
            
        Returns:
            ExtractedInvoiceInfo: 结构化的发票信息
        """
        try:
            logger.info("🔍 开始AI信息提取...")
            
            # 构建完整的提示
            system_prompt = self._get_invoice_system_prompt()
            human_message = f"请从以下文本中提取发票信息：\n\n{raw_text}"
            
            # 创建消息列表
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": human_message}
            ]
            
            # 直接调用LLM
            response = self.llm.invoke(messages)
            
            # 解析响应
            result = self.invoice_parser.parse(response.content)
            
            logger.info(f"✅ AI提取完成，置信度: {result.confidence_score}")
            return result
            
        except OutputParserException as e:
            logger.error(f"❌ AI输出解析失败: {e}")
            logger.error(f"原始AI输出: {getattr(e, 'llm_output', '无法获取')}")
            # 返回一个默认的结构，避免程序崩溃
            return ExtractedInvoiceInfo(
                business_analysis="AI解析失败，需要人工处理",
                confidence_score=0.0
            )
        except Exception as e:
            logger.error(f"❌ AI信息提取失败: {e}")
            raise
    
    def _get_invoice_system_prompt(self) -> str:
        """
        获取发票信息提取的系统提示词
        这是AI理解任务的关键
        """
        # 手动构建格式说明，避免LangChain变量冲突
        format_instructions = """
请按以下JSON格式输出，所有字段都是必需的：

{{
    "document_type": "销售发票" | "采购发票" | "收据" | "其他",
    "invoice_number": "发票号码字符串或null",
    "invoice_date": "日期字符串(YYYY-MM-DD格式)或null", 
    "seller_name": "销售方名称字符串或null",
    "buyer_name": "购买方名称字符串或null",
    "amount_before_tax": 不含税金额数字或null,
    "tax_amount": 税额数字或null,
    "total_amount": 总金额数字或null,
    "goods_description": "商品描述字符串或null",
    "standardized_business_description": "标准化业务描述字符串",
    "business_category": "销售收入" | "采购支出" | "费用支出" | "资产购置" | "其他",
    "business_analysis": "业务分析字符串",
    "confidence_score": 置信度数字(0-1之间)
}}
"""
        
        return f"""你是一位专业的会计师，负责从发票文档中提取关键信息，并生成标准化的业务描述。

你的任务：
1. 仔细分析提供的文本内容
2. 识别并提取发票的关键信息
3. 判断这是销售发票还是采购发票
4. **重要：生成标准化的业务描述，使用会计准则中的标准用词**
5. 分析这笔业务的会计含义
6. 评估提取信息的置信度

标准化业务描述生成规则：
- 如果是销售发票（我方开给客户）：使用"销售商品收到银行存款"、"销售商品收现金"等标准表述
- 如果是采购发票（供应商开给我方）：使用"采购商品"、"支付货款"等标准表述
- 涉及固定资产：使用"购买固定资产"、"采购设备"等表述
- 涉及费用：使用"支付房租"、"支付广告费"、"支付办公费"等表述
- 优先使用会计准则中出现的关键词

业务分类指导：
- 销售收入：我方销售商品给客户的发票
- 采购支出：从供应商采购商品的发票  
- 费用支出：租金、广告、办公用品等费用类发票
- 资产购置：购买设备、软件等资产的发票

注意事项：
- 金额请转换为数字格式（去掉逗号和货币符号）
- 日期请使用YYYY-MM-DD格式
- 如果信息不清楚或缺失，对应字段设为null
- 置信度基于文本清晰度和信息完整性
- business_analysis字段请用简洁的中文说明这笔业务
- **standardized_business_description是关键字段，必须使用标准会计用词**

{format_instructions}

请严格按照上述JSON格式输出，不要添加任何额外的文字解释。"""


def test_ai_extraction():
    """测试AI信息提取功能"""
    
    # 模拟发票文本
    sample_invoice_text = """
    发票
    
    销售方：阳光商贸有限公司
    地址：北京市朝阳区阳光大街123号
    税号：91110000123456789X
    
    购买方：星星科技有限公司
    地址：上海市浦东新区星星路456号
    税号：91310000987654321Y
    
    货物或应税劳务名称：办公用品
    规格型号：各种
    数量：1批
    单价：1000.00
    金额：1,000.00
    税率：13%
    税额：130.00
    
    价税合计（大写）：壹仟壹佰叁拾元整
    价税合计（小写）：￥1,130.00
    
    开票日期：2024年3月15日
    发票号码：12345678
    """
    
    try:
        service = AIExtractionService()
        result = service.extract_invoice_info(sample_invoice_text)
        
        print("🧪 AI信息提取测试结果:")
        print("=" * 50)
        print(f"文档类型: {result.document_type}")
        print(f"发票号码: {result.invoice_number}")
        print(f"开票日期: {result.invoice_date}")
        print(f"销售方: {result.seller_name}")
        print(f"购买方: {result.buyer_name}")
        print(f"总金额: {result.total_amount}")
        print(f"业务分析: {result.business_analysis}")
        print(f"置信度: {result.confidence_score}")
        print("=" * 50)
        
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print("💡 请检查：")
        print("1. .env文件中是否设置了OPENAI_API_KEY")
        print("2. API密钥是否有效")
        print("3. 网络连接是否正常")


if __name__ == "__main__":
    # 运行测试
    test_ai_extraction()