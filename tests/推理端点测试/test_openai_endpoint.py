#!/usr/bin/env python3

import os
import sys
import requests
from typing import Dict, Any

# 测试配置
TEST_CONFIGS = [
    {
        "base_url": "http://10.17.99.14:9997/v1",
        "model": "qwen3:8b-int4",
        "api_key": ""
    },
    {
        "base_url": "http://10.17.99.13:9997/v1",
        "model": "Qwen3-Embedding-0.6B",
        "api_key": ""
    }
]

import openai

# 检查端点上的可用模型
try:
    client = openai.Client(api_key="", base_url="http://10.17.99.14:9997/v1")

    # 获取模型列表
    models = client.models.list()
    print("可用的模型:")
    for model in models.data:
        print(f"- {model.id}")

    # # 测试聊天功能
    # response = client.chat.completions.create(
    #     model="qwen3:8b-int4",
    #     messages=[
    #         {"role": "user", "content": "What is the largest animal?"}
    #     ],
    #     max_tokens=512,
    #     temperature=0.7
    # )
    # print("\n聊天测试结果:")
    # print(response)
except Exception as e:
    print(f"发生错误: {str(e)}")