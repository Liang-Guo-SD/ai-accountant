#!/usr/bin/env python3
"""
AI会计师 - 智能发票处理系统（支持复合分录）
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
from rich.columns import Columns
from rich.text import Text

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.config import get_config, config
from app.services.document_processor import process_single_document, process_multiple_documents
from app.services.rag_service import AccountingRAGService
from app.database import init_database
from scripts.system_manager import SystemManager
from app.schemas import JournalEntry, EntryDirection

# 创建Typer应用
app = typer.Typer(
    name="ai-accountant",
    help="🤖 AI会计师 - 智能发票处理系统（支持复合分录）",
    add_completion=False
)

# 创建Rich控制台
console = Console()


def display_journal_entry_rich(entry: JournalEntry, verbose: bool = False):
    """使用Rich库美化显示会计分录（支持复合分录）"""
    
    # 创建主面板
    title = f"[bold blue]📊 会计分录[/bold blue]"
    
    # 基本信息表格
    info_table = Table(show_header=False, box=None, padding=(0, 1))
    info_table.add_column("Field", style="cyan")
    info_table.add_column("Value", style="white")
    
    info_table.add_row("业务描述", entry.business_description)
    info_table.add_row("分录日期", entry.entry_date)
    if hasattr(entry, 'voucher_number') and entry.voucher_number:
        info_table.add_row("凭证号", entry.voucher_number)
    
    # 置信度显示
    confidence_color = "green" if entry.confidence_score >= 0.8 else "yellow" if entry.confidence_score >= 0.6 else "red"
    info_table.add_row("置信度", f"[{confidence_color}]{entry.confidence_score:.2%}[/{confidence_color}]")
    
    # 平衡状态
    balance_status = "[green]✅ 平衡[/green]" if entry.is_balanced else "[red]❌ 不平衡[/red]"
    info_table.add_row("借贷平衡", balance_status)
    
    # 审核标记
    review_status = "[yellow]⚠️ 需要审核[/yellow]" if entry.needs_review else "[green]✅ 无需审核[/green]"
    info_table.add_row("审核状态", review_status)
    
    console.print(Panel(info_table, title=title, expand=False))
    
    # 分录明细表格
    detail_table = Table(title="[bold]分录明细[/bold]", show_lines=True)
    detail_table.add_column("方向", style="bold", width=6)
    detail_table.add_column("科目编码", width=12)
    detail_table.add_column("科目名称", width=25)
    detail_table.add_column("金额", justify="right", width=15)
    detail_table.add_column("摘要", width=30)
    
    # 分组显示借方和贷方
    debit_lines = [l for l in entry.entry_lines if l.direction == EntryDirection.DEBIT]
    credit_lines = [l for l in entry.entry_lines if l.direction == EntryDirection.CREDIT]
    
    # 添加借方行
    for line in debit_lines:
        detail_table.add_row(
            "[blue]借[/blue]",
            line.account_code,
            line.account_name,
            f"[blue]{line.amount:,.2f}[/blue]",
            line.description or ""
        )
    
    # 添加分隔行（如果既有借方又有贷方）
    if debit_lines and credit_lines:
        detail_table.add_row("", "", "", "", "")
    
    # 添加贷方行
    for line in credit_lines:
        detail_table.add_row(
            "[red]贷[/red]",
            line.account_code,
            line.account_name,
            f"[red]{line.amount:,.2f}[/red]",
            line.description or ""
        )
    
    # 添加合计行
    detail_table.add_row(
        "[bold]合计[/bold]",
        "",
        "",
        f"[bold]借: {entry.total_debit:,.2f}\n贷: {entry.total_credit:,.2f}[/bold]",
        ""
    )
    
    console.print(detail_table)
    
    # 显示验证信息
    if entry.validation_notes:
        validation_panel = Panel(
            entry.validation_notes,
            title="[bold yellow]验证说明[/bold yellow]",
            expand=False
        )
        console.print(validation_panel)
    
    # 详细模式下显示更多信息
    if verbose:
        # 分析过程
        if entry.analysis_process:
            analysis_panel = Panel(
                Text(entry.analysis_process, style="dim"),
                title="[bold cyan]🔍 分析过程[/bold cyan]",
                expand=False
            )
            console.print(analysis_panel)
        
        # 应用规则
        if entry.applied_rules:
            rules_panel = Panel(
                Text(entry.applied_rules, style="dim"),
                title="[bold magenta]📚 应用规则[/bold magenta]",
                expand=False
            )
            console.print(rules_panel)
    
    # 分录类型标识
    entry_type = "复合分录" if len(entry.entry_lines) > 2 else "简单分录"
    type_color = "yellow" if len(entry.entry_lines) > 2 else "green"
    console.print(f"\n[{type_color}]分录类型: {entry_type} (共{len(entry.entry_lines)}行)[/{type_color}]")


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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示详细信息"),
    allow_complex: bool = typer.Option(True, "--complex/--simple", help="允许生成复合分录")
):
    """处理发票文档并生成会计分录（支持复合分录）"""
    
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
    if allow_complex:
        console.print("✨ 已启用复合分录生成", style="cyan")
    else:
        console.print("📝 仅生成简单分录", style="cyan")
    
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
        _display_single_result_enhanced(result, verbose)
    else:
        _display_batch_results_enhanced(results, verbose)
    
    # 保存结果到文件
    if output:
        _save_results_to_file_enhanced(results if len(valid_files) > 1 else [result], output)


def _display_single_result_enhanced(result, verbose: bool):
    """显示单个处理结果（增强版）"""
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
    
    # 显示会计分录
    if result.journal_entry:
        display_journal_entry_rich(result.journal_entry, verbose)


def _display_batch_results_enhanced(results, verbose: bool):
    """显示批量处理结果（增强版）"""
    console.print(f"\n📊 批量处理结果 ({len(results)} 个文件)", style="bold blue")
    
    # 统计信息
    success_count = sum(1 for r in results if r.processing_status.value == 'success')
    complex_count = sum(1 for r in results 
                       if r.journal_entry and len(r.journal_entry.entry_lines) > 2)
    
    stats_table = Table(title="处理统计", show_header=False)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="white")
    
    stats_table.add_row("✅ 成功", f"{success_count}/{len(results)}")
    stats_table.add_row("❌ 失败", f"{len(results) - success_count}/{len(results)}")
    stats_table.add_row("🔀 复合分录", f"{complex_count}/{success_count}")
    stats_table.add_row("📝 简单分录", f"{success_count - complex_count}/{success_count}")
    
    console.print(stats_table)
    
    # 详细结果表格
    if verbose:
        detail_table = Table(title="详细结果")
        detail_table.add_column("文件名", style="cyan")
        detail_table.add_column("状态", style="white")
        detail_table.add_column("分录类型", style="white")
        detail_table.add_column("置信度", style="white")
        detail_table.add_column("需要审核", style="white")
        
        for result in results:
            status_color = "green" if result.processing_status.value == 'success' else "red"
            
            # 判断分录类型
            entry_type = "-"
            if result.journal_entry:
                entry_type = "复合" if len(result.journal_entry.entry_lines) > 2 else "简单"
            
            detail_table.add_row(
                result.file_name,
                f"[{status_color}]{result.processing_status.value}[/{status_color}]",
                entry_type,
                f"{result.final_confidence:.3f}",
                "是" if result.needs_review else "否"
            )
        
        console.print(detail_table)
        
        # 显示每个文件的分录详情
        if verbose:
            for result in results:
                if result.journal_entry:
                    console.print(f"\n[bold]文件: {result.file_name}[/bold]")
                    display_journal_entry_rich(result.journal_entry, False)


def _save_results_to_file_enhanced(results, output_path: str):
    """保存结果到文件（增强版，包含复合分录信息）"""
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
            # 保存完整的分录明细
            entry_lines = []
            for line in result.journal_entry.entry_lines:
                entry_lines.append({
                    "account_code": line.account_code,
                    "account_name": line.account_name,
                    "direction": line.direction.value,
                    "amount": line.amount,
                    "description": line.description
                })
            
            result_dict["journal_entry"] = {
                "business_description": result.journal_entry.business_description,
                "entry_date": result.journal_entry.entry_date,
                "voucher_number": getattr(result.journal_entry, 'voucher_number', None),
                "entry_lines": entry_lines,
                "total_debit": result.journal_entry.total_debit,
                "total_credit": result.journal_entry.total_credit,
                "entry_type": "复合分录" if len(entry_lines) > 2 else "简单分录",
                "confidence_score": result.journal_entry.confidence_score,
                "is_balanced": result.journal_entry.is_balanced,
                "validation_notes": result.journal_entry.validation_notes,
                "analysis_process": result.journal_entry.analysis_process,
                "applied_rules": result.journal_entry.applied_rules
            }
        
        serializable_results.append(result_dict)
    
    # 统计信息
    complex_entry_count = sum(1 for r in serializable_results 
                            if r.get("journal_entry") and 
                            len(r["journal_entry"]["entry_lines"]) > 2)
    
    # 添加元数据
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(results),
        "success_count": sum(1 for r in results if r.processing_status.value == 'success'),
        "complex_entry_count": complex_entry_count,
        "simple_entry_count": len(results) - complex_entry_count,
        "results": serializable_results
    }
    
    # 保存文件
    output_path = Path(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    console.print(f"💾 结果已保存到: {output_path}", style="green")


@app.command()
def status():
    """查看系统状态"""
    console.print("📊 AI会计师系统状态（支持复合分录）", style="bold blue")
    
    try:
        # 显示配置信息
        config.print_config_summary()
        
        # 系统功能状态
        console.print("\n[bold]系统功能:[/bold]")
        console.print("✅ 简单分录生成: 已启用", style="green")
        console.print("✅ 复合分录生成: 已启用", style="green")
        console.print("✅ 多借多贷支持: 已启用", style="green")
        
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


if __name__ == "__main__":
    app()