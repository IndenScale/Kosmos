# app/utils/db_types.py

import json
import logging
from sqlalchemy import TypeDecorator, TEXT

# 配置日志
logger = logging.getLogger(__name__)


class JSONEncodedDict(TypeDecorator):
    """自动处理 JSON 字典与字符串的转换"""
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, dict):
                try:
                    json_str = json.dumps(value, ensure_ascii=False)
                    logger.debug(f"字典序列化成功，JSON长度: {len(json_str)} 字符")
                    return json_str
                except Exception as e:
                    logger.error(f"字典序列化失败: {e}")
                    raise e
            elif isinstance(value, str):
                # 如果已经是字符串，先验证是否为有效JSON
                try:
                    parsed = json.loads(value)
                    logger.debug(f"字符串验证为有效JSON，长度: {len(value)} 字符")
                    return value
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"字符串不是有效JSON: {e}")
                    raise ValueError(f"无效的JSON字符串: {e}")
            else:
                logger.error(f"不支持的数据类型: {type(value)}")
                raise TypeError(f"不支持的数据类型: {type(value)}")
        
        logger.debug("输入值为None，返回空字典")
        return "{}"

    def process_result_value(self, value, dialect):
        if value:
            try:
                parsed = json.loads(value)
                logger.debug(f"JSON解析成功，字典键数: {len(parsed) if isinstance(parsed, dict) else 'N/A'}")
                return parsed
            except (TypeError, json.JSONDecodeError) as e:
                logger.error(f"JSON解析失败: {e}")
                return {}
        
        logger.debug("数据库值为空，返回空字典")
        return {}