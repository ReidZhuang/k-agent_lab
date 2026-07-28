#!/usr/bin/env python3
"""
Markdown → DOCX 转换工具（商务版）

生成专业商务风格的分析报告 Word 文档。

特性:
  - 封面页（标题、副标题、日期、免责声明）
  - 页眉页脚（公司名、页码）
  - 表格：专业配色、交替行底纹、表头深色
  - 标题层级：清晰的字号/颜色层次
  - 分段间距优化
  - 中文排版优化

用法:
  conda run -n stock_agent python md_to_docx.py input.md output.docx
  conda run -n stock_agent python md_to_docx.py --dir output/
"""
import os
import sys
import argparse
import re
from datetime import datetime
from docx import Document
from docx.shared import Pt, Cm, RGBColor, Inches, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

# ── 配色 ──
COLOR_PRIMARY = RGBColor(0x1F, 0x4E, 0x79)    # 深蓝（标题）
COLOR_SECONDARY = RGBColor(0x2E, 0x75, 0xB6)   # 中蓝（H2）
COLOR_ACCENT = RGBColor(0x47, 0x72, 0xA8)       # 蓝灰（H3）
COLOR_BODY = RGBColor(0x33, 0x33, 0x33)         # 深灰（正文）
COLOR_MUTED = RGBColor(0x66, 0x66, 0x66)         # 中灰（辅助文字）
COLOR_TABLE_HEADER = "1F4E79"                    # 表头深蓝
COLOR_TABLE_ALT = "EBF5FB"                       # 表格交替行浅蓝
COLOR_DIVIDER = "D0D0D0"                         # 分割线灰色


def md_to_docx(md_text: str, stock_name: str = "",
               trade_date: str = "") -> Document:
    """将 Markdown 报告文本转换为 Word 文档

    Args:
        md_text: 报告的 Markdown 内容
        stock_name: 股票名称（用于封面）
        trade_date: 交易日期（用于封面）

    Returns:
        python-docx Document 实例
    """
    doc = Document()

    # ── 页面设置 ──
    section = doc.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.8)

    # ── 页眉页脚 ──
    _add_header_footer(doc, stock_name)

    # ── 默认样式 ──
    _set_styles(doc)

    # ── 封面页 ──
    _add_cover_page(doc, stock_name, trade_date, md_text)

    # ── 正文 ──
    lines = md_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # 标题
        if line.startswith('# '):
            doc.add_heading(_strip_md(line[2:]), level=1)
        elif line.startswith('## '):
            doc.add_heading(_strip_md(line[3:]), level=2)
        elif line.startswith('### '):
            doc.add_heading(_strip_md(line[4:]), level=3)
        elif line.startswith('#### '):
            doc.add_heading(_strip_md(line[5:]), level=4)

        # 分割线
        elif re.match(r'^[-*]{3,}\s*$', line):
            _add_divider(doc)

        # 列表
        elif line.startswith('- ') or line.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            _add_rich_text(p, line[2:])

        elif re.match(r'^\d+[.、] ', line):
            text = re.sub(r'^\d+[.、] ', '', line)
            p = doc.add_paragraph(style='List Number')
            _add_rich_text(p, text)

        # 表格
        elif line.startswith('|') and '|' in line[1:]:
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append(lines[i].strip())
                i += 1
            _add_table(doc, rows)
            continue

        # 普通段落
        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            _add_rich_text(p, line)

        i += 1

    return doc


# ════════════════════════════════════════════════════════════════
# 封面
# ════════════════════════════════════════════════════════════════

def _add_cover_page(doc, stock_name: str, trade_date: str, md_text: str):
    """添加封面页"""
    if not stock_name:
        # 从正文第一行 # 标题 中提取
        m = re.search(r'^# (.+?)(?:（.*?）)?午间分析报告', md_text, re.M)
        if m:
            stock_name = _strip_md(m.group(1)).strip()
    if not trade_date:
        m = re.search(r'\*+\s*数据截止[：:]\s*(\S+)', md_text)
        if m:
            trade_date = m.group(1)

    # 空行推到上方
    for _ in range(6):
        doc.add_paragraph()

    # ── 标题 ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('午间分析报告')
    run.font.size = Pt(28)
    run.bold = True
    run.font.color.rgb = COLOR_PRIMARY
    run.font.name = 'Microsoft YaHei'

    # ── 股票名称 ──
    if stock_name:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(stock_name)
        run.font.size = Pt(18)
        run.font.color.rgb = COLOR_SECONDARY
        run.font.name = 'Microsoft YaHei'

    # ── 分隔 ──
    doc.add_paragraph()

    # ── 日期 ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f'报告日期：{trade_date or datetime.now().strftime("%Y-%m-%d")}')
    run.font.size = Pt(11)
    run.font.color.rgb = COLOR_MUTED
    run.font.name = 'Microsoft YaHei'

    # ── 数据说明 ──
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('数据截止时间：当日 11:30（午间收盘）')
    run.font.size = Pt(10)
    run.font.color.rgb = COLOR_MUTED
    run.font.name = 'Microsoft YaHei'

    # ── 免责声明 ──
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('— 本报告由 AI 自动生成，仅供参考，不构成投资建议 —')
    run.font.size = Pt(9)
    run.font.color.rgb = COLOR_MUTED
    run.italic = True
    run.font.name = 'Microsoft YaHei'

    # ── 分页符 ──
    doc.add_page_break()


# ════════════════════════════════════════════════════════════════
# 页眉页脚
# ════════════════════════════════════════════════════════════════

def _add_header_footer(doc, stock_name: str):
    """添加页眉和页脚"""
    # 页眉
    header = doc.sections[0].header
    header.is_linked_to_previous = False
    p = header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run(f'午间分析报告 {" | " + stock_name if stock_name else ""}')
    run.font.size = Pt(8)
    run.font.color.rgb = COLOR_MUTED
    run.font.name = 'Microsoft YaHei'

    # 页脚（页码）
    footer = doc.sections[0].footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('— ')
    run.font.size = Pt(8)
    run.font.color.rgb = COLOR_MUTED
    # 插入页码域
    fld_char_begin = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
    run._r.append(fld_char_begin)
    instr = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>')
    run._r.append(instr)
    fld_char_end = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')
    run._r.append(fld_char_end)
    run2 = p.add_run(' —')
    run2.font.size = Pt(8)
    run2.font.color.rgb = COLOR_MUTED


# ════════════════════════════════════════════════════════════════
# 样式
# ════════════════════════════════════════════════════════════════

def _set_styles(doc):
    """设置文档样式"""
    # ── Normal ──
    style = doc.styles['Normal']
    style.font.name = 'Microsoft YaHei'
    style.font.size = Pt(10.5)
    style.font.color.rgb = COLOR_BODY
    style.paragraph_format.line_spacing = 1.4
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.space_before = Pt(0)
    _set_font_east_asia(style, 'Microsoft YaHei')

    # ── Heading 1（报告章节标题） ──
    s = doc.styles['Heading 1']
    s.font.name = 'Microsoft YaHei'
    s.font.size = Pt(18)
    s.font.bold = True
    s.font.color.rgb = COLOR_PRIMARY
    s.paragraph_format.space_before = Pt(24)
    s.paragraph_format.space_after = Pt(12)
    s.paragraph_format.line_spacing = 1.2
    _set_font_east_asia(s, 'Microsoft YaHei')

    # ── Heading 2（子章节标题） ──
    s = doc.styles['Heading 2']
    s.font.name = 'Microsoft YaHei'
    s.font.size = Pt(14)
    s.font.bold = True
    s.font.color.rgb = COLOR_SECONDARY
    s.paragraph_format.space_before = Pt(18)
    s.paragraph_format.space_after = Pt(8)
    s.paragraph_format.line_spacing = 1.2
    _set_font_east_asia(s, 'Microsoft YaHei')

    # ── Heading 3 ──
    s = doc.styles['Heading 3']
    s.font.name = 'Microsoft YaHei'
    s.font.size = Pt(12)
    s.font.bold = True
    s.font.color.rgb = COLOR_ACCENT
    s.paragraph_format.space_before = Pt(12)
    s.paragraph_format.space_after = Pt(6)
    _set_font_east_asia(s, 'Microsoft YaHei')

    # ── List Bullet ──
    s = doc.styles['List Bullet']
    s.font.name = 'Microsoft YaHei'
    s.font.size = Pt(10.5)
    s.font.color.rgb = COLOR_BODY
    s.paragraph_format.space_after = Pt(2)
    _set_font_east_asia(s, 'Microsoft YaHei')

    # ── List Number ──
    s = doc.styles['List Number']
    s.font.name = 'Microsoft YaHei'
    s.font.size = Pt(10.5)
    s.font.color.rgb = COLOR_BODY
    s.paragraph_format.space_after = Pt(2)
    _set_font_east_asia(s, 'Microsoft YaHei')


def _set_font_east_asia(style, font_name: str):
    """设置中文字体"""
    style.element.rPr.rFonts.set(qn('w:eastAsia'), font_name)


# ════════════════════════════════════════════════════════════════
# 分割线
# ════════════════════════════════════════════════════════════════

def _add_divider(doc):
    """添加浅色分割线"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(8)
    pPr = p._p.get_or_add_pPr()
    pBdr = parse_xml(
        f'<w:pBdr {nsdecls("w")}>'
        f'  <w:bottom w:val="single" w:sz="4" w:space="1" w:color="{COLOR_DIVIDER}"/>'
        '</w:pBdr>'
    )
    pPr.append(pBdr)


# ════════════════════════════════════════════════════════════════
# 表格
# ════════════════════════════════════════════════════════════════

def _add_table(doc, rows: list[str]):
    """添加格式化表格"""
    data_rows = [r for r in rows if not re.match(r'^[\s|:—\-]+$', r)]
    if len(data_rows) < 1:
        return

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

    # 设置表格列宽等比
    for row_idx, cells in enumerate(parsed):
        for col_idx, cell_text in enumerate(cells):
            if col_idx >= num_cols:
                break
            cell = table.cell(row_idx, col_idx)
            cell.text = ''
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.2

            if row_idx == 0:
                # 表头：深蓝底 + 白字 + 加粗
                _set_cell_shading(cell, COLOR_TABLE_HEADER)
                run = p.add_run(cell_text.strip())
                run.bold = True
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                run.font.size = Pt(9.5)
                run.font.name = 'Microsoft YaHei'
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                # 交替行底纹
                if row_idx % 2 == 0:
                    _set_cell_shading(cell, COLOR_TABLE_ALT)
                _add_rich_text(p, cell_text.strip(), font_size=Pt(9.5))

    # 表格后间距
    doc.add_paragraph()


def _parse_table_row(row: str) -> list[str]:
    """解析 markdown 表格行"""
    row = row.strip()
    if not row.startswith('|'):
        return []
    row = row[1:]
    if row.endswith('|'):
        row = row[:-1]
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
    """设置单元格底纹"""
    shading = parse_xml(
        f'<w:shd {nsdecls("w")} w:fill="{color}" w:val="clear"/>'
    )
    cell._tc.get_or_add_tcPr().append(shading)


# ════════════════════════════════════════════════════════════════
# 富文本（粗体/普通文字）
# ════════════════════════════════════════════════════════════════

def _add_rich_text(paragraph, text: str, font_size: Pt | None = None):
    """添加带粗体格式的文本"""
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
            run.font.name = 'Microsoft YaHei'
            if font_size:
                run.font.size = font_size
            run.font.color.rgb = COLOR_PRIMARY
        else:
            run = paragraph.add_run(part)
            run.font.name = 'Microsoft YaHei'
            if font_size:
                run.font.size = font_size


def _strip_md(text: str) -> str:
    """移除 markdown 标记"""
    return text.replace('**', '').replace('*', '').strip()


# ════════════════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════════════════

def convert_file(input_path: str, output_path: str | None = None):
    """转换单个 md 文件为 docx"""
    if not output_path:
        output_path = os.path.splitext(input_path)[0] + '.docx'

    with open(input_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # 从文件路径和内容提取股票名称
    stock_dir = os.path.basename(os.path.dirname(input_path))
    doc = md_to_docx(md_text, stock_name=stock_dir)
    doc.save(output_path)
    print(f"✅ {os.path.basename(os.path.dirname(input_path))}")


def convert_directory(dir_path: str):
    """批量转换"""
    files = sorted(os.listdir(dir_path))
    for name in files:
        sub = os.path.join(dir_path, name)
        md_file = os.path.join(sub, f"{name}_midday.md") if os.path.isdir(sub) else None
        if md_file and os.path.exists(md_file) and name != 'test':
            convert_file(md_file)


def main():
    parser = argparse.ArgumentParser(description='Markdown → DOCX 转换（商务版）')
    parser.add_argument('input', help='输入文件')
    parser.add_argument('output', nargs='?', help='输出文件（可选）')
    args = parser.parse_args()

    output = args.output or args.input.replace('.md', '.docx')
    convert_file(args.input, output)


if __name__ == '__main__':
    main()
