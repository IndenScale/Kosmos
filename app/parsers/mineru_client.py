#!/usr/bin/env python3
"""
MineRU Client - A client for calling remote MineRU file parsing service.

This client reads configuration from .env file and provides a simple interface
to parse PDF files using the MineRU service.
支持多种调用方式：
1. SGLang Server模式（使用vlm-sglang-client后端）
2. 传统HTTP API模式
3. CLI命令行模式（作为回落方案）
"""

import os
import json
import base64
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from dotenv import load_dotenv


class MineRUClient:
    """Client for MineRU file parsing service."""

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the MineRU client.

        Args:
            base_url: Base URL of the MineRU service. If None, will read from .env file.
        """
        # Load environment variables
        load_dotenv()

        # Set base URL
        self.base_url = base_url or os.getenv('MINERU_BASE_URL', 'http://localhost:8000')
        self.base_url = self.base_url.rstrip('/')

        # API endpoint
        self.parse_endpoint = f"{self.base_url}/file_parse"

    def parse_file(self, input_path: str, output_path: str, backend: str = "pipeline", sglang_url: str = None) -> Dict[str, Any]:
        """
        Parse a file using the MineRU service.

        支持多种调用方式：
        1. SGLang Server模式（使用vlm-sglang-client后端）
        2. 传统HTTP API模式
        3. CLI命令行模式（作为回落方案）

        Args:
            input_path: Path to the input file (PDF)
            output_path: Path to the output directory
            backend: 解析后端类型，可选 'pipeline' 或 'vlm-sglang-client'
            sglang_url: SGLang Server的URL，默认为 None

        Returns:
            Dictionary containing the parsed results

        Raises:
            FileNotFoundError: If input file doesn't exist
            requests.RequestException: If API request fails
            ValueError: If response is invalid
            subprocess.CalledProcessError: If CLI command fails
        """
        input_file = Path(input_path)
        output_dir = Path(output_path)

        # Validate input file
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        if not input_file.suffix.lower() == '.pdf':
            raise ValueError("Only PDF files are supported")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Parsing file: {input_path}")
        print(f"Output directory: {output_path}")
        print(f"Backend: {backend}")

        # 优先尝试CLI方式（SGLang Server）
        if backend == "vlm-sglang-client" or sglang_url:
            try:
                return self._parse_with_cli(input_path, output_path, sglang_url or "http://10.17.99.15:30005")
            except Exception as e:
                print(f"CLI方式调用失败，尝试HTTP API方式: {e}")
                return self._parse_with_http(input_path, output_path)

        # 使用传统HTTP API方式
        return self._parse_with_http(input_path, output_path)

    def _save_results(self, result: Dict[str, Any], output_dir: Path, images_dir: Path):
        """
        Save the parsing results to the output directory.

        Args:
            result: The parsed result from MineRU service
            output_dir: Output directory path
            images_dir: Images directory path
        """
        if 'results' not in result:
            print("Warning: No 'results' key found in response")
            return

        results = result['results']

        for filename, content in results.items():
            print(f"Processing results for: {filename}")

            # Save markdown content
            if 'md_content' in content:
                md_file = output_dir / f"{filename}.md"
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write(content['md_content'])
                print(f"Saved markdown: {md_file}")

            # Save images
            if 'images' in content:
                for image_name, image_data in content['images'].items():
                    try:
                        # Remove data URL prefix if present
                        if image_data.startswith('data:image/'):
                            _, image_data = image_data.split(',', 1)

                        # Decode base64 image
                        image_bytes = base64.b64decode(image_data)

                        # Save image
                        image_path = images_dir / image_name
                        with open(image_path, 'wb') as f:
                            f.write(image_bytes)
                        print(f"Saved image: {image_path}")

                    except Exception as e:
                        print(f"Failed to save image {image_name}: {e}")

        # Save complete results as JSON
        results_file = output_dir / "results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Saved complete results: {results_file}")

        # Save content list (if available)
        content_list = []
        for filename, content in results.items():
            item = {
                'filename': filename,
                'has_md': 'md_content' in content,
                'image_count': len(content.get('images', {}))
            }
            content_list.append(item)

        content_list_file = output_dir / "content_list.json"
        with open(content_list_file, 'w', encoding='utf-8') as f:
            json.dump(content_list, f, ensure_ascii=False, indent=2)
        print(f"Saved content list: {content_list_file}")

    def _parse_with_cli(self, input_path: str, output_path: str, sglang_url: str) -> Dict[str, Any]:
        """
        使用CLI命令行方式调用SGLang Server的MineRU后端（同步调用）

        Args:
            input_path: 输入PDF文件路径
            output_path: 输出目录路径
            sglang_url: SGLang Server的URL

        Returns:
            Dict containing the parsed results
        """
        input_file = Path(input_path)
        output_dir = Path(output_path)

        print(f"使用CLI方式调用SGLang Server: {sglang_url}")

        # 构建CLI命令
        cmd = [
            "mineru",
            "-p", str(input_file),
            "-o", str(output_dir),
            "-b", "vlm-sglang-client",
            "-u", sglang_url,
            "--source", "modelscope"
        ]

        print(f"执行命令: {' '.join(cmd)}")

        # 同步执行CLI命令
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30分钟超时
                cwd=output_dir
            )

            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, result.stdout, result.stderr
                )

            print("CLI命令执行成功")
            if result.stdout:
                print(f"标准输出: {result.stdout}")

        except subprocess.TimeoutExpired:
            raise RuntimeError("CLI命令执行超时（30分钟）")

        # 检查输出目录是否包含结果文件
        results_file = output_dir / "results.json"
        if results_file.exists():
            with open(results_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # 如果没有results.json，尝试从markdown和images构建结果
        return self._build_result_from_files(output_dir, input_file.name)

    def _parse_with_http(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """
        使用传统HTTP API方式调用MineRU服务（同步调用）

        Args:
            input_path: 输入PDF文件路径
            output_path: 输出目录路径

        Returns:
            Dict containing the parsed results
        """
        input_file = Path(input_path)
        output_dir = Path(output_path)
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        print(f"使用HTTP API方式调用: {self.parse_endpoint}")

        # 准备HTTP请求
        with open(input_file, 'rb') as f:
            files = {
                'files': (input_file.name, f, 'application/pdf')
            }

            data = {
                'return_middle_json': 'false',
                'return_model_output': 'false',
                'return_md': 'true',
                'return_images': 'true',
                'end_page_id': '99999',
                'parse_method': 'auto',
                'start_page_id': '0',
                'lang_list': 'ch',
                'output_dir': './output',
                'server_url': 'string',
                'return_content_list': 'false',
                'backend': 'pipeline',
                'table_enable': 'true',
                'formula_enable': 'true'
            }

            # 发送HTTP请求
            try:
                print("发送HTTP请求到MineRU服务...")
                response = requests.post(
                    self.parse_endpoint,
                    files=files,
                    data=data,
                    timeout=1800  # 30分钟超时
                )
                response.raise_for_status()

            except requests.exceptions.RequestException as e:
                raise requests.RequestException(f"调用MineRU服务失败: {e}")

        # 解析响应
        try:
            result = response.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"服务器返回无效的JSON响应: {e}")

        print("成功接收到MineRU服务的响应")

        # 标准化返回格式，确保与CLI方式一致
        if 'results' not in result:
            result['results'] = {}

        # 处理每个文件的结果，确保images格式一致
        for filename, content in result.get('results', {}).items():
            if 'images' in content and isinstance(content['images'], dict):
                # 将images从dict格式转换为list格式，与CLI方式保持一致
                images_dict = content['images']
                images_list = []
                for img_name, img_data in images_dict.items():
                    images_list.append({
                        'filename': img_name,
                        'path': str(images_dir / img_name) if images_dir.exists() else None,
                        'base64': None
                    })
                content['images'] = images_list

        # 处理并保存结果
        self._save_results(result, output_dir, images_dir)

        return result

    def _build_result_from_files(self, output_dir: Path, filename: str) -> Dict[str, Any]:
        """
        当没有results.json时，从markdown和images文件构建结果

        Args:
            output_dir: 输出目录
            filename: 输入文件名

        Returns:
            Dict containing the parsed results
        """
        result = {
            "backend": "vlm-sglang-client",
            "version": "unknown",
            "results": {}
        }

        # 查找markdown文件
        md_files = list(output_dir.glob("*.md"))
        if not md_files:
            # 如果没有找到markdown文件，创建一个空的内容
            md_content = ""
        else:
            md_file = md_files[0]  # 取第一个找到的markdown文件
            with open(md_file, 'r', encoding='utf-8') as f:
                md_content = f.read()

        # 查找图片文件
        images_dir = output_dir / "images"
        images_info = []

        if images_dir.exists():
            for img_file in images_dir.glob("*"):
                if img_file.is_file() and img_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                    images_info.append({
                        'filename': img_file.name,
                        'path': str(img_file),
                        'base64': None  # 不编码base64，保持与HTTP API返回格式一致
                    })

        result["results"][filename] = {
            "md_content": md_content,
            "images": images_info
        }

        return result


def main():
    """Main function for command line interface."""
    parser = argparse.ArgumentParser(description='MineRU Client - Parse PDF files using MineRU service')
    parser.add_argument('input_path', help='Path to the input PDF file')
    parser.add_argument('output_path', help='Path to the output directory')
    parser.add_argument('--base-url', help='Base URL of MineRU service (overrides .env file)')

    args = parser.parse_args()

    try:
        # Create client
        client = MineRUClient(base_url=args.base_url)

        # Parse file
        result = client.parse_file(args.input_path, args.output_path)

        print("\n" + "="*50)
        print("PARSING COMPLETED SUCCESSFULLY")
        print("="*50)
        print(f"Backend: {result.get('backend', 'Unknown')}")
        print(f"Version: {result.get('version', 'Unknown')}")

        if 'results' in result:
            print(f"Processed files: {len(result['results'])}")
            for filename in result['results'].keys():
                print(f"  - {filename}")

        print(f"\nAll results saved to: {args.output_path}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())