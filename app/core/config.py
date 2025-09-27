"""
AI会计师 - 统一配置管理
集中管理所有系统配置，支持多环境部署
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


class DatabaseConfig:
    """数据库配置"""
    
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT}/data/accounting.db")
        self.echo_sql = os.getenv("DATABASE_ECHO", "false").lower() == "true"
        
        # 确保数据库目录存在
        db_path = self.database_url.replace("sqlite:///", "")
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)


class AIConfig:
    """AI服务配置"""
    
    def __init__(self):
        # 主要LLM配置
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4-1106-preview")
        self.openai_temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
        
        # 嵌入模型配置
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", "dashscope").lower()
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
        
        # 性能配置
        self.max_tokens = self._get_optional_int("OPENAI_MAX_TOKENS")
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))
        self.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
        
        # 验证必需参数
        self._validate_config()
    
    def _get_optional_int(self, key: str) -> Optional[int]:
        """获取可选的整数配置"""
        value = os.getenv(key)
        return int(value) if value else None
    
    def _validate_config(self):
        """验证配置完整性"""
        errors = []
        
        if not self.openai_api_key:
            errors.append("缺少 OPENAI_API_KEY")
        
        if self.embedding_provider == "dashscope" and not self.dashscope_api_key:
            errors.append("使用 DashScope 时需要设置 DASHSCOPE_API_KEY")
        
        if errors:
            raise ValueError(f"配置验证失败: {'; '.join(errors)}")


class AppConfig:
    """应用程序配置"""
    
    def __init__(self):
        self.app_name = os.getenv("APP_NAME", "AI Accountant")
        self.app_version = os.getenv("APP_VERSION", "2.0.0")
        self.debug = os.getenv("DEBUG", "true").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # 文件处理配置
        self.max_file_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", f"{PROJECT_ROOT}/data/uploads"))
        self.supported_formats = [".pdf", ".xlsx", ".xls"]
        
        # 确保上传目录存在
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 业务配置
        self.confidence_threshold_high = float(os.getenv("CONFIDENCE_HIGH", "0.8"))
        self.confidence_threshold_medium = float(os.getenv("CONFIDENCE_MEDIUM", "0.6"))


class KnowledgeConfig:
    """知识库配置"""
    
    def __init__(self):
        self.rules_file = Path(os.getenv("RULES_FILE", f"{PROJECT_ROOT}/config/accounting_rules.txt"))
        self.vector_store_path = Path(os.getenv("VECTOR_STORE", f"{PROJECT_ROOT}/data/vector_store"))
        
        # RAG配置
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        self.top_k_results = int(os.getenv("TOP_K_RESULTS", "3"))
        
        # 确保目录存在
        self.vector_store_path.mkdir(parents=True, exist_ok=True)


class SystemConfig:
    """系统统一配置类"""
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.ai = AIConfig()
        self.app = AppConfig()
        self.knowledge = KnowledgeConfig()
        
        # 配置日志
        self._setup_logging()
    
    def _setup_logging(self):
        """配置系统日志"""
        log_level = getattr(logging, self.app.log_level.upper())
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(f"{PROJECT_ROOT}/logs/app.log", encoding='utf-8')
            ] if not self.app.debug else [logging.StreamHandler()]
        )
        
        # 确保日志目录存在
        log_dir = Path(f"{PROJECT_ROOT}/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("⚙️  AI会计师系统配置")
        print("=" * 50)
        print(f"📱 应用名称: {self.app.app_name} v{self.app.app_version}")
        print(f"🐛 调试模式: {self.app.debug}")
        print(f"📊 日志级别: {self.app.log_level}")
        print()
        print(f"🤖 主要模型: {self.ai.openai_model}")
        print(f"🌡️  模型温度: {self.ai.openai_temperature}")
        print(f"🔗 嵌入提供商: {self.ai.embedding_provider}")
        print(f"📝 嵌入模型: {self.ai.embedding_model}")
        print()
        print(f"💾 数据库: {self.database.database_url}")
        print(f"📚 知识库: {self.knowledge.rules_file}")
        print(f"📁 上传目录: {self.app.upload_dir}")
        print()
        print(f"🎯 置信度阈值: 高>{self.app.confidence_threshold_high}, 中>{self.app.confidence_threshold_medium}")
        print("=" * 50)
    
    def validate_system(self) -> bool:
        """验证系统配置完整性"""
        try:
            # 验证关键文件存在
            if not self.knowledge.rules_file.exists():
                raise FileNotFoundError(f"会计准则文件不存在: {self.knowledge.rules_file}")
            
            # 验证API密钥
            if not self.ai.openai_api_key:
                raise ValueError("OpenAI API密钥未配置")
            
            print("✅ 系统配置验证通过")
            return True
            
        except Exception as e:
            print(f"❌ 系统配置验证失败: {e}")
            return False


# 全局配置实例
config = SystemConfig()


def get_config() -> SystemConfig:
    """获取全局配置实例"""
    return config


# 为了向后兼容，保留旧的获取方式
def get_ai_config() -> AIConfig:
    """获取AI配置"""
    return config.ai


def get_db_config() -> DatabaseConfig:
    """获取数据库配置"""
    return config.database


def get_app_config() -> AppConfig:
    """获取应用配置"""
    return config.app


if __name__ == "__main__":
    # 测试配置
    config.print_config_summary()
    config.validate_system()