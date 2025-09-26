# backend/app/tasks/content_extraction/directory_manager.py
import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from ...core.config import settings

class ContentExtractionDirectoryManager:
    """
    管理内容提取过程中的持久化目录结构。
    目录结构：/content_extraction/{file_hash}/{minio,libreoffice,mineru}
    """
    
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or "/home/hxdi/Kosmos/content_extraction")
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_file_hash(self, content_bytes: bytes, original_filename: str) -> str:
        """生成文件内容和文件名的组合哈希值作为目录名"""
        hasher = hashlib.sha256()
        hasher.update(content_bytes)
        hasher.update(original_filename.encode('utf-8'))
        return hasher.hexdigest()[:16]  # 使用前16位作为目录名
    
    def get_work_directory(self, content_bytes: bytes, original_filename: str) -> Path:
        """获取或创建工作目录"""
        file_hash = self._generate_file_hash(content_bytes, original_filename)
        work_dir = self.base_dir / file_hash
        work_dir.mkdir(parents=True, exist_ok=True)
        return work_dir
    
    def get_minio_directory(self, work_dir: Path) -> Path:
        """获取或创建minio子目录"""
        minio_dir = work_dir / "minio"
        minio_dir.mkdir(parents=True, exist_ok=True)
        return minio_dir
    
    def get_libreoffice_directory(self, work_dir: Path) -> Path:
        """获取或创建libreoffice子目录"""
        libreoffice_dir = work_dir / "libreoffice"
        libreoffice_dir.mkdir(parents=True, exist_ok=True)
        return libreoffice_dir
    
    def get_mineru_directory(self, work_dir: Path) -> Path:
        """获取或创建mineru子目录"""
        mineru_dir = work_dir / "mineru"
        mineru_dir.mkdir(parents=True, exist_ok=True)
        return mineru_dir
    
    def check_minio_cache(self, minio_dir: Path, original_filename: str) -> Optional[str]:
        """检查MinIO缓存，返回文件路径"""
        cache_file = minio_dir / original_filename
        if cache_file.exists():
            print(f"[CACHE] Found cached minio file: {cache_file}")
            return str(cache_file)
        return None
    
    def save_minio_cache(self, minio_dir: Path, original_filename: str, content_bytes: bytes) -> Path:
        """保存文件到minio缓存目录"""
        cached_file = minio_dir / original_filename
        cached_file.write_bytes(content_bytes)
        print(f"[CACHE] Saved minio file to cache: {cached_file}")
        return cached_file
    
    def check_libreoffice_cache(self, libreoffice_dir: Path, original_filename: str) -> Optional[bytes]:
        """检查LibreOffice缓存，返回PDF内容"""
        base_name = Path(original_filename).stem
        pdf_file = libreoffice_dir / f"{base_name}.pdf"
        if pdf_file.exists():
            print(f"[CACHE] Found cached LibreOffice PDF: {pdf_file}")
            return pdf_file.read_bytes()
        return None
    
    def save_libreoffice_cache(self, libreoffice_dir: Path, original_filename: str, pdf_content: bytes) -> Path:
        """保存LibreOffice转换结果到缓存"""
        base_name = Path(original_filename).stem
        pdf_file = libreoffice_dir / f"{base_name}.pdf"
        pdf_file.write_bytes(pdf_content)
        print(f"[CACHE] Saved LibreOffice PDF to cache: {pdf_file}")
        return pdf_file
    
    def check_mineru_cache(self, mineru_dir: Path) -> Optional[str]:
        """检查MinerU提取缓存，返回输出目录路径"""
        # 递归查找包含*_content_list.json的目录
        for root, dirs, files in os.walk(mineru_dir):
            for file in files:
                if file.endswith("_content_list.json"):
                    cached_path = str(root)
                    print(f"[CACHE] Found cached MinerU output: {cached_path}")
                    return cached_path
        return None
    
    def save_mineru_cache(self, mineru_dir: Path, output_path: str) -> None:
        """保存MinerU提取结果到缓存"""
        import shutil
        source_path = Path(output_path)
        if source_path.exists() and source_path.is_dir():
            # 目标路径使用源目录的名称
            target_path = mineru_dir / source_path.name
            if target_path.exists():
                shutil.rmtree(target_path)
            shutil.copytree(source_path, target_path)
            print(f"[CACHE] Saved MinerU output to cache: {target_path}")
        else:
            print(f"[CACHE] Warning: MinerU output path does not exist: {output_path}")
    
    def get_mineru_output_dir(self, mineru_dir: Path, pdf_filename: str) -> Path:
        """获取MinerU输出目录"""
        base_name = Path(pdf_filename).stem
        output_dir = mineru_dir / f"{base_name}_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def cleanup_directory(self, work_dir: Path) -> None:
        """清理工作目录（可选功能）"""
        if work_dir.exists():
            import shutil
            shutil.rmtree(work_dir)
            print(f"[CLEANUP] Removed directory: {work_dir}")
    
    def get_directory_info(self, work_dir: Path) -> Dict[str, Any]:
        """获取目录信息用于调试"""
        info = {
            "work_dir": str(work_dir),
            "exists": work_dir.exists(),
            "subdirs": {}
        }
        
        if work_dir.exists():
            for subdir_name in ["minio", "libreoffice", "mineru"]:
                subdir = work_dir / subdir_name
                info["subdirs"][subdir_name] = {
                    "exists": subdir.exists(),
                    "files": list(subdir.iterdir()) if subdir.exists() else []
                }
        
        return info