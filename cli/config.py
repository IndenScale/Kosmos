import os
import sys
from dotenv import load_dotenv
from typing import Optional

class CliConfig:
    """
    通过按优先顺序解析命令行参数、环境变量和 .env 文件来管理 CLI 配置。
    """
    def __init__(self, dotenv_path: Optional[str] = None):
        """
        初始化配置加载器。

        Args:
            dotenv_path: .env 文件的路径。如果为 None，则在脚本位置的父目录中搜索。
        """
        if dotenv_path is None:
            # 假设此文件在 scripts/ 中, .env 在父目录中
            dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        
        print(f"--- [CLI_CONFIG_DEBUG] ---", file=sys.stderr)
        print(f"Attempting to load .env file from: {dotenv_path}", file=sys.stderr)
        
        found_dotenv = load_dotenv(dotenv_path=dotenv_path, override=True)
        
        if found_dotenv:
            print(".env file loaded successfully (overriding system variables).", file=sys.stderr)
        else:
            print("Warning: .env file not found at the specified path.", file=sys.stderr)
            
        # 打印关键环境变量的值以供调试
        print(f"KOSMOS_USERNAME: {os.getenv('KOSMOS_USERNAME')}", file=sys.stderr)
        print(f"KOSMOS_PASSWORD: {'*' * len(os.getenv('KOSMOS_PASSWORD', '')) if os.getenv('KOSMOS_PASSWORD') else None}", file=sys.stderr)
        print(f"KOSMOS_KS_ID: {os.getenv('KOSMOS_KS_ID')}", file=sys.stderr)
        print(f"KOSMOS_ASSESSMENT_SESSION_ID: {os.getenv('KOSMOS_ASSESSMENT_SESSION_ID')}", file=sys.stderr)
        print(f"KOSMOS_MAX_OUTPUT_CHARS: {os.getenv('KOSMOS_MAX_OUTPUT_CHARS', '200000')}", file=sys.stderr)
        print(f"--------------------------", file=sys.stderr)


    def resolve(self, arg_value: Optional[str], env_var_name: str) -> Optional[str]:
        """
        按以下优先顺序解析配置值：
        1. 命令行参数（如果提供）
        2. 环境变量（包括来自 .env 的值）

        Args:
            arg_value: 通过命令行参数传递的值。
            env_var_name: 要检查的环境变量的名称（例如 "KOSMOS_KS_ID"）。

        Returns:
            解析后的配置值，如果未找到则为 None。
        """
        if arg_value is not None:
            return arg_value
        return os.getenv(env_var_name)

    def require(self, arg_value: Optional[str], env_var_name: str, name_for_error: str) -> str:
        """
        解析一个配置值，如果未找到则退出并显示错误。

        Args:
            arg_value: 通过命令行参数传递的值。
            env_var_name: 要检查的环境变量的名称。
            name_for_error: 在错误消息中使用的值的用户友好名称（例如 "知识空间ID"）。

        Returns:
            解析后的配置值。
        """
        value = self.resolve(arg_value, env_var_name)
        if value is None:
            print(f"错误: 缺少必要的参数 '{name_for_error}'。", file=sys.stderr)
            print(f"请使用命令行参数或设置环境变量 {env_var_name}。", file=sys.stderr)
            sys.exit(1)
        return value
    
    def get_api_base_url(self) -> str:
        """
        获取API基础URL。
        
        Returns:
            API基础URL，默认为localhost:8011/api/v1/
        """
        return os.getenv('KOSMOS_API_URL', 'http://127.0.0.1:8011/api/v1/')

    def require_session_id(self, session_id_arg: Optional[str]) -> str:
        """
        按优先顺序获取 session_id: 环境变量 > 命令行参数 > 状态文件。
        这是 Agent 和人类用户通用的会话 ID 解析器。

        Args:
            session_id_arg: 通过 --session-id 命令行参数传递的值。

        Returns:
            解析后的 session_id。
        """
        # 1. 环境变量 (最高优先级，为 Agent 设计)
        session_id_from_env = os.getenv("KOSMOS_ASSESSMENT_SESSION_ID")
        if session_id_from_env:
            return session_id_from_env

        # 2. 命令行参数
        if session_id_arg:
            return session_id_arg
        
        # 3. 状态文件 (回退，为人类用户设计)
        from cli.commands.assessment import get_current_session # 延迟导入以避免循环依赖
        session_id_from_state = get_current_session()

        if session_id_from_state:
            return session_id_from_state

        # 如果都未找到
        print("错误: 未找到活动的评估会话。", file=sys.stderr)
        print("请确保设置了 KOSMOS_ASSESSMENT_SESSION_ID 环境变量，", file=sys.stderr)
        print("或使用 'assessment start-session' 命令启动一个会话，", file=sys.stderr)
        print("或使用 --session-id 参数指定。", file=sys.stderr)
        sys.exit(1)

    def get_max_output_chars(self, arg_value: Optional[int] = None) -> int:
        """
        获取最大输出字符数限制。
        
        Args:
            arg_value: 通过命令行参数传递的值。
            
        Returns:
            最大输出字符数，默认为200000。
        """
        # 1. 命令行参数（最高优先级）
        if arg_value is not None:
            return arg_value
            
        # 2. 环境变量
        env_value = os.getenv('KOSMOS_MAX_OUTPUT_CHARS')
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                print(f"警告: KOSMOS_MAX_OUTPUT_CHARS 环境变量值 '{env_value}' 不是有效整数，使用默认值。", file=sys.stderr)
        
        # 3. 默认值
        return 2500
