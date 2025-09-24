#!/usr/bin/env python3
import os
import json
from typing import Dict, Any, List

def process_mineru_output_test(mineru_output_path: str) -> Dict[str, Any]:
    """
    Test version of the serializer function
    """
    # Find and parse the _content_list.json
    content_list_path = next((os.path.join(mineru_output_path, f) for f in os.listdir(mineru_output_path) if f.endswith('_content_list.json')), None)
    if not content_list_path:
        raise FileNotFoundError(f"'_content_list.json' not found in MinerU output: {mineru_output_path}")

    with open(content_list_path, 'r', encoding='utf-8') as f:
        content_data = json.load(f)

    # Build Markdown and Page Mappings
    markdown_lines = []
    page_mappings = []
    current_page = None
    page_start_line = 1

    for item in content_data:
        item_page = item.get("page_idx", 0) + 1  # Convert from 0-based to 1-based
        
        # Check if we've moved to a new page
        if current_page is not None and item_page != current_page:
            # Finalize the previous page mapping
            page_end_line = len(markdown_lines)
            if page_end_line >= page_start_line:
                page_mappings.append({
                    "page_number": current_page,
                    "line_from": page_start_line,
                    "line_to": page_end_line
                })
            page_start_line = len(markdown_lines) + 1
        
        current_page = item_page
        
        if item["type"] == "text":
            markdown_lines.append(item["text"])
        elif item["type"] == "image":
            img_path = item.get("img_path", "")
            caption = " ".join(item.get("image_caption", []))
            markdown_lines.append(f"![{caption}]({img_path})")
        elif item["type"] == "table":
            table_content = item.get("html", item.get("content", ""))
            markdown_lines.append(table_content)
    
    # Finalize the last page mapping
    if current_page is not None:
        page_end_line = len(markdown_lines)
        if page_end_line >= page_start_line:
            page_mappings.append({
                "page_number": current_page,
                "line_from": page_start_line,
                "line_to": page_end_line
            })

    final_markdown = "\n".join(markdown_lines)
    
    return {
        "canonical_content_bytes": final_markdown.encode('utf-8'),
        "page_mappings": page_mappings
    }

# Test the serializer
mineru_output_path = "/home/hxdi/Kosmos/content_extraction/8416bef83f83e20b/mineru/7aef310a-cfce-4580-9d2a-e7ef20c89630_output/7aef310a-cfce-4580-9d2a-e7ef20c89630/vlm"

try:
    result = process_mineru_output_test(mineru_output_path)
    print(f"Success! Generated {len(result['canonical_content_bytes'])} bytes of content")
    print(f"Number of page mappings: {len(result['page_mappings'])}")
    print(f"Content preview: {result['canonical_content_bytes'][:500].decode('utf-8')}...")
    print(f"\nPage mappings: {result['page_mappings'][:3]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()