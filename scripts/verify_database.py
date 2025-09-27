#!/usr/bin/env python3
"""
数据库验证脚本
查看数据库中的数据，确保初始化成功
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import SessionLocal
from app.models.accounting import Account


def verify_accounts():
    """验证会计科目数据"""
    db = SessionLocal()
    
    try:
        print("🔍 查询数据库中的会计科目...")
        print("=" * 60)
        
        # 查询所有科目
        accounts = db.query(Account).order_by(Account.code).all()
        
        if not accounts:
            print("❌ 数据库中没有找到任何科目数据")
            return
        
        print(f"✅ 找到 {len(accounts)} 个科目:\n")
        
        # 按类别分组显示
        current_category = None
        for account in accounts:
            if account.category != current_category:
                current_category = account.category
                print(f"\n📂 {current_category}类科目:")
                print("-" * 30)
            
            print(f"  {account.code} - {account.name}")
        
        print("\n" + "=" * 60)
        print("✅ 数据库验证完成")
        
    except Exception as e:
        print(f"❌ 查询数据库时出错: {e}")
    finally:
        db.close()


def main():
    """主函数"""
    print("🔍 开始验证数据库...")
    verify_accounts()


if __name__ == "__main__":
    main()