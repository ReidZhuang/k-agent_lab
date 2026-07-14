"""
批量转换 ds_prompts/ 下的 field.md、api.md、table.md 到统一格式。
"""
import re, os, shutil
from pathlib import Path

DS_DIR = Path(__file__).parent.parent / "ds_prompts"


def convert_field_md(path: Path) -> bool:
    """转换 field.md 到统一格式（含数据示例列）"""
    text = path.read_text(encoding="utf-8")

    # 已经转换过了
    if "数据示例" in text:
        return False

    lines = text.split("\n")
    new_lines = []
    in_table = False
    header_done = False

    for line in lines:
        # 保留标题行
        if line.startswith("#"):
            new_lines.append(line)
            continue

        # 检测表格开始
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]

            if not header_done:
                # 判断列数
                if len(cells) == 3:
                    header_done = True
                    # 新格式 header
                    new_lines.append("| 字段名 | 类型 | 说明 | 数据示例 |")
                    new_lines.append("|--------|:----:|:-----|:--------:|")
                elif len(cells) == 2:
                    header_done = True
                    new_lines.append("| 字段名 | 类型 | 说明 | 数据示例 |")
                    new_lines.append("|--------|:----:|:-----|:--------:|")
                elif len(cells) == 4 and "索引" not in text:
                    header_done = True
                    new_lines.append("| 字段名 | 类型 | 说明 | 数据示例 |")
                    new_lines.append("|--------|:----:|:-----|:--------:|")
                elif len(cells) >= 4:
                    header_done = True
                    # 保留原格式，加数据示例列
                    old_h = cells + ["数据示例"]
                    new_lines.append("| " + " | ".join(old_h) + " |")
                    new_lines.append("|" + "|".join([":---:"] * len(old_h)) + "|")
                continue

            # 分隔行
            if all(c.startswith(":") for c in cells) or all(c == "---" or c == ":---" for c in cells):
                continue

            # 数据行
            if len(cells) == 3:
                new_lines.append(f"| {cells[0]} | {cells[1]} | {cells[2]} | — |")
            elif len(cells) == 2:
                new_lines.append(f"| {cells[0]} | — | {cells[1]} | — |")
            elif len(cells) >= 4 and "索引" not in text and "说明" not in cells:
                new_lines.append(f"| {cells[0]} | {cells[1]} | {cells[2]} | — |")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    path.write_text("\n".join(new_lines), encoding="utf-8")
    return True


def convert_api_md(path: Path) -> bool:
    """清理 api.md：保留函数签名和参数表，删除示例代码和注意"""
    text = path.read_text(encoding="utf-8")
    original = text

    lines = text.split("\n")
    new_lines = []
    skip_block = False
    in_code_block = False

    for i, line in enumerate(lines):
        # 跳过代码块
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # 去掉标题行
        if re.match(r'^#\s+', line):
            clean = re.sub(r'^#\s+', '', line).strip()
            if clean.startswith("##"):
                new_lines.append(line)
            continue

        # 跳过"注意"章节
        if line.strip().startswith("## 注意"):
            skip_block = True
            continue
        if skip_block:
            if line.strip().startswith("## "):
                skip_block = False
                new_lines.append(line)
            continue

        # 跳过"标准调用模板"章节
        if "调用模板" in line or "示例" in line:
            continue

        new_lines.append(line)

    # 去掉多余空行
    result = "\n".join(new_lines)
    result = re.sub(r'\n{3,}', '\n\n', result).strip()

    if result != original:
        path.write_text(result, encoding="utf-8")
        return True
    return False


def convert_table_md(path: Path) -> bool:
    """简化 table.md：如果内容已包含在 field.md 中，就保留最小信息"""
    text = path.read_text(encoding="utf-8")
    if "注：" in text and "字段信息见" in text:
        return False  # already converted

    # 只保留第一行有意义的信息
    lines = text.strip().split("\n")
    first_line = ""
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            first_line = line
            break

    if first_line:
        new = f"# {path.parent.name} 表结构\n\n注：字段信息见 field.md。\n{first_line}"
    else:
        new = f"# {path.parent.name} 表结构\n\n注：字段信息见 field.md。"

    if text.strip() != new.strip():
        path.write_text(new, encoding="utf-8")
        return True
    return False


def main():
    changed = {"field": 0, "api": 0, "table": 0}

    for ds_dir in sorted(DS_DIR.iterdir()):
        if not ds_dir.is_dir():
            continue

        field_path = ds_dir / "field.md"
        api_path = ds_dir / "api.md"
        table_path = ds_dir / "table.md"

        if field_path.exists():
            if convert_field_md(field_path):
                changed["field"] += 1
                print(f"  📝 field.md: {ds_dir.name}")

        if api_path.exists():
            if convert_api_md(api_path):
                changed["api"] += 1
                print(f"  📝 api.md:   {ds_dir.name}")

        if table_path.exists():
            if convert_table_md(table_path):
                changed["table"] += 1
                print(f"  📝 table.md: {ds_dir.name}")

    print(f"\n✅ 完成:")
    for k, v in changed.items():
        print(f"   {k}: {v} 个文件")


if __name__ == "__main__":
    main()
