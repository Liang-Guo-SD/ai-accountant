"""
智能会计凭证生成服务
结合RAG检索和AI推理，生成标准化的会计分录
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import json
import logging
import re

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import OutputParserException
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.core.config import get_ai_config, get_app_config
from app.services.rag_service import AccountingRAGService
from app.services.business_standardizer import BusinessStandardizerService
from app.database import SessionLocal
from app.models.accounting import Account
from app.schemas import ExtractedInvoiceInfo

logger = logging.getLogger(__name__)


class JournalEntry(BaseModel):
    """会计分录数据结构"""
    
    # 基本信息
    business_description: str = Field(description="业务描述")
    entry_date: str = Field(description="分录日期，格式YYYY-MM-DD")
    
    # 分录明细
    debit_account_code: str = Field(description="借方科目编码")
    debit_account_name: str = Field(description="借方科目名称")
    credit_account_code: str = Field(description="贷方科目编码") 
    credit_account_name: str = Field(description="贷方科目名称")
    amount: float = Field(description="金额")
    
    # AI分析过程
    analysis_process: str = Field(description="AI的分析推理过程")
    applied_rules: str = Field(description="应用的会计准则")
    confidence_score: float = Field(description="置信度评分 0-1")
    
    # 验证信息
    is_balanced: bool = Field(description="借贷是否平衡")
    validation_notes: str = Field(description="验证说明")
    needs_review: bool = Field(False, description="是否需要人工审核")


class JournalGenerationService:
    """智能凭证生成服务"""
    
    def __init__(self):
        """初始化服务"""
        self.config = get_ai_config()
        self.our_company_tax_id = get_app_config().our_company_tax_id
        self.our_company_name = get_app_config().our_company_name
        self.llm = ChatOpenAI(
            model=self.config.openai_model,
            temperature=self.config.openai_temperature,
            openai_api_key=self.config.openai_api_key
        )
        
        # 初始化RAG服务
        self.rag_service = AccountingRAGService()
        if not self.rag_service.load_and_index_rules():
            logger.warning("⚠️ RAG服务初始化失败，将使用基础规则")
        
        # 初始化业务标准化服务
        self.standardizer = BusinessStandardizerService()
        
        # 初始化解析器
        self.parser = PydanticOutputParser(pydantic_object=JournalEntry)
        
        logger.info("🧠 智能凭证生成服务初始化完成")
    
    def generate_journal_entry(self, business_description: str, amount: float, 
                             entry_date: str = None) -> JournalEntry:
        """
        根据业务描述生成会计分录
        
        Args:
            business_description: 业务描述
            amount: 金额
            entry_date: 分录日期
            
        Returns:
            JournalEntry: 生成的会计分录
        """
        try:
            logger.info(f"🔄 开始生成会计分录: {business_description}")
            
            # 设置默认日期
            if not entry_date:
                from datetime import datetime
                entry_date = datetime.now().strftime("%Y-%m-%d")
            
            # 第一步：RAG检索相关规则
            logger.info("🔍 检索相关会计准则...")
            relevant_context = self.rag_service.get_context_for_business(business_description)
            
            # 第二步：获取可用科目
            available_accounts = self._get_available_accounts()
            
            # 第三步：构建提示并生成分录
            logger.info("🤖 AI生成会计分录...")
            journal_entry = self._generate_with_ai(
                business_description, amount, entry_date, 
                relevant_context, available_accounts
            )
            
            # 第四步：验证分录
            self._validate_journal_entry(journal_entry)
            
            logger.info(f"✅ 会计分录生成完成，置信度: {journal_entry.confidence_score}")
            return journal_entry
            
        except Exception as e:
            logger.error(f"❌ 生成会计分录失败: {e}")
            # 返回一个错误分录
            return self._create_error_entry(business_description, amount, entry_date, str(e))
    
    def _get_available_accounts(self) -> str:
        """获取可用的会计科目列表"""
        try:
            db = SessionLocal()
            accounts = db.query(Account).filter(Account.is_active == True).order_by(Account.code).all()
            
            if not accounts:
                return "未找到可用的会计科目"
            
            account_list = []
            for account in accounts:
                account_list.append(f"{account.code} {account.name} ({account.category})")
            
            return "\n".join(account_list)
            
        except Exception as e:
            logger.warning(f"获取科目列表失败: {e}")
            return "无法获取科目列表"
        finally:
            if 'db' in locals():
                db.close()
    
    def _generate_with_ai(self, business_description: str, amount: float, 
                         entry_date: str, context: str, accounts: str) -> JournalEntry:
        """使用AI生成会计分录"""
        
        # 构建系统提示
        system_prompt = self._build_system_prompt(context, accounts)
        
        # 构建用户消息
        user_message = f"""
你是一家名为 {self.our_company_name} 的公司的资深会计师。请为以下业务生成会计分录：

业务描述：{business_description}
金额：{amount}
日期：{entry_date}

请严格按照JSON格式输出，包含完整的分析过程。
"""

        # 调用AI
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        response = self.llm.invoke(messages)
        
        # 解析响应（带容错）
        return self._parse_response_to_journal_entry(response.content)

    def _parse_response_to_journal_entry(self, content: str) -> JournalEntry:
        """将LLM输出解析为 JournalEntry，带容错与纠偏。

        处理策略：
        1) 首先使用 PydanticOutputParser 直接解析
        2) 若失败，则提取JSON子串并手动loads
        3) 字段纠偏：
           - applied_rules 若为列表，拼接为字符串
           - amount 转为 float
           - 其他必填字段转字符串
        """
        try:
            return self.parser.parse(content)
        except Exception:
            pass

        # 提取JSON子串
        json_text = None
        # 优先匹配 ```json ... ```
        code_block = re.search(r"```json\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
        if code_block:
            json_text = code_block.group(1).strip()
        else:
            # 回退：贪婪匹配第一个花括号JSON
            brace_match = re.search(r"\{[\s\S]*\}", content)
            if brace_match:
                json_text = brace_match.group(0)

        if not json_text:
            raise OutputParserException(f"无法从模型输出中提取JSON: {content[:200]}")

        try:
            data = json.loads(json_text)
        except Exception as e:
            raise OutputParserException(f"JSON解析失败: {e}\n原始片段: {json_text[:200]}")

        # 字段纠偏
        def to_str(v) -> str:
            if v is None:
                return ""
            if isinstance(v, (list, dict)):
                return json.dumps(v, ensure_ascii=False)
            return str(v)

        coerced: Dict[str, Any] = {}
        coerced["business_description"] = to_str(data.get("business_description"))
        coerced["entry_date"] = to_str(data.get("entry_date"))
        coerced["debit_account_code"] = to_str(data.get("debit_account_code"))
        coerced["debit_account_name"] = to_str(data.get("debit_account_name"))
        coerced["credit_account_code"] = to_str(data.get("credit_account_code"))
        coerced["credit_account_name"] = to_str(data.get("credit_account_name"))

        amount_val = data.get("amount")
        try:
            coerced["amount"] = float(amount_val) if amount_val is not None else 0.0
        except Exception:
            coerced["amount"] = 0.0

        analysis = data.get("analysis_process")
        coerced["analysis_process"] = to_str(analysis)

        applied_rules = data.get("applied_rules")
        if isinstance(applied_rules, list):
            coerced["applied_rules"] = "; ".join(to_str(x) for x in applied_rules)
        else:
            coerced["applied_rules"] = to_str(applied_rules)

        conf = data.get("confidence_score")
        try:
            coerced["confidence_score"] = float(conf) if conf is not None else 0.0
        except Exception:
            coerced["confidence_score"] = 0.0

        is_balanced = data.get("is_balanced")
        coerced["is_balanced"] = bool(is_balanced) if isinstance(is_balanced, bool) else True

        coerced["validation_notes"] = to_str(data.get("validation_notes"))

        # needs_review: 若模型未提供，按保守策略设置为 False，由上游流程独立判定
        nr = data.get("needs_review")
        coerced["needs_review"] = bool(nr) if isinstance(nr, bool) else False

        # 使用Pydantic构造
        return JournalEntry(**coerced)
    
    def _build_system_prompt(self, context: str, accounts: str) -> str:
        """构建系统提示"""
        format_instructions = """
请按以下JSON格式输出：

{
    "business_description": "业务描述",
    "entry_date": "分录日期(YYYY-MM-DD)",
    "debit_account_code": "借方科目编码",
    "debit_account_name": "借方科目名称", 
    "credit_account_code": "贷方科目编码",
    "credit_account_name": "贷方科目名称",
    "amount": 金额数字,
    "analysis_process": "详细的分析推理过程",
    "applied_rules": "应用的具体会计准则（字符串格式，如：规则A02: 银行收到销售货款）",
    "confidence_score": 置信度数字(0-1),
    "is_balanced": true,
    "validation_notes": "验证说明"
}
"""
        
        return f"""你是一位资深的注册会计师，具备丰富的会计理论知识和实务经验。

你的任务：
1. 分析给定的业务描述
2. 根据会计准则和基本原理确定合适的会计科目
3. 编制标准的会计分录
4. 提供详细的分析过程
5. 评估结果的可靠性

可用的会计科目：
{accounts}

相关的会计准则：
{context}

基本会计原理：
- 资产 = 负债 + 所有者权益
- 资产增加记借方，资产减少记贷方
- 负债增加记贷方，负债减少记借方
- 收入增加记贷方，费用增加记借方
- 有借必有贷，借贷必相等

常见业务处理原则：
1. 现金销售：借记现金，贷记收入
2. 银行收款：借记银行存款，贷记收入
3. 支付费用：借记相应费用科目，贷记现金/银行存款
4. 房租费用通常属于管理费用
5. 销售相关费用属于销售费用
6. 日常办公费用属于管理费用

编制要求：
- 即使检索到的准则不完整，也要基于基本会计原理进行推理
- 严格遵循借贷记账法：有借必有贷，借贷必相等
- 选择最合适的会计科目
- 提供清晰的分析推理过程，说明为什么这样处理
- 如果准则库中没有完全匹配的规则，请说明你的推理依据
- 置信度评估：完全匹配规则时给高分(0.8-1.0)，基于原理推理时给中等分(0.6-0.8)，不确定时给低分(0.3-0.6)

{format_instructions}

请严格按照JSON格式输出，不要添加任何额外说明。"""
    
    def _validate_journal_entry(self, entry: JournalEntry) -> None:
        """验证会计分录的正确性"""
        validation_issues = []
        
        # 检查科目编码是否存在
        if not self._validate_account_code(entry.debit_account_code):
            validation_issues.append(f"借方科目编码 {entry.debit_account_code} 不存在")
        
        if not self._validate_account_code(entry.credit_account_code):
            validation_issues.append(f"贷方科目编码 {entry.credit_account_code} 不存在")
        
        # 检查金额是否合理
        if entry.amount <= 0:
            validation_issues.append("金额必须大于零")
        
        # 检查借贷是否相等（这里简化为单个分录）
        entry.is_balanced = True  # 单笔分录天然平衡
        
        # 更新验证说明与复核标记
        if validation_issues:
            entry.validation_notes = "验证发现问题: " + "; ".join(validation_issues)
            entry.confidence_score = min(entry.confidence_score, 0.5)  # 降低置信度
            entry.needs_review = True
        else:
            entry.validation_notes = "验证通过"
            # 若置信度偏低，建议复核
            if entry.confidence_score < 0.6:
                entry.needs_review = True
    
    def _validate_account_code(self, code: str) -> bool:
        """验证科目编码是否存在"""
        try:
            db = SessionLocal()
            account = db.query(Account).filter(Account.code == code).first()
            return account is not None
        except:
            return False
        finally:
            if 'db' in locals():
                db.close()
    
    def _create_error_entry(self, description: str, amount: float, 
                          date: str, error: str) -> JournalEntry:
        """创建错误分录"""
        return JournalEntry(
            business_description=description,
            entry_date=date,
            debit_account_code="",
            debit_account_name="",
            credit_account_code="",
            credit_account_name="",
            amount=amount,
            analysis_process=f"生成失败：{error}",
            applied_rules="无",
            confidence_score=0.0,
            is_balanced=False,
            validation_notes=f"生成错误：{error}",
            needs_review=True
        )


def test_journal_generator():
    """测试智能凭证生成"""
    print("🧪 测试智能会计凭证生成")
    print("=" * 60)
    
    try:
        # 初始化服务
        generator = JournalGenerationService()
        
        # 测试用例
        test_cases = [
            {
                "description": "收到客户银行转账支付货款",
                "amount": 10000.0,
                "date": "2024-03-20"
            },
            {
                "description": "支付办公室房租",
                "amount": 5000.0,
                "date": "2024-03-20"
            },
            {
                "description": "销售商品收到现金",
                "amount": 3000.0,
                "date": "2024-03-20"
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n📋 测试用例 {i}: {case['description']}")
            print("-" * 40)
            
            # 生成分录
            entry = generator.generate_journal_entry(
                case["description"], 
                case["amount"], 
                case["date"]
            )
            
            # 显示结果
            print(f"📊 置信度: {entry.confidence_score:.2f}")
            print(f"💰 金额: {entry.amount}")
            print(f"📝 借方: {entry.debit_account_code} {entry.debit_account_name}")
            print(f"📝 贷方: {entry.credit_account_code} {entry.credit_account_name}")
            print(f"🔍 分析过程: {entry.analysis_process[:100]}...")
            print(f"✅ 验证结果: {entry.validation_notes}")
        
        print("\n" + "=" * 60)
        print("🎉 智能凭证生成测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print("\n💡 可能的解决方案:")
        print("1. 确保数据库已初始化（有会计科目数据）")
        print("2. 检查API密钥配置")
        print("3. 确保RAG服务正常工作")


if __name__ == "__main__":
    test_journal_generator()