# backend/app/tasks/content_extraction/mineru_client.py
import subprocess
import os
import shutil
import time
from typing import Optional, Dict, Any
from pathlib import Path
from .directory_manager import ContentExtractionDirectoryManager

from ...core.config import settings

class MineruError(Exception):
    """Custom exception for MinerU extraction failures."""
    def __init__(self, message, stdout=None, stderr=None):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr

def find_executable(name: str) -> Optional[str]:
    """Check whether `name` is on PATH and marked as executable."""
    return shutil.which(name)

def extract_content(pdf_file_path: str, original_filename: str = None, dir_manager: Optional[ContentExtractionDirectoryManager] = None) -> Dict[str, Any]:
    """
    Runs the MinerU command-line tool and returns the path to the results.
    Uses persistent directory structure with caching support.

    Args:
        pdf_file_path: The path to the source PDF file.
        original_filename: Original filename for directory management.
        dir_manager: Directory manager instance for persistent storage.

    Returns:
        A dictionary containing the path to the result directory, stdout, stderr, and duration.
    """
    mineru_path = find_executable("mineru")
    if not mineru_path:
        raise FileNotFoundError("The 'mineru' command was not found.")

    # Initialize directory manager if not provided
    if dir_manager is None:
        dir_manager = ContentExtractionDirectoryManager()

    # Read PDF content for directory management
    with open(pdf_file_path, 'rb') as f:
        pdf_content = f.read()

    # Use original filename or derive from PDF path
    if original_filename is None:
        original_filename = Path(pdf_file_path).name

    # Get work directory and MinerU subdirectory
    work_dir = dir_manager.get_work_directory(pdf_content, original_filename)
    mineru_dir = dir_manager.get_mineru_directory(work_dir)

    print(f"[MinerU] Working directory: {work_dir}")
    print(f"[MinerU] MinerU directory: {mineru_dir}")

    # Check cache first
    cached_output = dir_manager.check_mineru_cache(mineru_dir)
    if cached_output:
        print(f"[MinerU] Using cached extraction result")
        return {
            "output_path": cached_output,
            "stdout": "[CACHED] Using previously extracted content",
            "stderr": "",
            "duration_seconds": 0
        }

    vlm_url = settings.MINERU_SERVER_URL
    vlm_source = settings.MINERU_SOURCE

    backends_to_try = [
        {"name": "vlm-http-client", "args": ["--url", vlm_url, "--source", vlm_source]},
        {"name": "pipeline", "args": []}
    ]

    # Get MinerU output directory
    pdf_filename = Path(pdf_file_path).name
    output_path = dir_manager.get_mineru_output_dir(mineru_dir, pdf_filename)

    # --- DEBUGGING: Print directory structure before processing ---
    print(f"--- [DEBUG] MinerU directory created: {mineru_dir} ---")
    print(f"--- [DEBUG] Input PDF path: {pdf_file_path} ---")
    print(f"--- [DEBUG] Output path: {output_path} ---")

    # Use tree command to show directory structure
    try:
        tree_result = subprocess.run(["tree", mineru_dir], capture_output=True, text=True)
        print(f"--- [DEBUG] Initial MinerU directory structure ---")
        print(tree_result.stdout)
    except FileNotFoundError:
        print("--- [DEBUG] tree command not available, using ls -la ---")
        ls_result = subprocess.run(["ls", "-la", mineru_dir], capture_output=True, text=True)
        print(ls_result.stdout)

    last_error = None
    for backend_config in backends_to_try:
        backend_name = backend_config["name"]
        print(f"  - Attempting MinerU extraction with backend: '{backend_name}'")

        command = [mineru_path, "-p", pdf_file_path, "-o", str(output_path), "-b", backend_name] + backend_config["args"]

        # --- DEBUGGING PRINT STATEMENTS ---
        print(f"--- [DEBUG] Executing MinerU command ---")
        print(f"  - Command: {' '.join(str(arg) for arg in command)}")
        # --- END DEBUGGING ---

        start_time = time.time()
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=1800, check=True
            )
            # --- DEBUGGING PRINT STATEMENTS ---
            print(f"--- [DEBUG] MinerU command finished ---")
            print(f"  - STDOUT: {result.stdout}")
            print(f"  - STDERR: {result.stderr}")

            # --- DEBUGGING: Print MinerU directory structure after processing ---
            print(f"--- [DEBUG] MinerU directory structure after processing ---")
            try:
                tree_result = subprocess.run(["tree", mineru_dir], capture_output=True, text=True)
                print(tree_result.stdout)
            except FileNotFoundError:
                ls_result = subprocess.run(["ls", "-laR", mineru_dir], capture_output=True, text=True)
                print(ls_result.stdout)

            # Calculate duration
            duration = time.time() - start_time

            # Find the final output path containing _content_list.json
            final_output_path = None
            for root, dirs, files in os.walk(output_path):
                for file in files:
                    if file.endswith('_content_list.json'):
                        final_output_path = root
                        break
                if final_output_path:
                    break

            if not final_output_path:
                raise MineruError("MinerU ran but no _content_list.json found in output directory.")

            # --- DEBUGGING: Print final output directory structure ---
            print(f"--- [DEBUG] Final output path: {final_output_path} ---")
            try:
                tree_result = subprocess.run(["tree", final_output_path], capture_output=True, text=True)
                print(f"--- [DEBUG] Final output directory structure ---")
                print(tree_result.stdout)
            except FileNotFoundError:
                ls_result = subprocess.run(["ls", "-la", final_output_path], capture_output=True, text=True)
                print(f"--- [DEBUG] Final output directory contents ---")
                print(ls_result.stdout)

            # Save to cache
            dir_manager.save_mineru_cache(mineru_dir, final_output_path)

            return {
                "output_path": final_output_path,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_seconds": duration
            }
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, MineruError) as e:
            stderr = e.stderr if hasattr(e, 'stderr') else str(e)
            stderr_str = stderr.strip() if stderr is not None else ""
            print(f"  - WARNING: MinerU backend '{backend_name}' failed. Stderr: {stderr_str}")
            last_error = e
            # Clean up for next attempt
            if os.path.exists(output_path):
                for item in os.listdir(output_path):
                    item_path = os.path.join(output_path, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)

    raise MineruError(f"All MinerU backends failed. Last error: {last_error}") from last_error