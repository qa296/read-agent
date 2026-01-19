#!/usr/bin/env python3
"""
代码阅读智能助手

使用方法：
    python main.py
    python main.py --code-dir /path/to/code
"""

import os
import sys
import argparse
import re
from pathlib import Path

from src.agent import ReadAgent


def load_env_file(env_path: str = ".env") -> dict:
    """
    使用标准库加载 .env 文件
    """
    env_vars = {}
    env_file = Path(env_path)

    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith("#"):
                    continue
                # 解析 KEY=VALUE 格式
                match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
                if match:
                    key = match.group(1)
                    value = match.group(2).strip('"').strip("'")
                    env_vars[key] = value

    return env_vars


def get_env(key: str, default: str = "") -> str:
    """获取环境变量，优先使用系统环境变量，其次使用 .env 文件"""
    value = os.getenv(key)
    if value is not None:
        return value

    # 尝试从 .env 加载
    if not hasattr(get_env, "_env_cache"):
        get_env._env_cache = load_env_file()

    return get_env._env_cache.get(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    """获取布尔型环境变量"""
    value = get_env(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    elif value in ("false", "0", "no", "off"):
        return False
    return default


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Read Agent - 代码阅读智能助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py
    python main.py --code-dir /path/to/your/code
    python main.py --api-key sk-xxx
        """
    )
    parser.add_argument(
        "--code-dir", "-d",
        default=get_env("CODE_DIR", "."),
        help="代码目录路径 (默认: 当前目录)"
    )
    parser.add_argument(
        "--api-key", "-k",
        default=get_env("OPENAI_API_KEY", ""),
        help="OpenAI API Key"
    )
    parser.add_argument(
        "--base-url", "-b",
        default=get_env("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="API 基础 URL"
    )
    parser.add_argument(
        "--model", "-m",
        default=get_env("OPENAI_MODEL", "gpt-4"),
        help="模型名称"
    )
    parser.add_argument(
        "--max-steps", "-s",
        type=int,
        default=int(get_env("MAX_STEPS", "10")),
        help="最大步骤数"
    )
    parser.add_argument(
        "--stream-output", "--stream",
        action="store_true",
        default=get_env_bool("STREAM_OUTPUT", True),
        help="启用流式输出（每步实时显示）"
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        default=False,
        help="禁用流式输出"
    )
    return parser.parse_args()


def print_welcome():
    """打印欢迎信息"""
    print("""
╔════════════════════════════════════════════════════════════╗
║                    Read Agent v1.0.0                       ║
╠════════════════════════════════════════════════════════════╣
║  命令:                                                     ║
║    quit / exit / q  - 退出                                 ║
║    clear              - 清空对话历史                       ║
║    status             - 查看状态                           ║
║    help               - 显示帮助                           ║
╚════════════════════════════════════════════════════════════╝
    """)


def print_help():
    """打印帮助信息"""
    print("""
可用命令:
  quit / exit / q   - 退出程序
  clear             - 清空对话历史和 Memory
  status            - 查看当前状态（对话轮数、Memory数量等）
  help              - 显示此帮助信息

示例问题:
  🤔 这个项目是做什么的？
  🤔 用户认证是如何实现的？
  🤔 找到处理 API 请求的代码
  🤔 这个函数的作用是什么？
  🤔 数据库连接是怎么配置的？
    """)


def main():
    """主函数"""
    # 解析参数
    args = parse_args()

    # 验证 API Key
    if not args.api_key:
        print("❌ 错误: 请设置 OPENAI_API_KEY 环境变量或使用 --api-key 参数")
        print("\n设置方式:")
        print("  方式1: echo 'OPENAI_API_KEY=your-api-key' > .env")
        print("  方式2: export OPENAI_API_KEY=your-api-key")
        print("  方式3: python main.py --api-key your-api-key")
        sys.exit(1)

    # 创建 Agent
    stream_output = args.stream_output and not args.no_stream
    agent = ReadAgent(
        code_dir=args.code_dir,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        max_steps=args.max_steps,
        stream_output=stream_output
    )

    # 打印欢迎信息
    print_welcome()
    print(f"📁 代码目录: {agent.searcher.root_dir}")
    print(f"🤖 使用模型: {agent.model}")
    print(f"📝 最大步骤: {agent.max_steps}")
    print()

    # 初始化提示
    print("💡 输入问题开始对话，输入 help 查看帮助")
    print()

    # 主循环
    while True:
        try:
            user_input = input("🤔 ").strip()

            # 处理空输入
            if not user_input:
                continue

            # 处理命令
            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 再见！")
                break
            elif user_input.lower() == "clear":
                agent.clear_history()
                print("✅ 已清空对话历史和 Memory")
                continue
            elif user_input.lower() == "status":
                stats = agent.get_stats()
                print(f"\n📊 状态统计:")
                print(f"   对话轮数: {stats['conversation_length']}")
                print(f"   Memory 数量: {stats['memory_count']}")
                print(f"   总步骤数: {stats['total_steps']}")
                print(f"   代码目录: {stats['code_dir']}")
                continue
            elif user_input.lower() == "help":
                print_help()
                continue

            # 处理问题
            print()
            response = agent.ask(user_input)
            print(response)

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            print("💡 提示: 检查 API Key 和网络连接")


if __name__ == "__main__":
    main()
