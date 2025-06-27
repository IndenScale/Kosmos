#!/bin/bash

# 安装截图功能相关依赖包
echo "正在使用uv虚拟环境安装截图功能依赖包..."

# 激活uv虚拟环境
source .venv/bin/activate

# 安装PDF处理和截图相关依赖
echo "安装PyMuPDF（用于PDF处理和截图）..."
uv pip install PyMuPDF>=1.23.0

echo "安装pdf2image（用于PDF页面截图）..."
uv pip install pdf2image>=3.1.0

echo "安装python-docx（用于DOCX文档处理）..."
uv pip install python-docx>=0.8.11

echo "安装python-pptx（用于PPTX文档处理）..."
uv pip install python-pptx>=0.6.21

# 检查系统依赖
echo "检查系统依赖..."

# 检查poppler-utils（pdf2image需要）
if ! command -v pdftoppm &> /dev/null; then
    echo "警告: 未找到poppler-utils，pdf2image可能无法正常工作"
    echo "Ubuntu/Debian系统请运行: sudo apt-get install poppler-utils"
    echo "CentOS/RHEL系统请运行: sudo yum install poppler-utils"
    echo "macOS系统请运行: brew install poppler"
fi

# 检查LibreOffice（用于文档转PDF）
if ! command -v libreoffice &> /dev/null; then
    echo "警告: 未找到LibreOffice，某些文档转换功能可能无法使用"
    echo "Ubuntu/Debian系统请运行: sudo apt-get install libreoffice"
    echo "CentOS/RHEL系统请运行: sudo yum install libreoffice"
    echo "macOS系统请运行: brew install --cask libreoffice"
fi

echo "依赖包安装完成！"
echo "注意：如果缺少系统依赖，请按上述提示安装相应的系统包。" 