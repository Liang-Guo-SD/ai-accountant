"""
业务标准化服务
将复杂的发票信息转换为标准化的业务描述，提高RAG检索精度
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any
import json
import logging

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from langchain_community.chat_models import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.core.config import get_ai_config
from app.schemas import ExtractedInvoiceInfo

logger = logging.getLogger(__name__)


class StandardizedBusiness(BaseModel):
    """标准化业务描述"""
    
    # 核心业务要素
    business_type: str = Field(description="业务类型：收款/付款/采购/销售等")
    payment_method: str = Field(description="支付方式：现金/银行转账/应收应付等")
    business_nature: str = Field(description="业务性质：销售商品/支付费用/资产购买等")
    amount_info: str = Field(description="金额信息：含税总额、不含税金额、税额等")
    
    # 标准化描述
    standardized_description: str = Field(description="标准化的业务描述，使用会计术语")
    key_elements: list = Field(description="关键业务要素列表")
    
    # 检索优化
    search_keywords: list = Field(description="用于RAG检索的关键词")
    confidence_level: float = Field(description="标准化的置信度")


class BusinessStandardizerService:
    """业务标准化服务"""
    
    def __init__(self):
        """初始化服务"""
        self.config = get_ai_config()
        self.llm = ChatOpenAI(
            model=self.config.openai_model,
            temperature=0.1,  # 使用较低温度确保标准化的一致性
            openai_api_key=self.config.openai_api_key
        )
        
        self.parser = PydanticOutputParser(pydantic_object=StandardizedBusiness)
        logger.info("🔧 业务标准化服务初始化完成")
    
    def standardize_business(self, extracted_info: ExtractedInvoiceInfo) -> StandardizedBusiness:
        """
        将提取的发票信息标准化为精确的业务描述
        
        Args:
            extracted_info: 从发票中提取的信息
            
        Returns:
            StandardizedBusiness: 标准化的业务描述
        """
        try:
            logger.info("🔄 开始标准化业务描述...")
            
            # 构建输入信息
            input_data = {
                "document_type": extracted_info.document_type,
                "seller_name": extracted_info.seller_name,
                "buyer_name": extracted_info.buyer_name,
                "total_amount": extracted_info.total_amount,
                "amount_before_tax": extracted_info.amount_before_tax,
                "tax_amount": extracted_info.tax_amount,
                "goods_description": extracted_info.goods_description,
                "business_analysis": extracted_info.business_analysis
            }
            
            # 构建提示并调用AI
            standardized = self._generate_standardized_description(input_data)
            
            logger.info(f"✅ 业务标准化完成: {standardized.standardized_description}")
            return standardized
            
        except Exception as e:
            logger.error(f"❌ 业务标准化失败: {e}")
            # 返回降级版本
            return self._create_fallback_standardized(extracted_info)
    
    def _generate_standardized_description(self, input_data: Dict[str, Any]) -> StandardizedBusiness:
        """使用AI生成标准化描述"""
        
        system_prompt = self._build_standardization_prompt()
        
        user_message = f"""
请分析以下发票信息并生成标准化业务描述：

发票信息：
{json.dumps(input_data, ensure_ascii=False, indent=2)}

请严格按照JSON格式输出标准化结果。
"""
        
        # 调用AI
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        response = self.llm.invoke(messages)
        standardized = self.parser.parse(response.content)
        
        return standardized
    
    def _build_standardization_prompt(self) -> str:
        """构建标准化提示"""
        
        format_instructions = """
请按以下JSON格式输出：

{
    "business_type": "业务类型分类",
    "payment_method": "支付方式",
    "business_nature": "业务性质描述",
    "amount_info": "金额详细信息（字符串格式，如：总金额11900元，不含税11782.18元，税额117.82元）",
    "standardized_description": "标准化业务描述",
    "key_elements": ["关键要素1", "关键要素2"],
    "search_keywords": ["检索关键词1", "检索关键词2"],
    "confidence_level": 置信度数字
}
"""
        
        return f"""你是一位专业的会计分析师，专门负责将复杂的发票信息标准化为精确的会计业务描述。

你的任务：
1. 分析发票中的关键信息
2. 识别核心业务类型和特征
3. 生成标准化的业务描述
4. 提供精确的检索关键词

标准化原则：
- 使用标准会计术语
- 突出关键业务要素：谁支付/收取、多少钱、什么业务
- 明确资金流向：收款还是付款
- 识别业务性质：销售、采购、费用支付等

业务类型分类：
- "销售收款" - 销售商品或服务收到款项
- "采购付款" - 采购商品或服务支付款项  
- "费用支付" - 支付各种费用（房租、广告等）
- "资产购买" - 购买固定资产、无形资产等
- "资金往来" - 投资、借款、还款等

支付方式分类：
- "现金收付" - 现金交易
- "银行转账" - 通过银行转账
- "应收应付" - 赊销赊购，形成债权债务

关键词提取要求：
- 包含业务动作词：收到、支付、采购、销售等
- 包含资金相关词：现金、银行转账、货款等  
- 包含业务对象：商品、服务、房租、设备等
- 避免公司名称等非关键信息

{format_instructions}

请严格按照JSON格式输出，确保关键词能精确匹配会计准则库。"""
    
    def _create_fallback_standardized(self, extracted_info: ExtractedInvoiceInfo) -> StandardizedBusiness:
        """创建降级版本的标准化描述"""
        return StandardizedBusiness(
            business_type="未知业务类型",
            payment_method="未知支付方式", 
            business_nature="需要人工分析",
            amount_info=f"总金额: {extracted_info.total_amount or 0}",
            standardized_description="标准化失败，需要人工处理",
            key_elements=["标准化失败"],
            search_keywords=["通用业务"],
            confidence_level=0.0
        )


def test_business_standardizer():
    """测试业务标准化服务"""
    print("🧪 测试业务标准化服务")
    print("=" * 60)
    
    try:
        # 初始化服务
        standardizer = BusinessStandardizerService()
        
        # 模拟几种不同类型的发票信息
        test_cases = [
            # 测试用例1：银行收款
            ExtractedInvoiceInfo(
                document_type="销售发票",
                seller_name="阳光商贸有限公司",
                buyer_name="星星科技有限公司", 
                total_amount=1130.0,
                amount_before_tax=1000.0,
                tax_amount=130.0,
                goods_description="办公用品",
                business_analysis="客户银行转账支付货款"
            ),
            
            # 测试用例2：现金销售
            ExtractedInvoiceInfo(
                document_type="销售发票",
                seller_name="便民商店",
                buyer_name="个人客户",
                total_amount=50.0,
                goods_description="日用品",
                business_analysis="现金销售商品"
            ),
            
            # 测试用例3：费用支付
            ExtractedInvoiceInfo(
                document_type="收据",
                seller_name="物业管理公司",
                buyer_name="我公司",
                total_amount=5000.0,
                goods_description="办公室租金",
                business_analysis="支付办公室房租"
            )
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n📋 测试用例 {i}: {case.business_analysis}")
            print("-" * 40)
            
            # 标准化处理
            standardized = standardizer.standardize_business(case)
            
            # 显示结果
            print(f"🏷️  业务类型: {standardized.business_type}")
            print(f"💳 支付方式: {standardized.payment_method}")
            print(f"📝 标准化描述: {standardized.standardized_description}")
            print(f"🔍 检索关键词: {', '.join(standardized.search_keywords)}")
            print(f"📊 置信度: {standardized.confidence_level:.2f}")
        
        print("\n" + "=" * 60)
        print("🎉 业务标准化测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print("💡 请检查API配置和网络连接")


if __name__ == "__main__":
    test_business_standardizer()