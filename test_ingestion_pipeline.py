#!/usr/bin/env python3
"""
文档摄入流水线测试脚本

用于测试文档处理和chunk分割效果，不进行持久化操作
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.processors.processor_factory import ProcessorFactory
from app.utils.intelligent_text_splitter import IntelligentTextSplitter
from app.utils.ai_utils import AIUtils


class IngestionPipelineTester:
    """摄入流水线测试器"""
    
    def __init__(self):
        self.processor_factory = ProcessorFactory()
        self.intelligent_splitter = IntelligentTextSplitter()
        self.ai_utils = AIUtils()
        
    def test_document_processing(self, file_path: str) -> Dict[str, Any]:
        """测试文档处理流程"""
        print(f"🔍 测试文档: {file_path}")
        
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        
        try:
            # 1. 获取处理器
            processor = self.processor_factory.get_processor(file_path)
            print(f"📋 使用处理器: {processor.__class__.__name__}")
            
            # 2. 提取内容（可能是结构化块或纯文本）
            print("🔄 提取文档内容...")
            raw_content, screenshot_paths = processor.extract_content(file_path)
            
            # 3. 将内容统一为结构化块列表
            if isinstance(raw_content, str):
                content_blocks = [{'type': 'text', 'content': raw_content}]
                original_content_length = len(raw_content)
            elif isinstance(raw_content, list):
                content_blocks = raw_content
                # 估算原始内容长度
                original_content_length = sum(len(self.intelligent_splitter._format_block_to_markdown(b)) for b in content_blocks)
            else:
                raise TypeError(f"不支持的内容类型: {type(raw_content)}")

            # 4. 分析原始内容
            print(f"📄 原始内容长度 (估算): {original_content_length} 字符")
            print(f"🧱 内容块数量: {len(content_blocks)}")
            print(f"📸 生成截图数量: {len(screenshot_paths)}")
            
            # 5. 使用智能分割器分割文本
            print("✂️ 使用智能分割器分割文本为chunks...")
            chunks = self.intelligent_splitter.split(content_blocks)
            print(f"📦 分割后chunks数量: {len(chunks)}")
            
            # 6. 分析chunks质量
            chunk_analysis = self._analyze_chunks(chunks)
            
            # 7. 生成测试报告
            report = {
                "file_path": file_path,
                "processor": processor.__class__.__name__,
                "original_content_length": original_content_length,
                "block_count": len(content_blocks),
                "screenshot_count": len(screenshot_paths),
                "chunk_count": len(chunks),
                "chunk_analysis": chunk_analysis,
                "sample_chunks": self._get_sample_chunks(chunks, 3)
            }
            
            return report
            
        except Exception as e:
            return {"error": f"处理失败: {str(e)}"}
    
    def _analyze_chunks(self, chunks: List[str]) -> Dict[str, Any]:
        """分析chunks质量"""
        if not chunks:
            return {"total": 0, "empty": 0, "short": 0, "normal": 0, "long": 0}
        
        empty_chunks = 0
        short_chunks = 0  # < 50字符
        normal_chunks = 0  # 50-1000字符
        long_chunks = 0  # > 1000字符
        
        length_distribution = []
        
        for chunk in chunks:
            content = chunk.strip()
            length = len(content)
            length_distribution.append(length)
            
            if length == 0:
                empty_chunks += 1
            elif length < 50:
                short_chunks += 1
            elif length <= 1000:
                normal_chunks += 1
            else:
                long_chunks += 1
        
        avg_length = sum(length_distribution) / len(length_distribution)
        
        return {
            "total": len(chunks),
            "empty": empty_chunks,
            "short": short_chunks,
            "normal": normal_chunks,
            "long": long_chunks,
            "average_length": round(avg_length, 2),
            "min_length": min(length_distribution),
            "max_length": max(length_distribution),
            "quality_score": self._calculate_quality_score(empty_chunks, short_chunks, normal_chunks, long_chunks)
        }
    
    def _calculate_quality_score(self, empty: int, short: int, normal: int, long: int) -> float:
        """计算chunks质量分数（0-100）"""
        total = empty + short + normal + long
        if total == 0:
            return 0.0
        
        # 质量分数计算：
        # - 空chunk: -10分
        # - 短chunk: -5分
        # - 正常chunk: +10分
        # - 长chunk: +5分
        score = (normal * 10 + long * 5 - short * 5 - empty * 10) / total
        
        # 归一化到0-100范围
        normalized_score = max(0, min(100, (score + 10) * 5))
        
        return round(normalized_score, 2)
    
    def _get_sample_chunks(self, chunks: List[str], count: int = 3) -> List[Dict[str, Any]]:
        """获取样本chunks"""
        if not chunks:
            return []
        
        sample_chunks = []
        
        # 选择不同位置的chunks作为样本
        indices = []
        if len(chunks) >= count:
            indices = [0, len(chunks) // 2, len(chunks) - 1]
        else:
            indices = list(range(len(chunks)))
        
        for i in indices[:count]:
            chunk = chunks[i]
            sample_chunks.append({
                "index": i,
                "length": len(chunk),
                "preview": chunk[:200] + "..." if len(chunk) > 200 else chunk,
                "is_valid": len(chunk.strip()) >= 50  # 判断是否为有效chunk
            })
        
        return sample_chunks
    
    def print_report(self, report: Dict[str, Any]):
        """打印测试报告"""
        if "error" in report:
            print(f"❌ 错误: {report['error']}")
            return
        
        print("\n" + "="*60)
        print("📊 文档处理测试报告")
        print("="*60)
        
        print(f"📁 文件路径: {report['file_path']}")
        print(f"🔧 处理器: {report['processor']}")
        print(f"📄 原始内容长度: {report['original_content_length']:,} 字符")
        print(f"🧱 内容块数量: {report['block_count']}")
        print(f"📸 截图数量: {report['screenshot_count']}")
        print(f"📦 Chunk数量: {report['chunk_count']}")
        
        analysis = report['chunk_analysis']
        print(f"\n📈 Chunk质量分析:")
        print(f"  • 总数: {analysis['total']}")
        print(f"  • 空chunk: {analysis['empty']} ({analysis['empty']/analysis['total']*100:.1f}%)")
        print(f"  • 短chunk (<50字符): {analysis['short']} ({analysis['short']/analysis['total']*100:.1f}%)")
        print(f"  • 正常chunk (50-1000字符): {analysis['normal']} ({analysis['normal']/analysis['total']*100:.1f}%)")
        print(f"  • 长chunk (>1000字符): {analysis['long']} ({analysis['long']/analysis['total']*100:.1f}%)")
        print(f"  • 平均长度: {analysis['average_length']:.1f} 字符")
        print(f"  • 长度范围: {analysis['min_length']} - {analysis['max_length']} 字符")
        print(f"  • 质量分数: {analysis['quality_score']}/100")
        
        print(f"\n📝 样本Chunks:")
        for i, sample in enumerate(report['sample_chunks'], 1):
            status = "✅ 有效" if sample['is_valid'] else "❌ 无效"
            print(f"  {i}. Chunk #{sample['index']} ({sample['length']} 字符) {status}")
            print(f"     预览: {sample['preview']}")
            print()
    
    def test_multiple_documents(self, document_dir: str = "data/documents"):
        """测试多个文档"""
        print(f"🔍 扫描文档目录: {document_dir}")
        
        if not os.path.exists(document_dir):
            print(f"❌ 目录不存在: {document_dir}")
            return
        
        # 获取所有支持的文件
        supported_extensions = self.processor_factory.get_supported_extensions()
        files = []
        
        for file_path in Path(document_dir).iterdir():
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                files.append(str(file_path))
        
        if not files:
            print("❌ 没有找到支持的文档文件")
            return
        
        print(f"📁 找到 {len(files)} 个文档文件")
        
        # 测试每个文件
        for file_path in files:
            print(f"\n{'='*60}")
            report = self.test_document_processing(file_path)
            self.print_report(report)


def main():
    """主函数"""
    print("🚀 启动文档摄入流水线测试")
    
    tester = IngestionPipelineTester()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 测试指定文件
        file_path = sys.argv[1]
        report = tester.test_document_processing(file_path)
        tester.print_report(report)
    else:
        # 测试所有文档
        tester.test_multiple_documents()


if __name__ == "__main__":
    main() 