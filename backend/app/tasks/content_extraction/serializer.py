# backend/app/tasks/content_extraction/serializer.py
import os
import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from minio import Minio

from ...models import Asset
from ...models.asset import AssetType

def _create_or_get_asset(db: Session, minio: Minio, asset_bytes: bytes, asset_type: AssetType, file_type: str) -> Asset:
    """
    Helper function to create or get an Asset record.
    Note: This is duplicated from pipelines.py to make this module self-contained.
    A better long-term solution might be a shared 'db_helpers' module.
    """
    from ...utils.file_utils import calculate_file_hash
    from ...utils.storage_utils import generate_storage_path
    from ...core.config import settings
    from io import BytesIO

    asset_hash = calculate_file_hash(asset_bytes)
    asset = db.query(Asset).filter(Asset.asset_hash == asset_hash).first()
    if asset:
        asset.reference_count += 1
    else:
        object_name = f"{asset_hash}.{file_type}"
        storage_path = generate_storage_path(settings.MINIO_BUCKET_ASSETS, object_name)
        minio.put_object(settings.MINIO_BUCKET_ASSETS, object_name, BytesIO(asset_bytes), len(asset_bytes), f"image/{file_type}")
        asset = Asset(asset_hash=asset_hash, asset_type=asset_type, file_type=file_type, size=len(asset_bytes), storage_path=storage_path, reference_count=1)
    db.add(asset)
    db.flush()
    return asset

def process_mineru_output(mineru_output_path: str, db: Session, minio: Minio) -> Dict[str, Any]:
    """
    Processes the output directory of MinerU to generate the final canonical content.
    """
    print(f"[Serializer] Starting processing for MinerU output path: {mineru_output_path}")
    # 1. Register all assets first to get their IDs
    asset_path_to_uri = {}
    processed_assets = []
    images_dir = os.path.join(mineru_output_path, "images")
    print(f"[Serializer] Checking for images directory at: {images_dir}")
    if os.path.isdir(images_dir):
        print(f"[Serializer] Found images directory. Listing files...")
        image_files = os.listdir(images_dir)
        print(f"[Serializer] Found {len(image_files)} file(s) in images directory.")
        for filename in image_files:
            print(f"[Serializer] Processing asset file: {filename}")
            with open(os.path.join(images_dir, filename), "rb") as f:
                asset_content = f.read()
            
            asset_type = AssetType.table if "table" in filename else AssetType.figure
            file_ext = filename.split('.')[-1] if '.' in filename else 'png'
            
            asset = _create_or_get_asset(db, minio, asset_content, asset_type, file_ext)
            processed_assets.append(asset)
            print(f"[Serializer] Created/updated asset record with ID: {asset.id}")
            
            # Map the local file path to the canonical asset URI
            local_path_in_md = f"images/{filename}"
            asset_path_to_uri[local_path_in_md] = f"asset://{asset.id}"
    else:
        print(f"[Serializer] Images directory not found at: {images_dir}")

    # 2. Find and parse the _content_list.json
    content_list_path = next((os.path.join(mineru_output_path, f) for f in os.listdir(mineru_output_path) if f.endswith('_content_list.json')), None)
    if not content_list_path:
        print(f"[Serializer] No content list JSON found in: {mineru_output_path}")
        return {
            "canonical_content_bytes": b"",
            "page_mappings": [],
            "processed_assets": []
        }

    # Parse the content list JSON
    with open(content_list_path, 'r', encoding='utf-8') as f:
        content_data = json.load(f)

    # [FIX] Correctly handle the flat list structure of content_data by grouping items by page first.
    from collections import defaultdict
    page_groups = defaultdict(list)
    for item in content_data:
        page_groups[item.get("page_idx", -1)].append(item)

    markdown_lines = []
    page_mappings = []
    current_line = 1

    for page_idx in sorted(page_groups.keys()):
        if page_idx == -1: continue # Skip items with no page index

        items_on_page = page_groups[page_idx]
        page_start_line = current_line

        for item in items_on_page:
            item_type = item.get("type")
            if item_type == "text":
                content = item.get("text", "")
                markdown_lines.append(content)
            elif item_type in ["figure", "image"]:
                path = item.get("img_path", item.get("path", "")) # Accommodate both keys
                asset_uri = asset_path_to_uri.get(path, path)
                caption = item.get("caption", "")
                markdown_lines.append(f"![{caption}]({asset_uri})")
            elif item_type == "table":
                table_content = item.get("table_body", item.get("html", "")) # Accommodate both keys
                markdown_lines.append(table_content)
        
        page_end_line = len(markdown_lines)
        if page_end_line >= page_start_line:
            page_mappings.append({
                "page_number": page_idx + 1, # Convert 0-indexed to 1-indexed
                "line_from": page_start_line,
                "line_to": page_end_line
            })
        
        current_line = page_end_line + 1

    final_markdown = "\n".join(markdown_lines)
    
    # [DEBUG] Print the first 5 lines of the generated content before returning
    try:
        decoded_content = final_markdown
        debug_lines = decoded_content.splitlines()
        print("--- [DEBUG] Final Serializer Output (First 5 lines) ---")
        if not debug_lines:
            print("  <EMPTY CONTENT>")
        else:
            for i, line in enumerate(debug_lines[:5]):
                print(f"  Line {i+1}: {line}")
        print("-------------------------------------------------------")
    except Exception as e:
        print(f"--- [DEBUG] Error decoding or printing final content: {e} ---")

    print(f"[Serializer] Finished processing. Total assets processed: {len(processed_assets)}")
    return {
        "canonical_content_bytes": final_markdown.encode('utf-8'),
        "page_mappings": page_mappings,
        "processed_assets": processed_assets
    }

