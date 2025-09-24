"""
Kosmos CLI的 `login` 命令。
"""
import getpass
import sys
from argparse import ArgumentParser, _SubParsersAction

# 导入新的客户端
from ..knowledge_base_client import KosmosClient

def register_subparser(subparsers: _SubParsersAction, parent_parser: ArgumentParser):
    """
    为 `login` 命令注册子解析器。
    """
    login_parser = subparsers.add_parser(
        "login",
        help="登录到Kosmos平台并保存会话凭证。",
        parents=[parent_parser],
        add_help=False
    )
    login_parser.set_defaults(func=run_login)

def run_login(client: KosmosClient, args, config):
    """
    执行登录逻辑。
    此命令会实例化自己的客户端来执行登录。
    """
    # 按 命令行 -> 环境变量/.env -> 交互式输入 的顺序解析凭证
    username = config.resolve(args.username, "KOSMOS_USERNAME")
    password = config.resolve(args.password, "KOSMOS_PASSWORD")

    if not username:
        try:
            username = input("请输入用户名: ")
        except EOFError:
            print("\n已取消登录。", file=sys.stderr)
            sys.exit(1)

    if not password:
        try:
            password = getpass.getpass("请输入密码: ")
        except EOFError:
            print("\n已取消登录。", file=sys.stderr)
            sys.exit(1)
    
    # 实例化一个新的、跳过认证检查的客户端实例专门用于登录
    login_client = KosmosClient(skip_auth=True)
    login_client.login(username, password)
