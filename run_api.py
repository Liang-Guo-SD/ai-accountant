#!/usr/bin/env python3
"""
FastAPI 服务启动脚本
提供开发和生产环境的启动配置
"""

import uvicorn
import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.config import get_config

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="启动AI会计师API服务")
    parser.add_argument("--host", default="0.0.0.0", help="服务器地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="开发模式（自动重载）")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数")
    parser.add_argument("--env", choices=["dev", "prod"], default="dev", help="运行环境")
    
    args = parser.parse_args()
    
    config = get_config()
    
    if args.env == "dev" or args.reload:
        # 开发模式
        print("🚀 启动开发服务器...")
        print(f"📍 API地址: http://{args.host}:{args.port}")
        print(f"📚 文档地址: http://{args.host}:{args.port}/docs")
        print(f"🔄 自动重载: 启用")
        print("\n按 CTRL+C 停止服务器\n")
        
        uvicorn.run(
            "app.api.main:app",
            host=args.host,
            port=args.port,
            reload=True,
            log_level="info"
        )
    else:
        # 生产模式
        print("🚀 启动生产服务器...")
        print(f"📍 API地址: http://{args.host}:{args.port}")
        print(f"📚 文档地址: http://{args.host}:{args.port}/docs")
        print(f"👷 工作进程: {args.workers}")
        print("\n按 CTRL+C 停止服务器\n")
        
        uvicorn.run(
            "app.api.main:app",
            host=args.host,
            port=args.port,
            workers=args.workers,
            log_level="info"
        )

if __name__ == "__main__":
    main()