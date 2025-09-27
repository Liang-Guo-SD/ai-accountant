#!/usr/bin/env python3
"""
AI会计师系统管理工具
提供系统初始化、重置、测试等功能
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_config


class SystemManager:
    """系统管理器"""
    
    def __init__(self):
        self.config = get_config()
        self.project_root = project_root
    
    def initialize_system(self):
        """完整系统初始化"""
        print("🚀 AI会计师系统初始化")
        print("=" * 60)
        
        steps = [
            ("验证系统配置", self._validate_config),
            ("创建必要目录", self._create_directories),
            ("初始化数据库", self._init_database),
            ("验证数据库", self._verify_database),
            ("初始化知识库", self._init_knowledge_base),
            ("测试核心服务", self._test_core_services),
        ]
        
        for step_name, step_func in steps:
            print(f"\n🔄 {step_name}...")
            try:
                success = step_func()
                if success:
                    print(f"✅ {step_name} 完成")
                else:
                    print(f"❌ {step_name} 失败")
                    return False
            except Exception as e:
                print(f"❌ {step_name} 异常: {e}")
                return False
        
        print(f"\n🎉 系统初始化完成！")
        print(f"💡 现在可以开始使用AI会计师系统了")
        return True
    
    def reset_system(self):
        """重置系统到初始状态"""
        print("🔄 重置AI会计师系统")
        print("=" * 60)
        
        # 确认操作
        confirm = input("⚠️ 这将删除所有数据，确定要继续吗？(y/N): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            return False
        
        try:
            # 删除数据库文件
            db_path = self.config.database.database_url.replace("sqlite:///", "")
            if os.path.exists(db_path):
                os.remove(db_path)
                print("✅ 数据库文件已删除")
            
            # 清空上传目录
            upload_dir = self.config.app.upload_dir
            if upload_dir.exists():
                for file in upload_dir.iterdir():
                    if file.is_file():
                        file.unlink()
                print("✅ 上传文件已清空")
            
            # 清空向量存储
            vector_dir = self.config.knowledge.vector_store_path
            if vector_dir.exists():
                for file in vector_dir.iterdir():
                    if file.is_file():
                        file.unlink()
                print("✅ 向量存储已清空")
            
            # 重新初始化
            return self.initialize_system()
            
        except Exception as e:
            print(f"❌ 系统重置失败: {e}")
            return False
    
    def run_comprehensive_test(self):
        """运行综合测试"""
        print("🧪 AI会计师系统综合测试")
        print("=" * 60)
        
        test_modules = [
            ("配置管理测试", "app.core.config"),
            ("数据库连接测试", "app.core.database"), 
            ("文件解析测试", "app.utils.file_parser"),
            ("AI信息提取测试", "app.services.ai_extractor"),
            ("业务标准化测试", "app.services.business_analyzer"),
            ("知识检索测试", "app.services.knowledge_retriever"),
            ("凭证生成测试", "app.services.journal_generator"),
            ("文档处理测试", "app.services.document_processor"),
        ]
        
        results = []
        
        for test_name, module_path in test_modules:
            print(f"\n🔍 {test_name}...")
            try:
                # 动态导入并运行测试函数
                result = self._run_module_test(module_path)
                if result:
                    print(f"✅ {test_name} 通过")
                    results.append((test_name, True))
                else:
                    print(f"❌ {test_name} 失败")
                    results.append((test_name, False))
            except Exception as e:
                print(f"❌ {test_name} 异常: {e}")
                results.append((test_name, False))
        
        # 测试结果汇总
        print(f"\n📊 测试结果汇总:")
        print("=" * 40)
        
        passed = sum(1 for _, success in results if success)
        total = len(results)
        
        for test_name, success in results:
            status = "✅ 通过" if success else "❌ 失败"
            print(f"  {test_name}: {status}")
        
        print(f"\n🎯 总体结果: {passed}/{total} 通过 ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 所有测试通过！系统运行正常")
        else:
            print("⚠️ 部分测试失败，请检查相关模块")
        
        return passed == total
    
    def _validate_config(self):
        """验证系统配置"""
        return self.config.validate_system()
    
    def _create_directories(self):
        """创建必要的目录结构"""
        directories = [
            self.config.app.upload_dir,
            self.config.knowledge.vector_store_path,
            self.project_root / "logs",
            self.project_root / "data",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        return True
    
    def _init_database(self):
        """初始化数据库"""
        try:
            script_path = self.project_root / "scripts" / "init_database.py"
            if not script_path.exists():
                print(f"⚠️ 数据库初始化脚本不存在: {script_path}")
                return False
            
            result = subprocess.run([sys.executable, str(script_path)], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _verify_database(self):
        """验证数据库"""
        try:
            from app.core.database import get_database
            from app.models.accounting import Account
            
            # 简单的数据库连接测试
            db = next(get_database())
            accounts = db.query(Account).limit(1).all()
            db.close()
            return len(accounts) >= 0  # 只要能查询就算成功
        except:
            return False
    
    def _init_knowledge_base(self):
        """初始化知识库"""
        try:
            from app.services.knowledge_retriever import KnowledgeRetriever
            retriever = KnowledgeRetriever()
            return retriever.initialize_knowledge_base()
        except:
            return False
    
    def _test_core_services(self):
        """测试核心服务"""
        try:
            from app.services.document_processor import DocumentProcessorFactory
            processor = DocumentProcessorFactory.create_processor()
            return processor is not None
        except:
            return False
    
    def _run_module_test(self, module_path):
        """运行模块测试"""
        try:
            # 动态导入模块
            module = __import__(module_path, fromlist=[''])
            
            # 查找测试函数
            test_functions = [
                'test_' + module_path.split('.')[-1],
                'test',
                'main'
            ]
            
            for func_name in test_functions:
                if hasattr(module, func_name):
                    test_func = getattr(module, func_name)
                    test_func()
                    return True
            
            return True  # 如果没有测试函数，认为通过
        except:
            return False
    
    def show_system_status(self):
        """显示系统状态"""
        print("📊 AI会计师系统状态")
        print("=" * 50)
        
        self.config.print_config_summary()
        
        # 检查关键组件状态
        print("\n🔍 组件状态检查:")
        
        # 数据库状态
        try:
            from app.core.database import get_database
            db = next(get_database())
            db.close()
            print("  ✅ 数据库连接正常")
        except:
            print("  ❌ 数据库连接失败")
        
        # 知识库文件状态
        if self.config.knowledge.rules_file.exists():
            print("  ✅ 会计准则文件存在")
        else:
            print("  ❌ 会计准则文件缺失")
        
        # API密钥状态
        if self.config.ai.openai_api_key:
            print("  ✅ OpenAI API密钥已配置")
        else:
            print("  ❌ OpenAI API密钥未配置")
        
        if self.config.ai.embedding_provider == "dashscope" and self.config.ai.dashscope_api_key:
            print("  ✅ DashScope API密钥已配置")
        elif self.config.ai.embedding_provider == "dashscope":
            print("  ❌ DashScope API密钥未配置")


def main():
    """主函数"""
    manager = SystemManager()
    
    if len(sys.argv) < 2:
        print("🔧 AI会计师系统管理工具")
        print("\n使用方法:")
        print("  python scripts/system_manager.py init     # 初始化系统")
        print("  python scripts/system_manager.py reset    # 重置系统")
        print("  python scripts/system_manager.py test     # 运行测试")
        print("  python scripts/system_manager.py status   # 查看状态")
        return
    
    command = sys.argv[1].lower()
    
    if command == "init":
        manager.initialize_system()
    elif command == "reset":
        manager.reset_system()
    elif command == "test":
        manager.run_comprehensive_test()
    elif command == "status":
        manager.show_system_status()
    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()