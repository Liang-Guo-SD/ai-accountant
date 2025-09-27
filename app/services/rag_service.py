"""
RAG检索服务
基于会计准则文档构建智能检索系统
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import logging

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import DashScopeEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from app.core.config import get_ai_config

logger = logging.getLogger(__name__)


class AccountingRAGService:
    """
    会计准则RAG检索服务
    将会计知识向量化，支持智能检索
    """
    
    def __init__(self, rules_file_path: str = None):
        """
        初始化RAG服务
        
        Args:
            rules_file_path: 会计准则文件路径
        """
        self.config = get_ai_config()
        
        # 设置默认规则文件路径
        if rules_file_path is None:
            rules_file_path = project_root / "config" / "accounting_rules.txt"
        
        self.rules_file_path = rules_file_path
        # 初始化组件
        self.embeddings = DashScopeEmbeddings(
            model=self.config.embedding_model,
            dashscope_api_key=self.config.dashscope_api_key,
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,  # 每个文本块的大小
            chunk_overlap=50,  # 文本块之间的重叠
            separators=["\n\n", "\n", "。", "；", " "]  # 分割符优先级
        )
        
        self.vector_store = None
        
        logger.info("🔍 RAG检索服务初始化完成")
    
    def load_and_index_rules(self) -> bool:
        """
        加载并索引会计准则文档
        
        Returns:
            bool: 是否成功建立索引
        """
        try:
            logger.info(f"📚 加载会计准则文档: {self.rules_file_path}")
            
            # 读取规则文件
            if not os.path.exists(self.rules_file_path):
                raise FileNotFoundError(f"规则文件不存在: {self.rules_file_path}")
            
            with open(self.rules_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 文本分割
            logger.info("✂️ 分割文本为块...")
            texts = self.text_splitter.split_text(content)
            
            # 创建文档对象
            documents = [
                Document(
                    page_content=text,
                    metadata={
                        "source": "accounting_rules",
                        "chunk_id": i,
                        "file_path": str(self.rules_file_path)
                    }
                )
                for i, text in enumerate(texts)
            ]
            
            logger.info(f"📄 创建了 {len(documents)} 个文档块")
            
            # 创建向量存储
            logger.info("🔮 创建向量索引...")
            self.vector_store = FAISS.from_documents(
                documents=documents,
                embedding=self.embeddings
            )
            
            logger.info("✅ 会计准则索引建立完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 建立索引失败: {e}")
            return False
    
    def search_relevant_rules(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        检索与查询相关的会计准则
        
        Args:
            query: 查询文本（业务描述）
            k: 返回的相关文档数量
            
        Returns:
            list: 相关的会计准则列表
        """
        if self.vector_store is None:
            logger.warning("⚠️ 向量存储未初始化，尝试加载...")
            if not self.load_and_index_rules():
                return []
        
        try:
            logger.info(f"🔍 检索相关规则: {query}")
            
            # 执行相似性搜索
            docs = self.vector_store.similarity_search_with_score(query, k=k)
            
            # 格式化结果
            results = []
            for doc, score in docs:
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": float(score),
                    "summary": doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
                })
            
            logger.info(f"✅ 找到 {len(results)} 条相关规则")
            return results
            
        except Exception as e:
            logger.error(f"❌ 检索失败: {e}")
            return []
    
    def get_context_for_business(self, business_description: str) -> str:
        """
        根据业务描述获取上下文信息
        
        Args:
            business_description: 业务描述
            
        Returns:
            str: 相关的会计准则上下文
        """
        relevant_rules = self.search_relevant_rules(business_description, k=3)
        
        if not relevant_rules:
            return "未找到相关的会计准则。"
        
        context_parts = []
        for i, rule in enumerate(relevant_rules, 1):
            context_parts.append(f"相关准则 {i}:\n{rule['content']}")
        
        return "\n\n".join(context_parts)


def test_rag_service():
    """测试RAG服务"""
    print("🧪 测试RAG检索服务")
    print("=" * 50)
    
    try:
        # 初始化服务
        rag_service = AccountingRAGService()
        
        # 建立索引
        print("📚 建立会计准则索引...")
        if not rag_service.load_and_index_rules():
            print("❌ 索引建立失败")
            return
        
        # 测试查询
        test_queries = [
            "收到银行存款",
            "支付房租费用", 
            "销售商品收入",
            "购买固定资产"
        ]
        
        for query in test_queries:
            print(f"\n🔍 查询: '{query}'")
            print("-" * 30)
            
            results = rag_service.search_relevant_rules(query, k=2)
            
            if results:
                for i, result in enumerate(results, 1):
                    print(f"📋 相关规则 {i} (相似度: {result['relevance_score']:.3f}):")
                    print(f"   {result['summary']}")
            else:
                print("   未找到相关规则")
        
        print("\n✅ RAG服务测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print("💡 请检查:")
        print("1. OPENAI_API_KEY 是否正确设置")
        print("2. accounting_rules.txt 文件是否存在")
        print("3. 网络连接是否正常")


if __name__ == "__main__":
    test_rag_service()