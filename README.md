# 🤖 AI会计师 - 智能发票处理系统

一个基于大语言模型和RAG技术的智能会计分录生成系统，能够自动处理发票文档并生成标准的会计分录。

## ✨ 核心特性

- **📄 智能文档解析**: 支持PDF发票的自动文本提取
- **🧠 AI信息提取**: 使用GPT-4从发票中提取关键业务信息  
- **📊 业务标准化**: 将复杂的业务描述标准化为规范的会计术语
- **🔍 知识检索**: 基于RAG技术检索相关会计准则
- **⚙️ 智能分录生成**: 自动生成符合会计准则的记账凭证
- **🎯 质量评估**: 多层次置信度评估，确保结果可靠性

## 🏗️ 系统架构

```
📄 发票文档 → 🔧 文档解析 → 🤖 AI信息提取 → 📊 业务标准化 → 🔍 知识检索 → ⚙️ 分录生成 → 💾 数据存储
```

### 核心模块

- **文档处理器**: 统一的发票处理流水线
- **业务分析器**: 智能业务描述标准化
- **知识检索器**: RAG-based会计准则检索
- **凭证生成器**: 智能会计分录生成
- **配置管理**: 统一的环境配置管理

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <project-url>
cd ai_accountant

# 创建Python虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# AI服务配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4-1106-preview
OPENAI_TEMPERATURE=0.1

# 嵌入模型配置（推荐中文场景）
EMBEDDING_PROVIDER=dashscope
DASHSCOPE_API_KEY=your_dashscope_api_key_here
EMBEDDING_MODEL=text-embedding-v4

# 数据库配置
DATABASE_URL=sqlite:///./data/accounting.db

# 应用配置
DEBUG=true
LOG_LEVEL=INFO
```

### 3. 系统初始化

```bash
# 初始化系统（创建数据库、知识库等）
python main.py init
```

### 4. 处理发票

```bash
# 处理单个发票
python main.py process invoice.pdf

# 处理多个发票
python main.py process invoice1.pdf invoice2.pdf

# 指定会计分录日期
python main.py process --date 2024-03-20 invoice.pdf

# 显示详细信息
python main.py process --verbose invoice.pdf

# 保存结果到文件
python main.py process --output results.json invoice.pdf
```

## 📊 使用示例

### 处理单个发票

```python
from app.services.document_processor import process_single_document

# 处理发票并生成会计分录
result = process_single_document("invoice.pdf", "2024-03-20")

print(f"处理状态: {result.processing_status}")
print(f"置信度: {result.final_confidence}")

if result.journal_entry:
    print(f"借方: {result.journal_entry.debit_account_code} {result.journal_entry.debit_account_name}")
    print(f"贷方: {result.journal_entry.credit_account_code} {result.journal_entry.credit_account_name}")
    print(f"金额: {result.journal_entry.amount}")
```

### 批量处理发票

```python
from app.services.document_processor import process_multiple_documents

# 批量处理多个发票
results = process_multiple_documents([
    "invoice1.pdf", 
    "invoice2.pdf", 
    "invoice3.pdf"
], "2024-03-20")

# 统计处理结果
success_count = sum(1 for r in results if r.processing_status.value == 'success')
print(f"成功处理: {success_count}/{len(results)}")
```

## 🔧 系统管理

```bash
# 查看系统状态
python main.py status

# 运行系统测试
python main.py test

# 重置系统
python scripts/system_manager.py reset
```

## 📁 项目结构

```
ai_accountant/
├── app/                     # 核心应用代码
│   ├── core/               # 核心配置管理
│   │   └── config.py       # 统一配置管理
│   ├── models/             # 数据库模型
│   │   └── accounting.py   # 会计科目模型
│   ├── schemas/            # 数据结构定义
│   │   └── __init__.py     # Pydantic数据模型
│   ├── services/           # 业务服务层
│   │   ├── ai_service.py           # AI信息提取服务
│   │   ├── business_standardizer.py # 业务标准化服务
│   │   ├── document_processor.py   # 文档处理编排
│   │   ├── journal_generator.py    # 凭证生成服务
│   │   └── rag_service.py          # RAG检索服务
│   └── utils/              # 工具类
│       ├── __init__.py
│       └── file_parser.py  # 文件解析器
├── config/                 # 配置文件
│   └── accounting_rules.txt # 会计准则库
├── data/                   # 数据存储
│   ├── accounting.db       # SQLite数据库
│   ├── invoice_sample.pdf  # 示例发票
│   ├── uploads/            # 上传文件目录
│   └── vector_store/       # 向量存储
├── logs/                   # 日志文件
├── scripts/                # 管理脚本
│   ├── init_database.py    # 数据库初始化
│   ├── system_manager.py   # 系统管理
│   └── verify_database.py  # 数据库验证
├── test_results/           # 测试结果
├── env.example             # 环境配置示例
├── main.py                 # 主程序入口
├── requirements.txt        # 依赖列表
├── README.md              # 项目说明
└── 使用示例.md            # 使用示例
```

## 🎯 置信度评估

系统使用多层次置信度评估机制：

- **高置信度 (≥0.8)**: 自动通过，可直接使用
- **中等置信度 (0.6-0.8)**: 建议人工审核
- **低置信度 (<0.6)**: 需要人工处理

## 🔍 支持的业务场景

### 收入业务
- 银行转账收货款
- 现金销售商品
- 应收账款回收

### 费用业务  
- 支付办公室房租
- 支付水电费用
- 支付广告费用
- 银行手续费

### 采购业务
- 采购商品入库
- 购买固定资产
- 预付款项

### 薪酬业务
- 计提员工工资
- 发放工资

## 🛠️ 技术栈

- **AI模型**: GPT-4, 通义千问embedding
- **RAG框架**: LangChain + FAISS
- **数据库**: SQLAlchemy + SQLite
- **文档解析**: pdfplumber
- **数据验证**: Pydantic
- **配置管理**: python-dotenv

## 📝 开发说明

### 添加新的业务规则

编辑 `config/accounting_rules.txt` 文件，按照以下格式添加：

```
规则A01: 新业务场景描述
关键词: 关键词1、关键词2、关键词3
业务分析: 这种业务的会计处理逻辑
会计处理:
  借记: 科目编码 科目名称 (金额说明)
  贷记: 科目编码 科目名称 (金额说明)
```

### 扩展文件格式支持

在 `app/utils/file_parser.py` 中添加新的解析器：

```python
class NewFormatParser:
    def parse(self, file_path):
        # 实现新格式的解析逻辑
        pass
```

## 🚧 注意事项

1. **API密钥安全**: 请妥善保管您的API密钥，不要提交到版本控制
2. **数据隐私**: 发票可能包含敏感信息，请确保合规使用
3. **结果审核**: AI生成的会计分录仅供参考，重要业务请人工审核
4. **系统限制**: 当前版本仅支持简单的单借单贷分录

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 📞 支持

如有问题或建议，请：

1. 查看 [文档](docs/)
2. 提交 [Issue](../../issues)
3. 联系维护者

---

**⚠️ 免责声明**: 本系统生成的会计分录仅供参考，不构成专业会计建议。在实际业务中使用前，请咨询专业会计师或相关专家。