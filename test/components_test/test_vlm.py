#!/usr/bin/env python3
"""
测试VLM服务是否正常工作
"""
import base64
import requests
import json
from pathlib import Path

def encode_image_to_base64(image_path):
    """将图片编码为base64字符串"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def test_vlm_service():
    # 选择一个测试图片
    test_image = "/home/hxdi/Kosmos/test_data/浙江电信数据安全评估采集收集/word/media/image91.png"
    
    # 检查图片是否存在
    if not Path(test_image).exists():
        print(f"图片文件不存在: {test_image}")
        return
    
    # 编码图片
    encoded_image = encode_image_to_base64(test_image)
    
    # 构建请求数据
    payload = {
        "model": "kimi-vl-2506",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请详细描述这幅图片的内容，并提取3-5个最相关的关键词作为标签。"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encoded_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1024
    }
    
    # 发送请求到VLM服务
    url = "http://127.0.0.1:30000/v1/chat/completions"
    
    try:
        print("正在测试VLM服务...")
        response = requests.post(url, json=payload, timeout=30)
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("VLM服务测试成功!")
            print(f"生成的描述: {result['choices'][0]['message']['content']}")
        else:
            print("VLM服务测试失败!")
            
    except Exception as e:
        print(f"请求VLM服务时出错: {e}")

if __name__ == "__main__":
    test_vlm_service()