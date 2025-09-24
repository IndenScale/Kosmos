import os
import sys
import argparse
import importlib
import pkgutil

# 将项目根目录添加到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import os
import sys
import argparse
import importlib
import pkgutil
import inspect

# 将项目根目录添加到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cli.config import CliConfig
from cli import utils
# 导入新的客户端类
from cli.knowledge_base_client import KosmosClient
from cli.assessment_client import AssessmentClient
from cli import commands

def check_agent_mode_and_redirect(args):
    """
    检查是否处于AGENT模式，如果是，则将顶层命令重定向到agent子命令。
    """
    kosmos_mode = os.getenv("KOSMOS_MODE", "").upper()
    
    if kosmos_mode == "AGENT":
        # 需要重定向到agent子命令的命令列表
        agent_commands = ["search", "read", "grep"]
        
        if args.command in agent_commands:
            print(f"[AGENT模式] 将 {args.command} 命令重定向到 agent {args.command}")
            # 保存原始命令用于提示
            args._original_command = args.command
            # 修改命令为agent，子命令会保存在args.func中
            args.command = "agent"
            # 设置子命令
            args.agent_subcommand = args._original_command
            
    return args

def main():
    """
    CLI 主入口点。
    """
    # 1. 初始化配置处理器
    config = CliConfig(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

    # 2. 创建父解析器
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--username", help="Kosmos用户名 (仅用于 'login' 命令)。")
    parent_parser.add_argument("--password", help="Kosmos密码 (仅用于 'login' 命令)。")
    parent_parser.add_argument("--ks-id", help="知识空间ID (环境变量: KOSMOS_KS_ID)。")
    parent_parser.add_argument("--asset-id", help="资产ID (环境变量: KOSMOS_ASSET_ID)。")

    # 3. 设置主命令解析器
    parser = argparse.ArgumentParser(
        description="一个用于与Kosmos API交互的CLI工具。",
        epilog="使用 'kosmos login' 开始会话。参数也可以通过环境变量提供。",
    )
    # Manually add global arguments to the main parser
    parser.add_argument("--username", help="Kosmos用户名 (仅用于 'login' 命令)。")
    parser.add_argument("--password", help="Kosmos密码 (仅用于 'login' 命令)。")
    parser.add_argument("--ks-id", help="知识空间ID (环境变量: KOSMOS_KS_ID)。")
    parser.add_argument("--asset-id", help="资产ID (环境变量: KOSMOS_ASSET_ID)。")
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用命令")

    # 4. 动态发现并注册所有子命令
    for _, module_name, _ in pkgutil.iter_modules(commands.__path__, commands.__name__ + "."):
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, 'register_subparser'):
                module.register_subparser(subparsers, parent_parser)
        except ImportError as e:
            print(f"错误: 无法加载命令模块 '{module_name}': {e}", file=sys.stderr)
    
    # 如果在AGENT模式下，确保agent子命令已注册
    kosmos_mode = os.getenv("KOSMOS_MODE", "").upper()
    if kosmos_mode == "AGENT" and not hasattr(subparsers, 'choices'):
        print("错误: 在AGENT模式下无法加载必要的子命令", file=sys.stderr)
        sys.exit(1)

    # 5. 解析参数
    args = parser.parse_args()
    
    # 5.5 检查AGENT模式并重定向命令
    args = check_agent_mode_and_redirect(args)

    # 6. 初始化客户端
    # login 命令是特例，它在执行前不需要认证
    if args.command == 'login':
        # login 命令的 run 函数签名是 (client, args, config)，但 client 为 None
        args.func(None, args, config)
        return

    # 对于所有其他命令，我们需要一个已认证的知识库客户端
    kb_client = KosmosClient()
    
    # 使用知识库客户端获取的token来初始化评估服务客户端
    try:
        token = kb_client.get_raw_token()
        assessment_client = AssessmentClient(token=token)
    except SystemExit as e:
        sys.exit(e.code)

    # 7. 执行选定的命令函数 (智能参数传递)
    if hasattr(args, 'func'):
        # 创建一个包含所有可用参数的字典
        # 'client' 是 'kb_client' 的别名，以实现向后兼容
        available_params = {
            'kb_client': kb_client,
            'assessment_client': assessment_client,
            'client': kb_client,  # 别名，用于旧命令
            'args': args,
            'config': config
        }
        
        # 检查目标函数需要哪些参数
        target_func_sig = inspect.signature(args.func).parameters
        
        # 构建将要传递给函数的参数字典
        params_to_pass = {
            name: available_params[name] 
            for name in target_func_sig 
            if name in available_params
        }
        
        # 使用关键字参数解包的方式调用函数
        args.func(**params_to_pass)
    else:
        print("错误: 未知的子命令或未指定操作。", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
