#!/usr/bin/env python3
"""
数据库初始化脚本
读取会计规则文件，并将科目数据写入数据库
"""

import sys
import os
import re
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import engine, SessionLocal, create_tables
from app.models.accounting import Account  # 这会触发模型的注册


def parse_accounting_rules(rules_file_path: str):
    """
    解析会计规则文件，提取科目信息
    
    Args:
        rules_file_path: 规则文件路径
    
    Returns:
        list: 包含科目信息的字典列表
    """
    accounts = []
    
    print(f"📖 读取规则文件: {rules_file_path}")
    
    try:
        with open(rules_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        print(f"❌ 文件不存在: {rules_file_path}")
        return accounts
    
    # 使用正则表达式匹配科目行
    # 格式：1001 库存现金 - 记录企业的现金
    pattern = r'(\d{4})\s+([^\s]+)\s+-\s+(.+)'
    matches = re.findall(pattern, content)
    
    for match in matches:
        code, name, description = match
        
        # 根据科目编码确定类别
        if code.startswith('1'):
            category = '资产'
        elif code.startswith('2'):
            category = '负债'  
        elif code.startswith('3'):
            category = '所有者权益'
        elif code.startswith('6') and int(code) < 6400:
            category = '收入'
        else:
            category = '费用'
            
        accounts.append({
            'code': code,
            'name': name,
            'category': category,
            'description': description.strip()
        })
    
    print(f"✅ 解析完成，找到 {len(accounts)} 个科目")
    return accounts


def init_accounts(accounts_data: list):
    """
    将科目数据写入数据库
    
    Args:
        accounts_data: 科目数据列表
    """
    db = SessionLocal()
    
    try:
        print("💾 写入科目数据到数据库...")
        
        for account_info in accounts_data:
            # 检查科目是否已存在
            existing = db.query(Account).filter(Account.code == account_info['code']).first()
            
            if existing:
                print(f"⚠️  科目 {account_info['code']} 已存在，跳过")
                continue
                
            # 创建新科目
            account = Account(
                code=account_info['code'],
                name=account_info['name'],
                category=account_info['category']
            )
            
            db.add(account)
            print(f"✅ 添加科目: {account.full_name}")
        
        db.commit()
        print("💾 科目数据写入完成")
        
    except Exception as e:
        print(f"❌ 写入数据库时出错: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """主函数"""
    print("🚀 开始初始化数据库...")
    print("=" * 50)
    
    # 1. 创建数据表
    create_tables()
    
    # 2. 读取和解析规则文件
    rules_file = project_root / "config" / "accounting_rules.txt"
    accounts = parse_accounting_rules(str(rules_file))
    
    # 3. 写入科目数据
    if accounts:
        init_accounts(accounts)
    
    print("=" * 50)
    print("🎉 数据库初始化完成！")


if __name__ == "__main__":
    main()