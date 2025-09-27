#!/usr/bin/env python3
"""
FastAPI服务启动脚本
专业的服务管理和配置
"""

import uvicorn
import click
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

@click.command()
@click.option('--host', default='127.0.0.1', help='服务监听地址')
@click.option('--port', default=8000, help='服务监听端口')
@click.option('--reload', is_flag=True, help='开发模式，自动重载')
@click.option('--workers', default=1, help='工作进程数量')
@click.option('--log-level', default='info', help='日志级别')
def run_server(host, port, reload, workers, log_level):
    """启动AI会计师API服务"""
    
    print(f"""
╔════════════════════════════════════════╗
║       AI会计师 FastAPI 服务器          ║
╚════════════════════════════════════════╝

🚀 启动配置:
   主机: {host}
   端口: {port}
   重载: {'开启' if reload else '关闭'}
   进程: {workers}
   日志: {log_level}

📝 API文档:
   Swagger UI: http://{host}:{port}/api/v1/docs
   ReDoc: http://{host}:{port}/api/v1/redoc

按 Ctrl+C 停止服务器
""")
    
    # 配置并启动服务器
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=1 if reload else workers,  # 重载模式下只能使用单进程
        log_level=log_level,
        access_log=True
    )

if __name__ == "__main__":
    run_server()