#!/usr/bin/env python3
"""
AI会计师 - 智能发票处理系统
主程序入口，提供命令行界面
"""

import sys
import os
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.config import get_config, config
from app.services.document_processor import process_single_document, process_multiple_documents
from app.services.rag_service import AccountingRAGService
from app.database import init_database
from scripts.system_manager import SystemManager

# 创建Typer应用
app = typer.Typer(
    name="ai-accountant",
    help="🤖 AI会计师 - 智能发票处理系统",
    add_completion=False
)

# 创建Rich控制台
console = Console()

@app.command()
def init():
    """初始化系统（创建数据库、知识库等）"""
    console.print("🚀 初始化AI会计师系统...", style="bold blue")
    
    try:
        # 验证配置
        if not config.validate_system():
            console.print("❌ 系统配置验证失败", style="bold red")
            raise typer.Exit(1)
        
        # 初始化数据库
        console.print("📊 初始化数据库...")
        init_database()
        
        # 初始化RAG服务
        console.print("🔍 初始化知识库...")
        rag_service = AccountingRAGService()
        if rag_service.load_and_index_rules():
            console.print("✅ 知识库索引建立成功", style="bold green")
        else:
            console.print("⚠️ 知识库索引建立失败，但系统仍可运行", style="bold yellow")
        
        console.print("🎉 系统初始化完成！", style="bold green")
        
    except Exception as e:
        console.print(f"❌ 初始化失败: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def process(
    files: List[str] = typer.Argument(..., help="要处理的文件路径"),
    date: Optional[str] = typer.Option(None, "--date", "-d", help="会计分录日期 (YYYY-MM-DD)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出结果到文件"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示详细信息")
):
    """处理发票文档并生成会计分录"""
    
    if not files:
        console.print("❌ 请提供要处理的文件路径", style="bold red")
        raise typer.Exit(1)
    
    # 验证文件存在
    valid_files = []
    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            console.print(f"⚠️ 文件不存在: {file_path}", style="yellow")
        else:
            valid_files.append(path)
    
    if not valid_files:
        console.print("❌ 没有找到有效的文件", style="bold red")
        raise typer.Exit(1)
    
    console.print(f"📄 开始处理 {len(valid_files)} 个文件...", style="bold blue")
    
    # 处理文件
    if len(valid_files) == 1:
        # 单个文件处理
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("处理文档...", total=None)
            result = process_single_document(valid_files[0], date)
            progress.update(task, completed=True)
    else:
        # 批量处理
        results = process_multiple_documents(valid_files, date)
    
    # 显示结果
    if len(valid_files) == 1:
        _display_single_result(result, verbose)
    else:
        _display_batch_results(results, verbose)
    
    # 保存结果到文件
    if output:
        _save_results_to_file(results if len(valid_files) > 1 else [result], output)

@app.command()
def status():
    """查看系统状态"""
    console.print("📊 AI会计师系统状态", style="bold blue")
    
    try:
        # 显示配置信息
        config.print_config_summary()
        
        # 检查数据库
        console.print("\n🔍 检查系统组件...")
        
        # 检查RAG服务
        rag_service = AccountingRAGService()
        if rag_service.load_and_index_rules():
            console.print("✅ 知识库: 正常", style="green")
        else:
            console.print("⚠️ 知识库: 异常", style="yellow")
        
        # 检查数据库连接
        try:
            from app.database import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            console.print("✅ 数据库: 正常", style="green")
        except Exception as e:
            console.print(f"❌ 数据库: 异常 - {e}", style="red")
        
    except Exception as e:
        console.print(f"❌ 状态检查失败: {e}", style="bold red")

@app.command()
def test():
    """运行系统测试"""
    console.print("🧪 运行系统测试...", style="bold blue")
    
    try:
        # 测试配置
        console.print("1. 测试配置...")
        if config.validate_system():
            console.print("✅ 配置测试通过", style="green")
        else:
            console.print("❌ 配置测试失败", style="red")
            return
        
        # 测试AI服务
        console.print("2. 测试AI服务...")
        from app.services.ai_service import test_ai_extraction
        test_ai_extraction()
        
        # 测试RAG服务
        console.print("3. 测试RAG服务...")
        from app.services.rag_service import test_rag_service
        test_rag_service()
        
        # 测试凭证生成
        console.print("4. 测试凭证生成...")
        from app.services.journal_generator import test_journal_generator
        test_journal_generator()
        
        console.print("🎉 所有测试完成！", style="bold green")
        
    except Exception as e:
        console.print(f"❌ 测试失败: {e}", style="bold red")
        import traceback
        traceback.print_exc()

def _display_single_result(result, verbose: bool):
    """显示单个处理结果"""
    console.print("\n📋 处理结果", style="bold blue")
    
    # 基本信息
    table = Table(title="文档信息")
    table.add_column("项目", style="cyan")
    table.add_column("值", style="white")
    
    table.add_row("文件名", result.file_name)
    table.add_row("文件大小", f"{result.file_size} 字节")
    table.add_row("处理状态", result.processing_status.value)
    table.add_row("置信度", f"{result.final_confidence:.3f}")
    table.add_row("需要审核", "是" if result.needs_review else "否")
    table.add_row("处理时间", f"{result.processing_time:.2f} 秒")
    
    console.print(table)
    
    # 详细信息
    if verbose and result.journal_entry:
        console.print("\n📊 会计分录", style="bold blue")
        journal = result.journal_entry
        
        journal_table = Table()
        journal_table.add_column("项目", style="cyan")
        journal_table.add_column("值", style="white")
        
        journal_table.add_row("业务描述", journal.business_description)
        journal_table.add_row("分录日期", journal.entry_date)
        journal_table.add_row("借方", f"{journal.debit_account_code} {journal.debit_account_name}")
        journal_table.add_row("贷方", f"{journal.credit_account_code} {journal.credit_account_name}")
        journal_table.add_row("金额", f"¥{journal.amount:,.2f}")
        journal_table.add_row("置信度", f"{journal.confidence_score:.3f}")
        journal_table.add_row("验证结果", journal.validation_notes)
        
        console.print(journal_table)
        
        if verbose:
            console.print(f"\n🔍 分析过程:\n{journal.analysis_process}")
            console.print(f"\n📚 应用规则:\n{journal.applied_rules}")

def _display_batch_results(results, verbose: bool):
    """显示批量处理结果"""
    console.print(f"\n📊 批量处理结果 ({len(results)} 个文件)", style="bold blue")
    
    # 统计信息
    success_count = sum(1 for r in results if r.processing_status.value == 'success')
    console.print(f"✅ 成功: {success_count}/{len(results)}")
    console.print(f"❌ 失败: {len(results) - success_count}/{len(results)}")
    
    # 详细结果表格
    if verbose:
        table = Table(title="详细结果")
        table.add_column("文件名", style="cyan")
        table.add_column("状态", style="white")
        table.add_column("置信度", style="white")
        table.add_column("需要审核", style="white")
        
        for result in results:
            status_color = "green" if result.processing_status.value == 'success' else "red"
            table.add_row(
                result.file_name,
                f"[{status_color}]{result.processing_status.value}[/{status_color}]",
                f"{result.final_confidence:.3f}",
                "是" if result.needs_review else "否"
            )
        
        console.print(table)

def _save_results_to_file(results, output_path: str):
    """保存结果到文件"""
    import json
    from datetime import datetime
    
    # 转换为可序列化的格式
    serializable_results = []
    for result in results:
        result_dict = {
            "file_name": result.file_name,
            "file_path": result.file_path,
            "file_size": result.file_size,
            "processing_status": result.processing_status.value,
            "final_confidence": result.final_confidence,
            "needs_review": result.needs_review,
            "processing_time": result.processing_time,
            "error_message": getattr(result, 'error_message', None)
        }
        
        if result.journal_entry:
            result_dict["journal_entry"] = {
                "business_description": result.journal_entry.business_description,
                "entry_date": result.journal_entry.entry_date,
                "debit_account_code": result.journal_entry.debit_account_code,
                "debit_account_name": result.journal_entry.debit_account_name,
                "credit_account_code": result.journal_entry.credit_account_code,
                "credit_account_name": result.journal_entry.credit_account_name,
                "amount": result.journal_entry.amount,
                "confidence_score": result.journal_entry.confidence_score,
                "is_balanced": result.journal_entry.is_balanced,
                "validation_notes": result.journal_entry.validation_notes,
                "analysis_process": result.journal_entry.analysis_process,
                "applied_rules": result.journal_entry.applied_rules
            }
        
        serializable_results.append(result_dict)
    
    # 添加元数据
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(results),
        "success_count": sum(1 for r in results if r.processing_status.value == 'success'),
        "results": serializable_results
    }
    
    # 保存文件
    output_path = Path(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    console.print(f"💾 结果已保存到: {output_path}", style="green")

if __name__ == "__main__":
    app()
