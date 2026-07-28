#!/usr/bin/env python3
"""
Markdown → DOCX 转换工具（增强版）

支持:
  - 标题 (H1-H4)
  - 表格（标准 Markdown 表格 → Word 表格）
  - 粗体/行内代码
  - 列表（有序/无序）
  - 分割线
  - 中文排版优化

依赖: python-docx（已在 stock_agent 环境）

用法:
  conda run -n stock_agent python md_to_docx.py input.md output.docx
  conda run -n stock_agent python md_to_docx.py --dir output/  # 批量转换
"""
import os
import sys
import argparse
import re
from docx import Document
from docx.shared import Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml


def md_to_docx(md_text: str) -> Document:
    """将 Markdown 文本转换为 python-docx Document 对象"""
    doc = Document()

    # ── 页面设置 ──
    section = doc.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # ── 设置默认样式 ──
    _set_default_style(doc)

    # ── 解析并构建 ──
    lines = md_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        # 空行
        if not line.strip():
            i += 1
            continue

        # 标题
        if line.startswith('# '):
            doc.add_heading(_strip_bold(line[2:]), level=1)
        elif line.startswith('## '):
            doc.add_heading(_strip_bold(line[3:]), level=2)
        elif line.startswith('### '):
            doc.add_heading(_strip_bold(line[4:]), level=3)
        elif line.startswith('#### '):
            doc.add_heading(_strip_bold(line[5:]), level=4)

        # 水平分割线
        elif re.match(r'^[-*]{3,}\s*$', line):
            _add_horizontal_rule(doc)

        # 无序列表
        elif line.startswith('- ') or line.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            _add_formatted_text(p, line[2:])

        # 有序列表
        elif re.match(r'^\d+[.、] ', line):
            text = re.sub(r'^\d+[.、] ', '', line)
            p = doc.add_paragraph(style='List Number')
            _add_formatted_text(p, text)

        # 表格：检测以 | 开头的行
        elif line.startswith('|') and '|' in line[1:]:
            table_rows = []
            # 收集连续的表格行
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_rows.append(lines[i].strip())
                i += 1
            # 解析表格
            _add_table(doc, table_rows)
            continue

        # 普通段落
        else:
            p = doc.add_paragraph()
            _add_formatted_text(p, line)

        i += 1

    return doc


# ════════════════════════════════════════════════════════════════
# 样式设置
# ════════════════════════════════════════════════════════════════

def _set_default_style(doc):
    """设置文档默认样式和字体"""
    style = doc.styles['Normal']
    style.font.name = 'Microsoft YaHei'
    style.font.size = Pt(10.5)
    style.paragraph_format.line_spacing = 1.3
    style.paragraph_format.space_after = Pt(4)
    # 设置中文字体（西文字体用 SameAsFont）
    style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')

    # 标题样式
    for level in range(1, 5):
        heading_style = doc.styles[f'Heading {level}']
        heading_style.font.name = 'Microsoft YaHei'
        heading_style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')

    # 设置表格样式
    table_style = doc.styles['Table Grid']
    table_style.font.name = 'Microsoft YaHei'
    table_style.font.size = Pt(9)
    table_style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')


def _add_horizontal_rule(doc):
    """添加水平分割线（底部细边框的段落）"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    # 使用段落底部边框模拟分割线
    pPr = p._p.get_or_add_pPr()
    pBdr = parse_xml(
        f'<w:pBdr {nsdecls("w")}>'
        '  <w:bottom w:val="single" w:sz="6" w:space="1" w:color="999999"/>'
        '</w:pBdr>'
    )
    pPr.append(pBdr)


# ════════════════════════════════════════════════════════════════
# 表格处理
# ════════════════════════════════════════════════════════════════

def _add_table(doc, rows: list[str]):
    """将 Markdown 表格行转换为 Word 表格"""
    # 过滤表头分隔行（| --- | --- |）
    data_rows = [r for r in rows if not re.match(r'^[\s|:—\-]+$', r)]
    if len(data_rows) < 1:
        return

    # 解析所有行
    parsed = [_parse_table_row(r) for r in data_rows]
    if not parsed:
        return

    num_cols = max(len(row) for row in parsed)
    if num_cols < 2:
        return

    table = doc.add_table(rows=len(parsed), cols=num_cols)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    # 填充表格
    for row_idx, cells in enumerate(parsed):
        for col_idx, cell_text in enumerate(cells):
            if col_idx >= num_cols:
                break
            cell = table.cell(row_idx, col_idx)
            cell.text = ''
            p = cell.paragraphs[0]
            _add_formatted_text(p, cell_text.strip())

            # 表头加粗 + 灰色背景
            if row_idx == 0:
                _set_cell_shading(cell, "F2F2F2")
                for run in p.runs:
                    run.bold = True
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 表格后加空行
    doc.add_paragraph()


def _parse_table_row(row: str) -> list[str]:
    """解析一行 markdown 表格，返回单元格内容列表"""
    row = row.strip()
    if not row.startswith('|'):
        return []
    row = row[1:]  # 去掉开头的 |
    if row.endswith('|'):
        row = row[:-1]  # 去掉结尾的 |
    cells = []
    current = ''
    for ch in row:
        if ch == '|':
            cells.append(current.strip())
            current = ''
        else:
            current += ch
    cells.append(current.strip())
    return cells


def _set_cell_shading(cell, color: str):
    """设置单元格底纹颜色"""
    shading = parse_xml(
        f'<w:shd {nsdecls("w")} w:fill="{color}" w:val="clear"/>'
    )
    cell._tc.get_or_add_tcPr().append(shading)


# ════════════════════════════════════════════════════════════════
# 文本格式化
# ════════════════════════════════════════════════════════════════

def _add_formatted_text(paragraph, text):
    """添加带粗体/颜色的格式化文本"""
    # 匹配 **bold** 和分隔符
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            # 粗体
            run = paragraph.add_run(part[2:-2])
            run.bold = True
            run.font.name = 'Microsoft YaHei'
        elif part == '—':
            run = paragraph.add_run(part)
        else:
            run = paragraph.add_run(part)
            run.font.name = 'Microsoft YaHei'


def _strip_bold(text: str) -> str:
    """从标题文本中移除粗体标记"""
    return text.replace('**', '')


# ════════════════════════════════════════════════════════════════
# 文件操作
# ════════════════════════════════════════════════════════════════

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
    parser = argparse.ArgumentParser(description='Markdown → DOCX 转换（增强版）')
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
