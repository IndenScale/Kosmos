"""Kosmos CLI的凭证管理命令。"""

import sys
import json
from argparse import ArgumentParser, _SubParsersAction
from ..knowledge_base_client import KosmosClient

def register_subparser(subparsers: _SubParsersAction, parent_parser: ArgumentParser):
    """
    为凭证管理命令注册子解析器。
    """
    credential_parser = subparsers.add_parser(
        "credential",
        help="凭证管理命令 - 管理OpenAI兼容的API凭证",
        description="管理用于访问AI模型的API凭证，支持OpenAI兼容的各种服务提供商",
        parents=[parent_parser],
        add_help=False
    )
    
    credential_subparsers = credential_parser.add_subparsers(
        dest="credential_action", 
        required=False, 
        help="凭证操作"
    )
    
    # 凭证列表命令
    list_parser = credential_subparsers.add_parser(
        "list",
        help="列出当前用户的所有API凭证",
        description="显示当前用户拥有的所有API凭证列表，包括凭证类型、模型族和创建时间等信息。",
        epilog="示例: kosmos credential list --type llm --family openai",
        parents=[parent_parser],
        add_help=False
    )
    list_parser.add_argument("--type", help="按凭证类型过滤 (vlm, llm, embedding, slm, image_gen, omni)")
    list_parser.add_argument("--family", help="按模型家族过滤 (openai, gemini, anthropic)")
    list_parser.add_argument("--limit", type=int, default=20, help="返回凭证数量限制 (默认: 20)")
    list_parser.add_argument("--offset", type=int, default=0, help="偏移量 (默认: 0)")
    list_parser.set_defaults(func=run_list)
    
    # 凭证创建命令
    create_parser = credential_subparsers.add_parser(
        "create",
        help="创建新的API凭证",
        description="创建新的API凭证。",
        epilog="示例: kosmos credential create --name 'My OpenAI' --model-name gpt-4 --base-url https://api.openai.com/v1 --api-key sk-xxx",
        parents=[parent_parser],
        add_help=False
    )
    create_parser.add_argument("--credential-type", required=True, 
                              choices=['vlm', 'llm', 'embedding', 'slm', 'image_gen', 'omni', 'none'], 
                              help="凭证类型")
    create_parser.add_argument("--model-family", required=True, help="模型系列")
    create_parser.add_argument("--provider", required=True, help="提供商")
    create_parser.add_argument("--model-name", required=True, help="模型名称 (如: gpt-4, claude-3, gemini-pro)")
    create_parser.add_argument("--base-url", required=True, help="API基础URL")
    create_parser.add_argument("--api-key", required=True, help="API密钥")
    create_parser.add_argument("--default", action="store_true", help="设置为默认凭证")
    create_parser.set_defaults(func=run_create)
    
    # 凭证更新命令
    update_parser = credential_subparsers.add_parser(
        "update",
        help="更新现有API凭证",
        description="修改现有API凭证的信息。",
        epilog="示例: kosmos credential update 12345678-1234-1234-1234-123456789abc --model-name gpt-4-turbo --api-key sk-new-key",
        parents=[parent_parser],
        add_help=False
    )
    update_parser.add_argument("id", help="要更新的凭证ID")
    update_parser.add_argument("--model-name", help="新的模型名称")
    update_parser.add_argument("--base-url", help="新的基础URL")
    update_parser.add_argument("--api-key", help="新的API密钥")
    update_parser.add_argument("--default", action="store_true", help="设置为默认凭证")
    update_parser.add_argument("--no-default", action="store_true", help="取消默认凭证设置")
    update_parser.set_defaults(func=run_update)
    
    # 凭证删除命令
    delete_parser = credential_subparsers.add_parser(
        "delete",
        help="删除指定的API凭证",
        description="永久删除指定的API凭证。此操作不可逆，请谨慎使用。",
        epilog="示例: kosmos credential delete 12345678-1234-1234-1234-123456789abc --force",
        parents=[parent_parser],
        add_help=False
    )
    delete_parser.add_argument("id", help="要删除的凭证ID")
    delete_parser.add_argument("--force", action="store_true", 
                              help="跳过确认提示，直接删除凭证")
    delete_parser.set_defaults(func=run_delete)
    
    # 凭证详情命令
    show_parser = credential_subparsers.add_parser(
        "show",
        help="查看指定API凭证的详细信息",
        description="显示指定API凭证的详细信息，包括类型、模型族、提供商等，但不显示敏感的API密钥。",
        epilog="示例: kosmos credential show 12345678-1234-1234-1234-123456789abc",
        parents=[parent_parser],
        add_help=False
    )
    show_parser.add_argument("id", help="要查看的凭证ID")
    show_parser.set_defaults(func=run_show)
    
    # 设置默认凭证命令
    set_default_parser = credential_subparsers.add_parser(
        "set-default",
        help="设置默认凭证",
        description="将指定的凭证设置为默认凭证。",
        epilog="示例: kosmos credential set-default 12345678-1234-1234-1234-123456789abc",
        parents=[parent_parser],
        add_help=False
    )
    set_default_parser.add_argument("id", help="要设置为默认的凭证ID")
    set_default_parser.set_defaults(func=run_set_default)
    
    # 设置默认动作为list
    credential_parser.set_defaults(func=run_list)

def run_list(client, args, config):
    """
    执行凭证列表查询。
    """
    credentials = client.list_credentials()
    
    if not credentials:
        print("没有找到凭证。")
        return
    
    # 格式化输出
    print(f"{'ID':<36} {'类型':<12} {'提供商':<15} {'模型':<25} {'基础URL':<30} {'默认':<6}")
    print("-" * 130)
    
    for cred in credentials:
        is_default = "是" if cred.get('is_default', False) else "否"
        credential_type = cred.get('credential_type', 'N/A')
        provider = cred.get('provider', 'N/A')
        model_name = cred.get('model_name', 'N/A')
        base_url = cred.get('base_url', 'N/A') or 'N/A'
        print(f"{cred['id']:<36} {credential_type:<12} {provider:<15} {model_name:<25} {base_url:<30} {is_default:<6}")

def run_create(client, args, config):
    """
    执行凭证创建。
    """
    try:
        response = client.create_credential(
            credential_type=args.credential_type,
            model_family=args.model_family,
            provider=args.provider,
            model_name=args.model_name,
            base_url=args.base_url,
            api_key=args.api_key,
            is_default=getattr(args, 'default', False)
        )
        
        print(f"凭证创建成功!")
        print(f"ID: {response['id']}")
        print(f"类型: {response.get('credential_type', 'N/A')}")
        print(f"模型: {response.get('model_name', 'N/A')}")
        print(f"基础URL: {response.get('base_url', 'N/A')}")
        
    except Exception as e:
        print(f"创建凭证失败: {e}", file=sys.stderr)
        sys.exit(1)

def run_update(client, args, config):
    """
    执行凭证更新。
    """
    try:
        # 检查是否有字段需要更新
        if not any([args.model_name, args.base_url, args.api_key, getattr(args, 'default', False), getattr(args, 'no_default', False)]):
            print("没有提供要更新的字段。", file=sys.stderr)
            sys.exit(1)
        
        # 准备更新数据
        update_data = {
            'credential_id': args.id,
            'model_name': args.model_name,
            'base_url': args.base_url,
            'api_key': args.api_key
        }
        
        # 处理默认凭证设置
        if getattr(args, 'default', False):
            update_data['is_default'] = True
        elif getattr(args, 'no_default', False):
            update_data['is_default'] = False
        
        response = client.update_credential(**update_data)
        
        print(f"凭证更新成功!")
        print(f"ID: {response['id']}")
        print(f"类型: {response.get('credential_type', 'N/A')}")
        print(f"模型: {response.get('model_name', 'N/A')}")
        print(f"基础URL: {response.get('base_url', 'N/A')}")
        
    except Exception as e:
        print(f"更新凭证失败: {e}", file=sys.stderr)
        sys.exit(1)

def run_delete(client, args, config):
    """执行凭证删除。"""
    credential_id = args.id
    
    # 确认删除
    if not args.force:
        confirm = input(f"确定要删除凭证 {credential_id} 吗？(y/N): ")
        if confirm.lower() not in ['y', 'yes']:
            print("删除操作已取消。")
            return
    
    try:
        client.delete_credential(credential_id)
        print(f"凭证 {credential_id} 删除成功。")
            
    except Exception as e:
        print(f"删除凭证失败: {e}", file=sys.stderr)
        sys.exit(1)

def run_show(client, args, config):
    """执行凭证详情查看。"""
    credential_id = args.id
    
    try:
        cred_data = client.get_credential(credential_id)
        
        print("凭证详情:")
        print("-" * 40)
        print(f"凭证ID: {cred_data['id']}")
        print(f"名称: {cred_data['name']}")
        print(f"模型名称: {cred_data['model_name']}")
        print(f"基础URL: {cred_data['base_url']}")
        print(f"默认凭证: {'是' if cred_data.get('is_default', False) else '否'}")
        print(f"API密钥: {'已设置' if cred_data.get('api_key') else '未设置'}")
            
    except Exception as e:
        print(f"获取凭证详情失败: {e}", file=sys.stderr)
        sys.exit(1)

def run_set_default(client, args, config):
    """执行设置默认凭证。"""
    credential_id = args.id
    
    try:
        client.set_default_credential(credential_id)
        print(f"凭证 {credential_id} 已设置为默认凭证。")
            
    except Exception as e:
        print(f"设置默认凭证失败: {e}", file=sys.stderr)
        sys.exit(1)