"""
财务报表生成模块
生成标准的三大财务报表：资产负债表、利润表、现金流量表
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.database import SessionLocal
from app.models.accounting import Account, JournalEntry as JournalEntryModel
from app.schemas import JournalEntry, EntryDirection

logger = logging.getLogger(__name__)


class FinancialReportGenerator:
    """
    财务报表生成器
    负责从数据库读取凭证数据，计算科目余额，生成各类财务报表
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """初始化报表生成器"""
        self.db = db_session or SessionLocal()
        self.account_balances = {}
        self.period_start = None
        self.period_end = None
    
    def calculate_account_balances(self, 
                                  start_date: date, 
                                  end_date: date,
                                  only_approved: bool = True) -> Dict[str, Decimal]:
        """
        计算指定期间的科目余额
        
        Args:
            start_date: 开始日期
            end_date: 结束日期  
            only_approved: 是否只计算已批准的凭证
            
        Returns:
            科目余额字典 {科目编码: 余额}
        """
        self.period_start = start_date
        self.period_end = end_date
        
        # 查询期间内的凭证
        query = self.db.query(JournalEntryModel).filter(
            and_(
                JournalEntryModel.entry_date >= start_date,
                JournalEntryModel.entry_date <= end_date
            )
        )
        
        if only_approved:
            query = query.filter(JournalEntryModel.status == 'approved')
        
        journals = query.all()
        
        # 初始化余额字典
        balances = defaultdict(Decimal)
        
        # 计算各科目余额
        for journal in journals:
            for line in journal.entry_lines:
                account_code = line['account_code']
                amount = Decimal(str(line['amount']))
                direction = line['direction']
                
                # 根据借贷方向和科目性质计算余额
                account = self._get_account_info(account_code)
                if account:
                    if account['category'] in ['资产', '费用']:
                        # 资产和费用类科目：借增贷减
                        if direction == '借':
                            balances[account_code] += amount
                        else:
                            balances[account_code] -= amount
                    else:
                        # 负债、所有者权益、收入类科目：贷增借减
                        if direction == '贷':
                            balances[account_code] += amount
                        else:
                            balances[account_code] -= amount
        
        self.account_balances = dict(balances)
        return self.account_balances
    
    def generate_balance_sheet(self) -> Dict:
        """
        生成资产负债表
        
        Returns:
            资产负债表数据
        """
        if not self.account_balances:
            raise ValueError("请先计算科目余额")
        
        # 资产负债表结构
        balance_sheet = {
            "report_name": "资产负债表",
            "period": f"{self.period_start} 至 {self.period_end}",
            "currency": "CNY",
            "assets": {
                "current_assets": {},  # 流动资产
                "non_current_assets": {},  # 非流动资产
                "total_assets": Decimal(0)
            },
            "liabilities": {
                "current_liabilities": {},  # 流动负债
                "non_current_liabilities": {},  # 非流动负债
                "total_liabilities": Decimal(0)
            },
            "equity": {
                "paid_in_capital": Decimal(0),  # 实收资本
                "retained_earnings": Decimal(0),  # 留存收益
                "total_equity": Decimal(0)
            },
            "total_liabilities_and_equity": Decimal(0),
            "is_balanced": False
        }
        
        # 分类汇总科目余额
        for account_code, balance in self.account_balances.items():
            account = self._get_account_info(account_code)
            if not account:
                continue
            
            # 资产类
            if account['category'] == '资产':
                if account_code.startswith('1'):
                    # 流动资产 (1xxx)
                    if account_code[:2] in ['10', '11', '12']:
                        balance_sheet['assets']['current_assets'][account['name']] = balance
                    # 非流动资产 (16xx-19xx)
                    else:
                        balance_sheet['assets']['non_current_assets'][account['name']] = balance
                    balance_sheet['assets']['total_assets'] += balance
            
            # 负债类
            elif account['category'] == '负债':
                if account_code.startswith('2'):
                    # 流动负债 (20xx-22xx)
                    if account_code[:2] in ['20', '21', '22']:
                        balance_sheet['liabilities']['current_liabilities'][account['name']] = balance
                    # 非流动负债 (24xx-29xx)
                    else:
                        balance_sheet['liabilities']['non_current_liabilities'][account['name']] = balance
                    balance_sheet['liabilities']['total_liabilities'] += balance
            
            # 所有者权益类
            elif account['category'] == '所有者权益':
                if account_code.startswith('4'):
                    if account_code[:4] == '4001':  # 实收资本
                        balance_sheet['equity']['paid_in_capital'] += balance
                    else:  # 其他权益
                        balance_sheet['equity']['retained_earnings'] += balance
                    balance_sheet['equity']['total_equity'] += balance
        
        # 计算总计
        balance_sheet['total_liabilities_and_equity'] = (
            balance_sheet['liabilities']['total_liabilities'] + 
            balance_sheet['equity']['total_equity']
        )
        
        # 检查平衡
        balance_sheet['is_balanced'] = abs(
            balance_sheet['assets']['total_assets'] - 
            balance_sheet['total_liabilities_and_equity']
        ) < Decimal('0.01')
        
        return balance_sheet
    
    def generate_income_statement(self) -> Dict:
        """
        生成利润表（损益表）
        
        Returns:
            利润表数据
        """
        if not self.account_balances:
            raise ValueError("请先计算科目余额")
        
        income_statement = {
            "report_name": "利润表",
            "period": f"{self.period_start} 至 {self.period_end}",
            "currency": "CNY",
            "revenues": {
                "operating_revenue": Decimal(0),  # 营业收入
                "other_revenue": Decimal(0),  # 其他收入
                "total_revenue": Decimal(0)
            },
            "expenses": {
                "cost_of_sales": Decimal(0),  # 营业成本
                "operating_expenses": Decimal(0),  # 营业费用
                "admin_expenses": Decimal(0),  # 管理费用
                "financial_expenses": Decimal(0),  # 财务费用
                "other_expenses": Decimal(0),  # 其他费用
                "total_expenses": Decimal(0)
            },
            "profit": {
                "gross_profit": Decimal(0),  # 毛利润
                "operating_profit": Decimal(0),  # 营业利润
                "profit_before_tax": Decimal(0),  # 税前利润
                "net_profit": Decimal(0)  # 净利润
            }
        }
        
        # 分类汇总收入和费用
        for account_code, balance in self.account_balances.items():
            account = self._get_account_info(account_code)
            if not account:
                continue
            
            # 收入类 (6xxx)
            if account['category'] == '收入' or account_code.startswith('6'):
                if account_code[:4] in ['6001', '6051']:  # 主营业务收入
                    income_statement['revenues']['operating_revenue'] += abs(balance)
                else:  # 其他收入
                    income_statement['revenues']['other_revenue'] += abs(balance)
            
            # 费用类 (5xxx, 6xxx)
            elif account['category'] == '费用' or account_code.startswith('5'):
                if account_code[:4] == '6401':  # 主营业务成本
                    income_statement['expenses']['cost_of_sales'] += abs(balance)
                elif account_code[:4] == '6601':  # 销售费用
                    income_statement['expenses']['operating_expenses'] += abs(balance)
                elif account_code[:4] == '6602':  # 管理费用
                    income_statement['expenses']['admin_expenses'] += abs(balance)
                elif account_code[:4] == '6603':  # 财务费用
                    income_statement['expenses']['financial_expenses'] += abs(balance)
                else:
                    income_statement['expenses']['other_expenses'] += abs(balance)
        
        # 计算汇总数据
        income_statement['revenues']['total_revenue'] = (
            income_statement['revenues']['operating_revenue'] +
            income_statement['revenues']['other_revenue']
        )
        
        income_statement['expenses']['total_expenses'] = (
            income_statement['expenses']['cost_of_sales'] +
            income_statement['expenses']['operating_expenses'] +
            income_statement['expenses']['admin_expenses'] +
            income_statement['expenses']['financial_expenses'] +
            income_statement['expenses']['other_expenses']
        )
        
        # 计算利润
        income_statement['profit']['gross_profit'] = (
            income_statement['revenues']['operating_revenue'] -
            income_statement['expenses']['cost_of_sales']
        )
        
        income_statement['profit']['operating_profit'] = (
            income_statement['profit']['gross_profit'] -
            income_statement['expenses']['operating_expenses'] -
            income_statement['expenses']['admin_expenses'] -
            income_statement['expenses']['financial_expenses']
        )
        
        income_statement['profit']['profit_before_tax'] = (
            income_statement['profit']['operating_profit'] +
            income_statement['revenues']['other_revenue'] -
            income_statement['expenses']['other_expenses']
        )
        
        # 简化处理：假设税率25%
        tax = income_statement['profit']['profit_before_tax'] * Decimal('0.25')
        income_statement['profit']['net_profit'] = (
            income_statement['profit']['profit_before_tax'] - tax
        )
        
        return income_statement
    
    def generate_cash_flow_statement(self) -> Dict:
        """
        生成现金流量表
        
        Returns:
            现金流量表数据
        """
        if not self.account_balances:
            raise ValueError("请先计算科目余额")
        
        cash_flow = {
            "report_name": "现金流量表",
            "period": f"{self.period_start} 至 {self.period_end}",
            "currency": "CNY",
            "operating_activities": {
                "cash_received": Decimal(0),  # 销售商品收到的现金
                "cash_paid": Decimal(0),  # 购买商品支付的现金
                "net_cash_flow": Decimal(0)
            },
            "investing_activities": {
                "cash_received": Decimal(0),  # 收回投资收到的现金
                "cash_paid": Decimal(0),  # 购建固定资产支付的现金
                "net_cash_flow": Decimal(0)
            },
            "financing_activities": {
                "cash_received": Decimal(0),  # 吸收投资收到的现金
                "cash_paid": Decimal(0),  # 偿还债务支付的现金
                "net_cash_flow": Decimal(0)
            },
            "net_increase_in_cash": Decimal(0),
            "cash_beginning": Decimal(0),
            "cash_ending": Decimal(0)
        }
        
        # 分析现金相关科目的变动
        cash_accounts = ['1001', '1002']  # 现金和银行存款
        
        for account_code in cash_accounts:
            if account_code in self.account_balances:
                cash_flow['cash_ending'] += self.account_balances[account_code]
        
        # 简化处理：根据其他科目推算现金流
        # 实际应该分析每笔凭证的现金影响
        
        # 经营活动现金流
        if '6001' in self.account_balances:  # 主营业务收入
            cash_flow['operating_activities']['cash_received'] = abs(
                self.account_balances.get('6001', Decimal(0))
            )
        
        if '6401' in self.account_balances:  # 主营业务成本
            cash_flow['operating_activities']['cash_paid'] = abs(
                self.account_balances.get('6401', Decimal(0))
            )
        
        cash_flow['operating_activities']['net_cash_flow'] = (
            cash_flow['operating_activities']['cash_received'] -
            cash_flow['operating_activities']['cash_paid']
        )
        
        # 投资活动现金流（简化）
        cash_flow['investing_activities']['net_cash_flow'] = Decimal(0)
        
        # 筹资活动现金流（简化）
        cash_flow['financing_activities']['net_cash_flow'] = Decimal(0)
        
        # 现金净增加额
        cash_flow['net_increase_in_cash'] = (
            cash_flow['operating_activities']['net_cash_flow'] +
            cash_flow['investing_activities']['net_cash_flow'] +
            cash_flow['financing_activities']['net_cash_flow']
        )
        
        return cash_flow
    
    def _get_account_info(self, account_code: str) -> Optional[Dict]:
        """
        获取科目信息
        
        Args:
            account_code: 科目编码
            
        Returns:
            科目信息字典
        """
        try:
            account = self.db.query(Account).filter(
                Account.code == account_code
            ).first()
            
            if account:
                return {
                    'code': account.code,
                    'name': account.name,
                    'category': account.category
                }
        except:
            pass
        
        # 如果数据库中没有，使用默认映射
        default_accounts = {
            '1001': {'name': '库存现金', 'category': '资产'},
            '1002': {'name': '银行存款', 'category': '资产'},
            '1122': {'name': '应收账款', 'category': '资产'},
            '1403': {'name': '原材料', 'category': '资产'},
            '1601': {'name': '固定资产', 'category': '资产'},
            '2001': {'name': '短期借款', 'category': '负债'},
            '2202': {'name': '应付账款', 'category': '负债'},
            '2211': {'name': '应付职工薪酬', 'category': '负债'},
            '2221': {'name': '应交税费', 'category': '负债'},
            '4001': {'name': '实收资本', 'category': '所有者权益'},
            '6001': {'name': '主营业务收入', 'category': '收入'},
            '6401': {'name': '主营业务成本', 'category': '费用'},
            '6601': {'name': '销售费用', 'category': '费用'},
            '6602': {'name': '管理费用', 'category': '费用'},
            '6603': {'name': '财务费用', 'category': '费用'},
        }
        
        if account_code in default_accounts:
            return {
                'code': account_code,
                **default_accounts[account_code]
            }
        
        return None
    
    def format_report_for_display(self, report: Dict) -> str:
        """
        格式化报表用于显示
        
        Args:
            report: 报表数据
            
        Returns:
            格式化的报表字符串
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"{report['report_name']:^60}")
        lines.append(f"{report['period']:^60}")
        lines.append("=" * 60)
        
        if report['report_name'] == '资产负债表':
            lines.append("\n资产:")
            lines.append("-" * 40)
            lines.append("流动资产:")
            for name, amount in report['assets']['current_assets'].items():
                lines.append(f"  {name:30} {amount:>15,.2f}")
            lines.append("非流动资产:")
            for name, amount in report['assets']['non_current_assets'].items():
                lines.append(f"  {name:30} {amount:>15,.2f}")
            lines.append("-" * 40)
            lines.append(f"{'资产总计':30} {report['assets']['total_assets']:>15,.2f}")
            
            lines.append("\n负债和所有者权益:")
            lines.append("-" * 40)
            lines.append("流动负债:")
            for name, amount in report['liabilities']['current_liabilities'].items():
                lines.append(f"  {name:30} {amount:>15,.2f}")
            lines.append(f"{'负债合计':30} {report['liabilities']['total_liabilities']:>15,.2f}")
            
            lines.append("\n所有者权益:")
            lines.append(f"  {'实收资本':30} {report['equity']['paid_in_capital']:>15,.2f}")
            lines.append(f"  {'留存收益':30} {report['equity']['retained_earnings']:>15,.2f}")
            lines.append(f"{'所有者权益合计':30} {report['equity']['total_equity']:>15,.2f}")
            
            lines.append("-" * 40)
            lines.append(f"{'负债和所有者权益总计':30} {report['total_liabilities_and_equity']:>15,.2f}")
            
            if report['is_balanced']:
                lines.append("\n✅ 资产负债表平衡")
            else:
                lines.append("\n❌ 资产负债表不平衡")
        
        elif report['report_name'] == '利润表':
            lines.append("收入:")
            lines.append(f"  {'营业收入':30} {report['revenues']['operating_revenue']:>15,.2f}")
            lines.append(f"  {'其他收入':30} {report['revenues']['other_revenue']:>15,.2f}")
            lines.append(f"{'收入合计':30} {report['revenues']['total_revenue']:>15,.2f}")
            
            lines.append("\n费用:")
            lines.append(f"  {'营业成本':30} {report['expenses']['cost_of_sales']:>15,.2f}")
            lines.append(f"  {'销售费用':30} {report['expenses']['operating_expenses']:>15,.2f}")
            lines.append(f"  {'管理费用':30} {report['expenses']['admin_expenses']:>15,.2f}")
            lines.append(f"  {'财务费用':30} {report['expenses']['financial_expenses']:>15,.2f}")
            lines.append(f"{'费用合计':30} {report['expenses']['total_expenses']:>15,.2f}")
            
            lines.append("\n利润:")
            lines.append(f"  {'毛利润':30} {report['profit']['gross_profit']:>15,.2f}")
            lines.append(f"  {'营业利润':30} {report['profit']['operating_profit']:>15,.2f}")
            lines.append(f"  {'税前利润':30} {report['profit']['profit_before_tax']:>15,.2f}")
            lines.append(f"{'净利润':30} {report['profit']['net_profit']:>15,.2f}")
        
        elif report['report_name'] == '现金流量表':
            lines.append("经营活动现金流:")
            lines.append(f"  {'收到现金':30} {report['operating_activities']['cash_received']:>15,.2f}")
            lines.append(f"  {'支付现金':30} {report['operating_activities']['cash_paid']:>15,.2f}")
            lines.append(f"{'经营活动净现金流':30} {report['operating_activities']['net_cash_flow']:>15,.2f}")
            
            lines.append("\n现金及现金等价物:")
            lines.append(f"  {'期初余额':30} {report['cash_beginning']:>15,.2f}")
            lines.append(f"  {'净增加额':30} {report['net_increase_in_cash']:>15,.2f}")
            lines.append(f"{'期末余额':30} {report['cash_ending']:>15,.2f}")
        
        lines.append("=" * 60)
        return "\n".join(lines)