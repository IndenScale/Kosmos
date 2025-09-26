# backend/app/tasks/content_extraction/libreoffice_client.py
import subprocess
import os
import shutil
from typing import Optional
from pathlib import Path
from .directory_manager import ContentExtractionDirectoryManager

class ConversionError(Exception):
    """Custom exception for LibreOffice conversion failures."""
    def __init__(self, message, stdout=None, stderr=None):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr

def find_executable(name: str) -> Optional[str]:
    """Check whether `name` is on PATH and marked as executable."""
    return shutil.which(name)

def convert_to_pdf(content_bytes: bytes, original_filename: str = "input_file", dir_manager: Optional[ContentExtractionDirectoryManager] = None) -> bytes:
    """
    Converts a document's byte content to PDF using the LibreOffice command-line tool.
    Uses persistent directory structure with caching support.

    Args:
        content_bytes: The byte content of the source document.
        original_filename: The original filename with extension, used as a hint for the input format.
        dir_manager: Directory manager instance for persistent storage.

    Returns:
        The byte content of the converted PDF file.

    Raises:
        FileNotFoundError: If the 'libreoffice' executable is not found in the system's PATH.
        ConversionError: If the LibreOffice command fails to execute or returns an error.
    """
    # Initialize directory manager if not provided
    if dir_manager is None:
        dir_manager = ContentExtractionDirectoryManager()
    
    # Get work directory and LibreOffice subdirectory
    work_dir = dir_manager.get_work_directory(content_bytes, original_filename)
    libreoffice_dir = dir_manager.get_libreoffice_directory(work_dir)
    
    print(f"[LibreOffice] Working directory: {work_dir}")
    print(f"[LibreOffice] LibreOffice directory: {libreoffice_dir}")
    
    # Check cache first
    cached_pdf = dir_manager.check_libreoffice_cache(libreoffice_dir, original_filename)
    if cached_pdf:
        print(f"[LibreOffice] Using cached PDF conversion")
        return cached_pdf
    
    libreoffice_path = find_executable("libreoffice")
    if not libreoffice_path:
        raise FileNotFoundError(
            "The 'libreoffice' command was not found. Please ensure LibreOffice is installed and accessible in the system's PATH."
        )

    # Create a filename with the original extension to help LibreOffice
    # Extract just the filename part to avoid path traversal issues
    safe_filename = os.path.basename(original_filename)
    input_path = libreoffice_dir / safe_filename
    
    with open(input_path, "wb") as f:
        f.write(content_bytes)
        
    # Debug: Check if file was written correctly
    if not os.path.exists(input_path):
        raise ConversionError(f"Failed to write input file to {input_path}")
    
    file_size = os.path.getsize(input_path)
    print(f"[DEBUG] Input file written: {input_path}, size: {file_size} bytes")

    # Create a dedicated user profile directory for this conversion.
    # This prevents conflicts and issues with user permissions in server environments.
    user_profile_dir = libreoffice_dir / "libreoffice_profile"
    user_profile_dir.mkdir(exist_ok=True)

    command = [
        libreoffice_path,
        f"-env:UserInstallation=file://{user_profile_dir}", # Use an isolated user profile with file:// protocol
        "--headless",          # Run without a GUI
        "--convert-to", "pdf", # Specify the output format
        "--outdir", str(libreoffice_dir),  # Set the output directory
        str(input_path)
    ]

    try:
        # Create environment with proper Java configuration
        env = os.environ.copy()
        env['JAVA_HOME'] = '/usr/lib/jvm/java-21-openjdk-amd64'
        
        print(f"[DEBUG] LibreOffice command: {' '.join(command)}")
        print(f"[DEBUG] Working directory: {libreoffice_dir}")
        print(f"[DEBUG] Files in libreoffice_dir before conversion: {list(libreoffice_dir.iterdir())}")
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300, # 5-minute timeout for conversion
            check=True,  # Raise CalledProcessError on non-zero exit codes
            env=env      # Use modified environment with disabled Java
        )
        
        print(f"[DEBUG] LibreOffice stdout: {result.stdout}")
        print(f"[DEBUG] LibreOffice stderr: {result.stderr}")
        print(f"[DEBUG] Files in libreoffice_dir after conversion: {list(libreoffice_dir.iterdir())}")
    except FileNotFoundError:
        raise FileNotFoundError(f"Failed to execute '{libreoffice_path}'. Is it correctly installed?")
    except subprocess.TimeoutExpired as e:
        raise ConversionError(
            f"LibreOffice conversion timed out after {e.timeout} seconds.",
            stdout=e.stdout,
            stderr=e.stderr
        )
    except subprocess.CalledProcessError as e:
        error_message = (
            f"LibreOffice conversion failed with exit code {e.returncode}.\n"
            f"Command: {' '.join(command)}\n"
            f"Stderr: {e.stderr.strip()}"
        )
        raise ConversionError(error_message, stdout=e.stdout, stderr=e.stderr)

    base_filename, _ = os.path.splitext(safe_filename)
    output_path = libreoffice_dir / f"{base_filename}.pdf"

    if not output_path.exists():
        pdf_files = [f for f in libreoffice_dir.iterdir() if f.suffix == '.pdf']
        if not pdf_files:
            raise ConversionError(
                "LibreOffice command executed successfully, but no PDF file was generated.",
                stdout=result.stdout,
                stderr=result.stderr
            )
        output_path = pdf_files[0]

    # Read the PDF content
    pdf_content = output_path.read_bytes()
    
    # Save to cache
    dir_manager.save_libreoffice_cache(libreoffice_dir, original_filename, pdf_content)
    
    return pdf_content
