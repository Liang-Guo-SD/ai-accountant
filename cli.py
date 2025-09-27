#!/usr/bin/env python3
"""
AI会计师 CLI - 专业的命令行界面
使用 Typer + Rich 打造优雅的用户交互体验
"""

import typer
from typing import List, Optional
from pathlib import Path
import json
import time
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from rich.syntax import Syntax
from rich.prompt import Confirm, Prompt
from rich.tree import Tree
from rich import print as rprint
from rich.layout import Layout
from rich.live import Live
from rich.text import Text

import httpx
import asyncio
from tqdm import tqdm

# 创建Typer应用
app = typer.Typer(
    name="ai-accountant",
    help="🤖 AI会计师 - 智能财务处理命令行工具",
    add_completion=True,
    rich_markup_mode="rich"
)

# 创建Rich控制台
console = Console()

# API配置
API_BASE_URL = "http://localhost:8000"


# ==================== 工具函数 ====================

def print_banner():
    """打印欢迎横幅"""
    banner = """
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║       🤖 AI 会 计 师 - 智 能 财 务 系 统 🤖        ║
    ║                     Version 2.0                      ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold blue"))


def check_api_health() -> bool:
    """检查API服务是否在线"""
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


# ==================== 处理命令 ====================

@app.command("process")
def process_document(
    files: List[Path] = typer.Argument(..., help="要处理的文件路径"),
    date: Optional[str] = typer.Option(None, "--date", "-d", help="凭证日期 YYYY-MM-DD"),
    complex: bool = typer.Option(True, "--complex/--simple", help="允许复合分录"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="保存结果到文件"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="显示详细信息")
):
    """
    📄 处理发票文档，生成会计分录
    
    示例:
        ai-accountant process invoice.pdf
        ai-accountant process *.pdf --date 2024-03-20
        ai-accountant process docs/ --output results.json
    """
    print_banner()
    
    # 检查API服务
    with console.status("[bold green]检查API服务...", spinner="dots"):
        if not check_api_health():
            console.print("❌ API服务未运行，请先启动: [bold]python run_api.py[/bold]", style="red")
            raise typer.Exit(1)
    
    console.print("✅ API服务正常", style="green")
    
    # 验证文件
    valid_files = []
    for file in files:
        if file.is_dir():
            # 如果是目录，获取所有支持的文件
            for ext in [".pdf", ".xlsx", ".xls"]:
                valid_files.extend(file.glob(f"*{ext}"))
        elif file.exists():
            valid_files.append(file)
        else:
            console.print(f"⚠️ 文件不存在: {file}", style="yellow")
    
    if not valid_files:
        console.print("❌ 没有找到有效文件", style="red")
        raise typer.Exit(1)
    
    console.print(f"📁 找到 [bold]{len(valid_files)}[/bold] 个文件待处理")
    
    # 创建进度条
    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        
        task = progress.add_task(
            f"[cyan]处理文档...", 
            total=len(valid_files)
        )
        
        for file in valid_files:
            progress.update(task, description=f"[cyan]处理: {file.name}")
            
            # 调用API处理文档
            try:
                with open(file, 'rb') as f:
                    files_data = {'file': (file.name, f, 'application/octet-stream')}
                    params = {
                        'entry_date': date,
                        'allow_complex': complex
                    }
                    
                    response = httpx.post(
                        f"{API_BASE_URL}/api/v1/process",
                        files=files_data,
                        params=params,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        results.append(result)
                        
                        if verbose:
                            _display_processing_result(result)
                    else:
                        console.print(f"❌ 处理失败: {file.name}", style="red")
                        
            except Exception as e:
                console.print(f"❌ 处理出错: {e}", style="red")
            
            progress.update(task, advance=1)
    
    # 显示汇总结果
    _display_summary(results)
    
    # 保存结果
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        console.print(f"💾 结果已保存到: [bold]{output}[/bold]", style="green")


@app.command("review")
def review_pending():
    """
    👀 查看待审核的凭证
    """
    print_banner()
    
    with console.status("[bold green]获取待审核凭证...", spinner="dots"):
        response = httpx.get(f"{API_BASE_URL}/api/v1/journals/pending")
    
    if response.status_code != 200:
        console.print("❌ 获取失败", style="red")
        return
    
    journals = response.json()
    
    if not journals:
        console.print("✨ 没有待审核的凭证", style="green")
        return
    
    # 创建表格显示
    table = Table(title=f"待审核凭证 (共{len(journals)}条)", show_lines=True)
    table.add_column("ID", style="cyan", width=6)
    table.add_column("日期", width=12)
    table.add_column("业务描述", width=30)
    table.add_column("借方", width=20)
    table.add_column("贷方", width=20)
    table.add_column("金额", justify="right", width=15)
    table.add_column("置信度", justify="right", width=10)
    
    for journal in journals:
        # 简化显示（假设是简单分录）
        debit_line = journal['entry_lines'][0] if journal['entry_lines'] else {}
        credit_line = journal['entry_lines'][1] if len(journal['entry_lines']) > 1 else {}
        
        confidence_color = "green" if journal['confidence_score'] >= 0.8 else "yellow"
        
        table.add_row(
            str(journal.get('id', '-')),
            journal['entry_date'],
            journal['business_description'][:30],
            f"{debit_line.get('account_name', '-')}",
            f"{credit_line.get('account_name', '-')}",
            f"¥{journal.get('total_debit', 0):,.2f}",
            f"[{confidence_color}]{journal['confidence_score']:.2%}[/{confidence_color}]"
        )
    
    console.print(table)


@app.command("approve")
def approve_journal(
    journal_id: int = typer.Argument(..., help="凭证ID"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="批准备注")
):
    """
    ✅ 批准凭证
    """
    # 确认操作
    if not Confirm.ask(f"确定要批准凭证 [bold]{journal_id}[/bold] 吗？"):
        console.print("已取消", style="yellow")
        return
    
    # 获取批准人
    approver = Prompt.ask("请输入您的姓名", default="管理员")
    
    # 调用API
    with console.status("[bold green]批准凭证...", spinner="dots"):
        response = httpx.post(
            f"{API_BASE_URL}/api/v1/journals/{journal_id}/approve",
            json={
                "approved_by": approver,
                "approval_notes": notes
            }
        )
    
    if response.status_code == 200:
        console.print(f"✅ 凭证 {journal_id} 已批准", style="green")
    else:
        console.print(f"❌ 批准失败: {response.text}", style="red")


@app.command("server")
def server_command(
    action: str = typer.Argument(..., help="操作: start|stop|status"),
    port: int = typer.Option(8000, "--port", "-p", help="服务端口")
):
    """
    🖥️ 管理API服务器
    """
    if action == "start":
        console.print("🚀 启动API服务器...", style="green")
        console.print(f"📍 地址: http://localhost:{port}")
        console.print(f"📚 文档: http://localhost:{port}/docs")
        console.print("\n提示: 在新终端窗口运行 [bold]python run_api.py[/bold]")
        
    elif action == "status":
        if check_api_health():
            console.print("✅ 服务器正在运行", style="green")
            
            # 获取详细状态
            response = httpx.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                status = response.json()
                
                # 创建状态面板
                status_tree = Tree("🖥️ 系统状态")
                status_tree.add(f"版本: {status['version']}")
                status_tree.add(f"数据库: {status['database']}")
                status_tree.add(f"AI服务: {status['ai_service']}")
                status_tree.add(f"RAG服务: {status['rag_service']}")
                
                console.print(Panel(status_tree, title="服务状态"))
        else:
            console.print("❌ 服务器未运行", style="red")
    
    elif action == "stop":
        console.print("⏹️ 请在运行服务器的终端按 CTRL+C 停止", style="yellow")


# ==================== 显示函数 ====================

def _display_processing_result(result: dict):
    """显示单个处理结果"""
    # 创建结果面板
    if result['status'] == 'success':
        status_text = Text("✅ 成功", style="green")
    else:
        status_text = Text("❌ 失败", style="red")
    
    info = f"""
文件: {result['file_name']}
状态: {status_text}
置信度: {result['confidence']:.2%}
处理时间: {result['processing_time']:.2f}秒
需要审核: {'是' if result['needs_review'] else '否'}
    """
    
    console.print(Panel(info, title="处理结果", border_style="blue"))
    
    # 显示凭证详情
    if result.get('journal_entry'):
        _display_journal_entry(result['journal_entry'])


def _display_journal_entry(entry: dict):
    """显示凭证详情"""
    table = Table(title="会计分录", show_lines=True)
    table.add_column("方向", width=6)
    table.add_column("科目编码", width=12)
    table.add_column("科目名称", width=20)
    table.add_column("金额", justify="right", width=15)
    
    for line in entry['entry_lines']:
        direction_style = "blue" if line['direction'] == '借' else "red"
        table.add_row(
            f"[{direction_style}]{line['direction']}[/{direction_style}]",
            line['account_code'],
            line['account_name'],
            f"¥{line['amount']:,.2f}"
        )
    
    console.print(table)


def _display_summary(results: List[dict]):
    """显示处理汇总"""
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = len(results) - success_count
    avg_confidence = sum(r['confidence'] for r in results) / len(results) if results else 0
    
    # 创建汇总表格
    summary_table = Table(title="📊 处理汇总", show_header=False)
    summary_table.add_column("指标", style="cyan")
    summary_table.add_column("值", style="white")
    
    summary_table.add_row("处理文件", str(len(results)))
    summary_table.add_row("成功", f"[green]{success_count}[/green]")
    summary_table.add_row("失败", f"[red]{failed_count}[/red]")
    summary_table.add_row("平均置信度", f"{avg_confidence:.2%}")
    summary_table.add_row("需要审核", str(sum(1 for r in results if r.get('needs_review'))))
    
    console.print(summary_table)


# ==================== 主函数 ====================

@app.callback()
def callback(version: bool = typer.Option(False, "--version", "-v", help="显示版本")):
    """
    🤖 AI会计师 - 让财务处理更智能
    """
    if version:
        console.print("AI会计师 版本 2.0.0", style="bold blue")
        raise typer.Exit()


if __name__ == "__main__":
    app()