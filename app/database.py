"""
数据库配置和连接管理
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库URL，从环境变量读取，如果没有则使用默认值
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/accounting.db")

print(f"📊 连接数据库: {DATABASE_URL}")

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite需要这个参数
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 数据库基类
Base = declarative_base()


def get_database():
    """
    获取数据库会话
    这是一个生成器函数，确保数据库连接能够正确关闭
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    创建所有数据表
    这个函数会读取所有模型并在数据库中创建对应的表
    """
    print("🔨 创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")


def init_database():
    """
    初始化数据库
    创建所有必要的表和初始数据
    """
    print("🚀 初始化数据库...")
    
    # 确保数据目录存在
    import os
    from pathlib import Path
    
    db_path = DATABASE_URL.replace("sqlite:///", "")
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建表
    create_tables()
    
    # 导入模型以确保它们被注册
    try:
        from app.models.accounting import Account
        print("✅ 数据库初始化完成")
        return True
    except ImportError as e:
        print(f"⚠️ 模型导入失败: {e}")
        return False