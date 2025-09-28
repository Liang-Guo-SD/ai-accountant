"""
智能会计凭证生成服务（支持复合分录）
结合RAG检索和AI推理，生成标准化的会计分录，支持多借多贷
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
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
from app.schemas import (
    ExtractedInvoiceInfo, 
    JournalEntry, 
    JournalEntryLine, 
    EntryDirection
)

logger = logging.getLogger(__name__)


class JournalGenerationService:
    """增强的智能凭证生成服务（支持复合分录）"""
    
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
        
        logger.info("🧠 增强的智能凭证生成服务初始化完成")
    
    def generate_journal_entry(self, business_description: str, amount: float, 
                              entry_date: str = None,
                              allow_complex: bool = True) -> JournalEntry:
        """
        根据业务描述生成会计分录（支持复合分录）
        
        Args:
            business_description: 业务描述
            amount: 金额
            entry_date: 分录日期
            allow_complex: 是否允许生成复合分录
            
        Returns:
            JournalEntry: 生成的会计分录
        """
        try:
            logger.info(f"📄 开始生成会计分录: {business_description}")
            
            # 设置默认日期
            if not entry_date:
                from datetime import datetime
                entry_date = datetime.now().strftime("%Y-%m-%d")
            
            # 第一步：判断业务复杂度
            is_complex = self._analyze_business_complexity(business_description, amount)
            
            if is_complex and not allow_complex:
                logger.info("业务需要复合分录，但设置为仅生成简单分录")
                is_complex = False
            
            # 第二步：RAG检索相关规则
            logger.info("🔍 检索相关会计准则...")
            relevant_context = self.rag_service.get_context_for_business(business_description)
            
            # 第三步：获取可用科目
            available_accounts = self._get_available_accounts()
            
            # 第四步：根据复杂度选择生成策略
            if is_complex:
                logger.info("🤖 AI生成复合会计分录...")
                journal_entry = self._generate_complex_entry(
                    business_description, amount, entry_date, 
                    relevant_context, available_accounts
                )
            else:
                logger.info("🤖 AI生成简单会计分录...")
                journal_entry = self._generate_simple_entry(
                    business_description, amount, entry_date,
                    relevant_context, available_accounts
                )
            
            # 第五步：验证分录
            self._validate_journal_entry(journal_entry)
            
            logger.info(f"✅ 会计分录生成完成，置信度: {journal_entry.confidence_score}")
            logger.info(f"   分录类型: {'复合分录' if len(journal_entry.entry_lines) > 2 else '简单分录'}")
            logger.info(f"   分录行数: {len(journal_entry.entry_lines)}")
            
            return journal_entry
            
        except Exception as e:
            logger.error(f"❌ 生成会计分录失败: {e}")
            return self._create_error_entry(business_description, amount, entry_date, str(e))
    
    def _analyze_business_complexity(self, business_description: str, amount: float) -> bool:
        """分析业务是否需要复合分录"""
        
        # 复合业务关键词
        complex_indicators = [
            "含税", "增值税", "进项税", "销项税",
            "多个", "分别", "部分", "预付", "预收",
            "工资", "社保", "公积金", "个税",
            "折旧", "摊销", "计提", "预提",
            "应收", "应付", "预付", "预收"
        ]
        
        # 检查是否包含复合业务指标
        description_lower = business_description.lower()
        for indicator in complex_indicators:
            if indicator in description_lower:
                logger.info(f"检测到复合业务指标: {indicator}")
                return True
        
        return False
    
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
    
    def _generate_simple_entry(self, business_description: str, amount: float,
                              entry_date: str, context: str, accounts: str) -> JournalEntry:
        """生成简单分录（单借单贷）"""
        
        system_prompt = self._build_simple_entry_prompt(context, accounts)
        
        user_message = f"""
你是一家名为 {self.our_company_name} 的公司的资深会计师。请为以下发票业务（发票的核心是确认债权或债务）生成简单的会计分录（单借单贷）：

业务描述：{business_description}
金额：{amount}
日期：{entry_date}

请严格按照JSON格式输出。
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        response = self.llm.invoke(messages)
        return self._parse_response_to_journal_entry(response.content, is_complex=False)
    
    def _generate_complex_entry(self, business_description: str, amount: float,
                               entry_date: str, context: str, accounts: str) -> JournalEntry:
        """生成复合分录（多借多贷）"""
        
        system_prompt = self._build_complex_entry_prompt(context, accounts)
        
        user_message = f"""
你是一家名为 {self.our_company_name} 的公司的资深会计师。请为以下业务生成复合会计分录（可能涉及多借多贷）：

业务描述：{business_description}
总金额：{amount}
日期：{entry_date}

如果业务涉及税费、多个科目或需要分解的，请生成相应的复合分录。
请严格按照JSON格式输出。
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        response = self.llm.invoke(messages)
        return self._parse_response_to_journal_entry(response.content, is_complex=True)
    
    def _build_simple_entry_prompt(self, context: str, accounts: str) -> str:
        """构建简单分录的系统提示"""
        
        format_instructions = """
请按以下JSON格式输出简单分录：

{
    "business_description": "业务描述",
    "entry_date": "分录日期(YYYY-MM-DD)",
    "entry_lines": [
        {
            "account_code": "借方科目编码",
            "account_name": "借方科目名称",
            "direction": "借",
            "amount": 金额数字,
            "description": "摘要"
        },
        {
            "account_code": "贷方科目编码",
            "account_name": "贷方科目名称",
            "direction": "贷",
            "amount": 金额数字,
            "description": "摘要"
        }
    ],
    "analysis_process": "详细的分析推理过程",
    "applied_rules": "应用的具体会计准则",
    "confidence_score": 置信度数字(0-1),
    "is_balanced": true,
    "validation_notes": "验证说明",
    "needs_review": false
}
"""
        
        return self._build_base_prompt(context, accounts, format_instructions, "简单")
    
    def _build_complex_entry_prompt(self, context: str, accounts: str) -> str:
        """构建复合分录的系统提示"""
        
        format_instructions = """
请按以下JSON格式输出复合分录：

{
    "business_description": "业务描述",
    "entry_date": "分录日期(YYYY-MM-DD)",
    "entry_lines": [
        {
            "account_code": "科目编码1",
            "account_name": "科目名称1",
            "direction": "借",
            "amount": 金额1,
            "description": "摘要1"
        },
        {
            "account_code": "科目编码2",
            "account_name": "科目名称2",
            "direction": "借",
            "amount": 金额2,
            "description": "摘要2"
        },
        {
            "account_code": "科目编码3",
            "account_name": "科目名称3",
            "direction": "贷",
            "amount": 金额3,
            "description": "摘要3"
        }
    ],
    "analysis_process": "详细的分析推理过程",
    "applied_rules": "应用的具体会计准则",
    "confidence_score": 置信度数字(0-1),
    "is_balanced": true,
    "validation_notes": "验证说明",
    "needs_review": false
}

注意：
1. entry_lines可以包含多行，支持多借多贷
2. 借方合计必须等于贷方合计
3. 每行的direction必须是"借"或"贷"
4. 含税业务要分解为价款和税额
"""
        
        return self._build_base_prompt(context, accounts, format_instructions, "复合")
    
    def _build_base_prompt(self, context: str, accounts: str, 
                          format_instructions: str, entry_type: str) -> str:
        """构建基础系统提示"""
        
        return f"""你是一位资深的注册会计师，具备丰富的会计理论知识和实务经验。

你的任务：
1. 分析给定的业务描述
2. 根据会计准则和基本原理确定合适的会计科目
3. 编制标准的{entry_type}会计分录
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

**核心处理原则：凭证隔离原则**
- 你处理的业务信息来源于【发票】。
- **仅凭一张采购发票，必须默认交易为【赊购】，贷方科目【必须】使用 '2202 应付账款'。**
- **仅凭一张销售发票，必须默认交易为【赊销】，借方科目【必须】使用 '1122 应收账款'。**
- **绝对禁止**在没有明确的银行流水信息时，使用 '1002 银行存款' 或 '1001 库存现金' 作为发票业务的对应科目。

复合分录处理原则：
1. 含税销售：
   借：银行存款/应收账款（价税合计）
   贷：主营业务收入（不含税金额）
   贷：应交税费-应交增值税(销项税额)（税额）

2. 含税采购：
   借：库存商品/原材料（不含税金额）
   借：应交税费-应交增值税(进项税额)（税额）
   贷：银行存款/应付账款（价税合计）

3. 工资发放：
   借：应付职工薪酬（应发工资）
   贷：银行存款（实发工资）
   贷：应交税费-应交个人所得税（代扣个税）
   贷：其他应付款-社保个人部分（代扣社保）

4. 费用报销（含税）：
   借：管理费用/销售费用（不含税金额）
   借：应交税费-应交增值税(进项税额)（可抵扣税额）
   贷：银行存款/现金

编制要求：
- 严格遵循借贷记账法
- 借贷必须平衡
- 选择最合适的会计科目
- 提供清晰的分析推理过程
- 置信度评估：完全匹配规则时给高分(0.8-1.0)，基于原理推理时给中等分(0.6-0.8)

{format_instructions}

请严格按照JSON格式输出，不要添加任何额外说明。"""
    
    def _parse_response_to_journal_entry(self, content: str, is_complex: bool) -> JournalEntry:
        """解析AI响应为JournalEntry对象"""
        
        # 提取JSON字符串
        json_text = None
        code_block = re.search(r"```json\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
        if code_block:
            json_text = code_block.group(1).strip()
        else:
            brace_match = re.search(r"\{[\s\S]*\}", content)
            if brace_match:
                json_text = brace_match.group(0)
        
        if not json_text:
            raise OutputParserException(f"无法从模型输出中提取JSON: {content[:200]}")
        
        try:
            data = json.loads(json_text)
        except Exception as e:
            raise OutputParserException(f"JSON解析失败: {e}\n原始片段: {json_text[:200]}")
        
        # 解析分录明细行
        entry_lines = []
        for line_data in data.get("entry_lines", []):
            # 处理方向字段
            direction_str = str(line_data.get("direction", "")).strip()
            if direction_str in ["借", "DEBIT", "debit"]:
                direction = EntryDirection.DEBIT
            elif direction_str in ["贷", "CREDIT", "credit"]:
                direction = EntryDirection.CREDIT
            else:
                raise ValueError(f"无效的记账方向: {direction_str}")
            
            entry_line = JournalEntryLine(
                account_code=str(line_data.get("account_code", "")),
                account_name=str(line_data.get("account_name", "")),
                direction=direction,
                amount=float(line_data.get("amount", 0)),
                description=line_data.get("description"),
                auxiliary_accounting=line_data.get("auxiliary_accounting")
            )
            entry_lines.append(entry_line)
        
        # 构建JournalEntry对象
        journal_entry = JournalEntry(
            business_description=str(data.get("business_description", "")),
            entry_date=str(data.get("entry_date", "")),
            voucher_number=data.get("voucher_number"),
            entry_lines=entry_lines,
            analysis_process=str(data.get("analysis_process", "")),
            applied_rules=str(data.get("applied_rules", "")),
            confidence_score=float(data.get("confidence_score", 0.0)),
            is_balanced=bool(data.get("is_balanced", False)),
            validation_notes=str(data.get("validation_notes", "")),
            needs_review=bool(data.get("needs_review", False))
        )
        
        return journal_entry
    
    def _validate_journal_entry(self, entry: JournalEntry) -> None:
        """验证会计分录的正确性"""
        validation_issues = []
        
        # 检查是否有分录行
        if not entry.entry_lines:
            validation_issues.append("没有分录明细行")
        
        # 检查借贷平衡
        total_debit = sum(line.debit_amount for line in entry.entry_lines)
        total_credit = sum(line.credit_amount for line in entry.entry_lines)
        
        if abs(total_debit - total_credit) > 0.01:
            validation_issues.append(f"借贷不平衡：借方{total_debit:.2f} ≠ 贷方{total_credit:.2f}")
            entry.is_balanced = False
        else:
            entry.is_balanced = True
        
        # 检查科目编码是否存在
        for line in entry.entry_lines:
            if not self._validate_account_code(line.account_code):
                validation_issues.append(f"科目编码 {line.account_code} 不存在")
            
            if line.amount <= 0:
                validation_issues.append(f"科目 {line.account_name} 的金额必须大于零")
        
        # 检查是否有借方和贷方
        has_debit = any(line.direction == EntryDirection.DEBIT for line in entry.entry_lines)
        has_credit = any(line.direction == EntryDirection.CREDIT for line in entry.entry_lines)
        
        if not has_debit:
            validation_issues.append("分录缺少借方")
        if not has_credit:
            validation_issues.append("分录缺少贷方")
        
        # 更新验证说明与复核标记
        if validation_issues:
            entry.validation_notes = "验证发现问题: " + "; ".join(validation_issues)
            entry.confidence_score = min(entry.confidence_score, 0.5)
            entry.needs_review = True
        else:
            entry.validation_notes = "验证通过"
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
            entry_lines=[],
            analysis_process=f"生成失败：{error}",
            applied_rules="无",
            confidence_score=0.0,
            is_balanced=False,
            validation_notes=f"生成错误：{error}",
            needs_review=True
        )


def display_journal_entry(entry: JournalEntry):
    """美化显示会计分录"""
    print("\n" + "=" * 60)
    print(f"📊 会计分录")
    print("-" * 60)
    print(f"业务描述: {entry.business_description}")
    print(f"分录日期: {entry.entry_date}")
    if entry.voucher_number:
        print(f"凭证号: {entry.voucher_number}")
    print(f"置信度: {entry.confidence_score:.2%}")
    print(f"是否平衡: {'✅ 是' if entry.is_balanced else '❌ 否'}")
    print(f"需要审核: {'⚠️ 是' if entry.needs_review else '✅ 否'}")
    
    print("\n分录明细:")
    print("-" * 60)
    
    # 分组显示借方和贷方
    debit_lines = [l for l in entry.entry_lines if l.direction == EntryDirection.DEBIT]
    credit_lines = [l for l in entry.entry_lines if l.direction == EntryDirection.CREDIT]
    
    if debit_lines:
        print("借方:")
        for line in debit_lines:
            print(f"  {line.account_code} {line.account_name:20} {line.amount:>12,.2f}")
            if line.description:
                print(f"    摘要: {line.description}")
    
    if credit_lines:
        print("贷方:")
        for line in credit_lines:
            print(f"  {line.account_code} {line.account_name:20} {line.amount:>12,.2f}")
            if line.description:
                print(f"    摘要: {line.description}")
    
    print("-" * 60)
    print(f"合计: 借方 {entry.total_debit:,.2f} | 贷方 {entry.total_credit:,.2f}")
    
    if entry.validation_notes:
        print(f"\n验证说明: {entry.validation_notes}")
    
    print("=" * 60)


def test_enhanced_journal_generator():
    """测试增强的智能凭证生成"""
    print("🧪 测试增强的智能会计凭证生成（支持复合分录）")
    print("=" * 60)
    
    try:
        # 初始化服务
        generator = JournalGenerationService()
        
        # 测试用例
        test_cases = [
            {
                "description": "收到客户银行转账支付货款11300元，其中货款10000元，增值税1300元",
                "amount": 11300.0,
                "date": "2024-03-20",
                "expect_complex": True
            },
            {
                "description": "支付办公室房租5000元",
                "amount": 5000.0,
                "date": "2024-03-20",
                "expect_complex": False
            },
            {
                "description": "采购办公用品，价税合计5650元，其中价款5000元，增值税650元",
                "amount": 5650.0,
                "date": "2024-03-20",
                "expect_complex": True
            },
            {
                "description": "发放工资10000元，代扣个人所得税500元，代扣社保个人部分800元，实发8700元",
                "amount": 10000.0,
                "date": "2024-03-20",
                "expect_complex": True
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n📋 测试用例 {i}: {case['description']}")
            print(f"   预期类型: {'复合分录' if case['expect_complex'] else '简单分录'}")
            print("-" * 60)
            
            # 生成分录
            entry = generator.generate_journal_entry(
                case["description"],
                case["amount"],
                case["date"],
                allow_complex=True  # 允许生成复合分录
            )
            
            # 显示结果
            display_journal_entry(entry)
            
            # 验证分录类型
            is_complex = len(entry.entry_lines) > 2
            print(f"\n实际类型: {'复合分录' if is_complex else '简单分录'}")
            print(f"分录行数: {len(entry.entry_lines)}")
        
        print("\n" + "=" * 60)
        print("🎉 增强的智能凭证生成测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 可能的解决方案:")
        print("1. 确保数据库已初始化（有会计科目数据）")
        print("2. 检查API密钥配置")
        print("3. 确保RAG服务正常工作")


if __name__ == "__main__":
    test_enhanced_journal_generator()