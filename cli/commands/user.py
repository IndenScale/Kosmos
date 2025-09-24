"""Kosmos CLI的用户管理命令。"""

import sys
import getpass
from argparse import ArgumentParser, _SubParsersAction
from ..knowledge_base_client import KosmosClient
from ..config import CliConfig

def register_subparser(subparsers: _SubParsersAction, parent_parser: ArgumentParser):
    """
    为用户管理命令注册子解析器。
    """
    user_parser = subparsers.add_parser(
        "user",
        help="用户管理命令 - 注册、列表、删除用户以及查看个人信息",
        description="管理Kosmos平台用户账户的命令集合",
        parents=[parent_parser],
        add_help=False
    )
    
    user_subparsers = user_parser.add_subparsers(
        dest="user_action", 
        required=False, 
        help="用户操作"
    )
    
    # 添加默认行为：当没有指定子命令时显示帮助
    user_parser.set_defaults(func=lambda client, args, config: user_parser.print_help())
    
    # 用户注册命令
    register_parser = user_subparsers.add_parser(
        "register",
        help="注册新用户账户",
        description="创建新的Kosmos用户账户。需要提供用户名、邮箱和显示名称。",
        epilog="示例: kosmos user register --new-username john --email john@example.com --display-name 'John Doe'",
        parents=[parent_parser],
        add_help=False
    )
    register_parser.add_argument("--new-username", required=True, help="新用户的用户名 (必须唯一)")
    register_parser.add_argument("--email", required=True, help="用户邮箱地址 (必须唯一)")
    register_parser.add_argument("--display-name", required=True, help="用户显示名称")
    register_parser.add_argument("--new-password", help="新用户的密码 (如果不提供将提示输入)")
    register_parser.add_argument("--role", default="user", 
                                choices=["user", "admin", "super_admin"],
                                help="用户角色 (默认: user, 可选: user, admin, super_admin)")
    register_parser.set_defaults(func=run_register)
    
    # 用户列表命令
    list_parser = user_subparsers.add_parser(
        "list",
        help="列出系统中的所有用户",
        description="显示系统中所有注册用户的列表。需要管理员权限。",
        epilog="示例: kosmos user list --limit 50 --offset 0",
        parents=[parent_parser],
        add_help=False
    )
    list_parser.add_argument("--limit", type=int, default=20, 
                            help="每页显示的用户数量 (默认: 20, 最大: 100)")
    list_parser.add_argument("--offset", type=int, default=0, 
                            help="跳过的用户数量，用于分页 (默认: 0)")
    list_parser.set_defaults(func=run_list)
    
    # 用户删除命令
    delete_parser = user_subparsers.add_parser(
        "delete",
        help="删除指定用户账户",
        description="永久删除用户账户及其相关数据。此操作不可逆，需要管理员权限。",
        epilog="示例: kosmos user delete 12345678-1234-1234-1234-123456789abc --force",
        parents=[parent_parser],
        add_help=False
    )
    delete_parser.add_argument("user_id", help="要删除的用户UUID")
    delete_parser.add_argument("--force", action="store_true", 
                              help="跳过确认提示，直接删除用户")
    delete_parser.set_defaults(func=run_delete)
    
    # 查看自我信息命令
    me_parser = user_subparsers.add_parser(
        "me",
        help="查看当前登录用户的详细信息",
        description="显示当前已登录用户的个人资料信息，包括用户名、邮箱、角色等。",
        epilog="示例: kosmos user me",
        parents=[parent_parser],
        add_help=False
    )
    me_parser.set_defaults(func=run_me)

def run_register(client: KosmosClient, args, config):
    """
    执行用户注册命令。
    """
    try:
        # 获取密码（如果未提供则提示输入）
        password = getattr(args, 'new_password', None)
        if not password:
            password = getpass.getpass("请输入新用户密码: ")
            if not password:
                print("密码不能为空")
                return 1
        
        # 创建跳过认证的客户端用于注册
        register_client = KosmosClient(skip_auth=True)
        
        # 调用注册API
        result = register_client.register_user(
            username=getattr(args, 'new_username'),
            email=args.email,
            display_name=getattr(args, 'display_name'),
            password=password,
            role=args.role
        )
        
        print(f"用户注册成功！")
        print(f"用户ID: {result.get('id')}")
        print(f"用户名: {result.get('username')}")
        print(f"邮箱: {result.get('email')}")
        print(f"显示名称: {result.get('display_name')}")
        print(f"角色: {result.get('role')}")
            
    except Exception as e:
        print(f"注册过程中发生错误: {e}")
        return 1
    
    return 0

def run_list(client: KosmosClient, args, config):
    """
    执行用户列表查询逻辑。
    """
    try:
        params = {
            "limit": args.limit,
            "offset": args.offset
        }
        
        # 使用正确的API调用方式
        data = client._request("GET", "users/", params=params)
        
        users = data.get('users', [])
        total = data.get('total', 0)
        
        print(f"用户列表 (共 {total} 个用户):")
        print("-" * 80)
        print(f"{'ID':<36} {'用户名':<20} {'邮箱':<30} {'角色':<10}")
        print("-" * 80)
        
        for user in users:
            print(f"{user['id']:<36} {user['username']:<20} {user['email']:<30} {user['role']:<10}")
            
        if args.offset + len(users) < total:
            print(f"\n显示 {args.offset + 1}-{args.offset + len(users)} / {total}")
            
    except Exception as e:
        print(f"获取用户列表过程中发生错误: {str(e)}", file=sys.stderr)
        sys.exit(1)

def run_delete(client: KosmosClient, args, config):
    """
    执行用户删除逻辑。
    """
    user_id = args.user_id
    
    if not args.force:
        try:
            confirm = input(f"确定要删除用户 {user_id} 吗? (y/N): ")
            if confirm.lower() not in ['y', 'yes']:
                print("已取消删除操作。")
                return
        except EOFError:
            print("\n已取消删除操作。")
            return
    
    try:
        response = client.delete(f"/api/v1/users/{user_id}")
        
        if response.status_code == 200:
            print(f"用户 {user_id} 删除成功。")
        elif response.status_code == 404:
            print(f"用户 {user_id} 不存在。", file=sys.stderr)
            sys.exit(1)
        else:
            error_msg = response.json().get('detail', '删除用户失败')
            print(f"删除用户失败: {error_msg}", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"删除用户过程中发生错误: {str(e)}", file=sys.stderr)
        sys.exit(1)

def run_me(client: KosmosClient, args, config):
    """
    执行查看当前用户信息逻辑。
    """
    try:
        user_data = client._request("GET", "users/me")
        
        print("当前用户信息:")
        print("-" * 40)
        print(f"用户ID: {user_data['id']}")
        print(f"用户名: {user_data['username']}")
        print(f"邮箱: {user_data['email']}")
        print(f"显示名称: {user_data['display_name']}")
        print(f"角色: {user_data['role']}")
        # 移除了不存在的 'created_at' 属性
        # print(f"创建时间: {user_data['created_at']}")
            
    except Exception as e:
        print(f"获取用户信息过程中发生错误: {str(e)}", file=sys.stderr)
        sys.exit(1)