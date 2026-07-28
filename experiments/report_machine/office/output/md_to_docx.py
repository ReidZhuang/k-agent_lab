#!/usr/bin/env python3
"""
Markdown → DOCX 转换工具

将生成的 md 报告转换为带基本格式的 Word 文档。
需安装 python-docx（已在 stock_agent 环境中）。

用法:
  conda run -n stock_agent python md_to_docx.py input.md output.docx
  conda run -n stock_agent python md_to_docx.py --dir output/  # 批量转换整个目录
"""
import os
import sys
import argparse
import re
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def md_to_docx(md_text: str) -> Document:
    """将 Markdown 文本转换为 python-docx Document 对象

    Args:
        md_text: Markdown 格式的文本

    Returns:
        python-docx Document 实例
    """
    doc = Document()

    # ── 设置默认字体 ──
    style = doc.styles['Normal']
    style.font.name = 'Microsoft YaHei'
    style.font.size = Pt(11)
    style.paragraph_format.line_spacing = 1.5

    for line in md_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # 标题
        if line.startswith('# '):
            doc.add_heading(line[2:], level=1)
        elif line.startswith('## '):
            doc.add_heading(line[3:], level=2)
        elif line.startswith('### '):
            doc.add_heading(line[4:], level=3)
        elif line.startswith('#### '):
            doc.add_heading(line[5:], level=4)
        # 分割线
        elif line.startswith('---') or line.startswith('***'):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run('─' * 40)
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(180, 180, 180)
        # 列表项
        elif line.startswith('- ') or line.startswith('* '):
            doc.add_paragraph(line[2:], style='List Bullet')
        elif re.match(r'^\d+[.、] ', line):
            doc.add_paragraph(re.sub(r'^\d+[.、] ', '', line), style='List Number')
        # 表格行（包含 |）
        elif '|' in line and line.count('|') >= 3:
            _handle_table_row(doc, line, md_text)
        else:
            # 普通段落——处理粗体
            p = doc.add_paragraph()
            _add_formatted_text(p, line)

    return doc


def _handle_table_row(doc, line, full_text):
    """处理表格行（暂不实现复杂表格检测，简单跳过表头分隔行）"""
    # 跳过表格分隔行（|---|）
    if re.match(r'^[\s\|:\-]+$', line):
        return
    p = doc.add_paragraph()
    p.style = doc.styles['Normal']
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    _add_formatted_text(p, line)


def _add_formatted_text(paragraph, text):
    """添加带粗体/行内代码格式的文本"""
    # 处理 **bold**
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        elif part:
            paragraph.add_run(part)


def convert_file(input_path: str, output_path: str | None = None):
    """转换单个 md 文件为 docx"""
    if not output_path:
        output_path = os.path.splitext(input_path)[0] + '.docx'

    with open(input_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    doc = md_to_docx(md_text)
    doc.save(output_path)
    print(f"✅ 已转换: {input_path} → {output_path}")


def convert_directory(dir_path: str):
    """批量转换目录下所有 md 文件"""
    for root, _, files in os.walk(dir_path):
        for f in files:
            if f.endswith('.md'):
                md_path = os.path.join(root, f)
                docx_path = os.path.splitext(md_path)[0] + '.docx'
                convert_file(md_path, docx_path)


def main():
    parser = argparse.ArgumentParser(description='Markdown → DOCX 转换')
    parser.add_argument('input', help='输入文件或目录')
    parser.add_argument('output', nargs='?', help='输出文件（可选）')
    parser.add_argument('--dir', action='store_true', help='批量转换目录')

    args = parser.parse_args()

    if args.dir:
        convert_directory(args.input)
    else:
        convert_file(args.input, args.output)


if __name__ == '__main__':
    main()
