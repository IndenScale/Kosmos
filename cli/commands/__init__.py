'''
CLI命令模块的包初始化文件。
'''
from .assessment_finding import register_subparser as register_assessment_finding_subparser

def register_all_subparsers(subparsers, parent_parser):
    """注册所有CLI命令的子解析器。"""
    # 注册所有命令
    register_assessment_finding_subparser(subparsers, parent_parser)