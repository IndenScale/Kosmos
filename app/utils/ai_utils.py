import openai
import os
from typing import List, Dict, Any
import json

def get_openai_client():
    """获取OpenAI客户端实例"""
    return openai.OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL")
    )

class AIUtils:
    def __init__(self):
        self.openai_client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url = os.getenv("OPENAI_BASE_URL")
        )
        self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3")
        self.llm_model = os.getenv("OPENAI_LLM_MODEL", "deepseek-v3")
        self.vlm_model = os.getenv("OPENAI_VLM_MODEL", "qwen-vl-plus")

    def get_embedding(self, text: str) -> List[float]:
        """获取文本的向量嵌入"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"获取嵌入向量失败: {str(e)}")
    def _clean_json_response(self, response: str) -> str:
        """清理AI响应中的markdown代码块标记和其他格式"""
        # 移除markdown代码块标记
        response = response.replace('```json', '').replace('```', '')

        # 移除可能的前后空白字符和换行符
        response = response.strip()

        # 如果响应包含多行，尝试找到JSON部分
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                return line

    def get_tags(self, content: str, tag_directory: Dict[str, Any], mag_tags:int = 40) -> List[str]:
        """根据内容和标签字典生成标签"""
        try:
            prompt = f"""
你是一个专业的文档标签生成助手。请根据以下内容和标签字典，为文档片段生成合适的标签。

**重要：如果内容主要是目录、索引或导航信息，请直接返回空列表[]**

目录特征识别：
- 包含大量链接引用（如 [图380 01-数据安全管理制度列表 [1419](#_Toc256002531)]）
- 主要由标题列表、页码、章节编号组成
- 缺乏实质性描述内容，主要是导航信息
- 包含大量重复的格式化模式

标签字典：
{json.dumps(tag_directory, ensure_ascii=False, indent=2)}

文档内容：
{content}

请从标签字典中选择最相关的标签，返回JSON格式的标签列表。例如：["技术文档", "Python", "API设计"]

要求：
1. **首先判断内容是否为目录/索引，如果是则直接返回[]**
2. 只返回JSON格式的标签列表
3. 标签必须来自提供的标签字典
4. 最多选择5个最相关的标签
5. 如果没有合适的标签，返回空列表[]
"""

            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            result = response.choices[0].message.content.strip()

            result = self._clean_json_response(result)
            if not result:
                result = "[]"
            # 提取第一个和最后一个{}之间的内容
            try:
                first_brace = result.index('[')
                last_brace = result.rindex(']')
                json_str = result[first_brace:last_brace+1]
                tags = json.loads(json_str)

                # 新增：限制标签数量不超过20个
                if len(tags) > mag_tags:
                    tags = tags[:mag_tags]
                    print(f"警告：标签数量超过20个，已自动截断")

            except (ValueError, json.JSONDecodeError) as e:
                print(f"JSON解析失败: {str(e)}, 原始内容: {result}")
                return []
            return tags if isinstance(tags, list) else []

        except Exception as e:
            print(f"标签生成失败: {str(e)}")
            return []

    def get_image_description(self, image_path: str) -> str:
        """获取图片描述"""
        try:
            import base64

            # 读取图片并转换为base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            response = self.openai_client.chat.completions.create(
                model=self.vlm_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "请详细描述这张图片的内容，包括主要元素、文字信息、图表数据等。描述要准确、详细，便于理解图片传达的信息。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"图片描述生成失败: {str(e)}")
            return f"[图片描述生成失败: {image_path}]"