#!/usr/bin/env python3
"""
MineRU Client - A client for calling remote MineRU file parsing service.

This client reads configuration from .env file and provides a simple interface
to parse PDF files using the MineRU service.
"""

import os
import json
import base64
import argparse
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

    def parse_file(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """
        Parse a file using the MineRU service.

        Args:
            input_path: Path to the input file (PDF)
            output_path: Path to the output directory

        Returns:
            Dictionary containing the parsed results

        Raises:
            FileNotFoundError: If input file doesn't exist
            requests.RequestException: If API request fails
            ValueError: If response is invalid
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
        images_dir = output_dir / "images"
        images_dir.mkdir(exist_ok=True)

        print(f"Parsing file: {input_path}")
        print(f"Output directory: {output_path}")
        print(f"MineRU service URL: {self.parse_endpoint}")

        # Prepare the request
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

            # Make the API request
            try:
                print("Sending request to MineRU service...")
                response = requests.post(
                    self.parse_endpoint,
                    files=files,
                    data=data,
                    timeout=1000  # 10 minutes timeout
                )
                response.raise_for_status()

            except requests.exceptions.RequestException as e:
                raise requests.RequestException(f"Failed to call MineRU service: {e}")

        # Parse response
        try:
            result = response.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from server: {e}")

        print("Successfully received response from MineRU service")

        # Process and save results
        self._save_results(result, output_dir, images_dir)

        return result

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