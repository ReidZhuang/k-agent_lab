"""
测试要点定位：用要点 "开发者规模持续壮大，年轻开发者占比高，一线城市集中" 定位原文
模拟 pipeline 中的分块 → locate_point_text 流程
"""
import os, time, asyncio
from core import split_paragraphs, build_point_locate_prompt, locate_point_text, parse_point_locate_output, _call_llm

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "point_text_test")
os.makedirs(RESULTS_DIR, exist_ok=True)

async def main():
    # 读长文本
    with open('t_article_8000.txt', 'r', encoding='utf-8') as f:
        body = f.read()
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

    # 模拟 pipeline 分块
    chunks = split_paragraphs(paragraphs)
    print(f'原文: {len(paragraphs)}段, {sum(len(p) for p in paragraphs)}字')
    print(f'分块: {len(chunks)}块')
    for ci, chunk in enumerate(chunks):
        print(f'  块{ci+1}: {len(chunk)}段')
    print()

    # 测试要点
    key_point = "开发者规模持续壮大，年轻开发者占比高，一线城市集中"
    print(f'要点: {key_point}')
    print()

    # 保存每个块的 locate prompt + LLM 输出
    for ci, chunk in enumerate(chunks):
        prompt = build_point_locate_prompt(chunk, key_point)
        prompt_file = os.path.join(RESULTS_DIR, f"01_chunk{ci+1}_prompt.md")
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(f'# 块{ci+1} 要点定位 Prompt\n\n')
            f.write(f'**要点**: {key_point}\n\n')
            f.write(f'**Prompt 字数**: {len(prompt)}\n')
            f.write(f'**块段落数**: {len(chunk)}段\n\n')
            f.write('```\n')
            f.write(prompt)
            f.write('\n```\n')
        print(f'块{ci+1} Prompt: {len(prompt)}字 → 已保存')

        # 调 LLM
        raw = await _call_llm(prompt)
        output_file = os.path.join(RESULTS_DIR, f"02_chunk{ci+1}_output.md")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f'# 块{ci+1} LLM 输出\n\n')
            f.write('```\n')
            f.write(raw)
            f.write('\n```\n')

        paras = parse_point_locate_output(raw)
        print(f'  LLM 输出: {raw}')
        print(f'  解析段落: {paras}')
        print()

    # 用 locate_point_text 整合调用
    print('=== locate_point_text 整合调用 ===')
    result = await locate_point_text(chunks, key_point)
    print(f'找到: {result["found"]}')
    print(f'块索引: {result["chunk_index"]}')
    print(f'段落号: P{result["paragraphs"]}')
    print(f'原文:\n{result["text"][:200]}...')

    # 保存最终结果
    final_file = os.path.join(RESULTS_DIR, "03_final_result.md")
    with open(final_file, 'w', encoding='utf-8') as f:
        f.write('# 要点定位最终结果\n\n')
        f.write(f'## 输入\n\n')
        f.write(f'**要点**: {key_point}\n\n')
        f.write(f'**原文**: t_article_8000.txt（{len(paragraphs)}段, {len(chunks)}块）\n\n')
        f.write(f'## locate_point_text 输出\n\n')
        f.write(f'| 项目 | 值 |\n')
        f.write(f'|---|---|\n')
        f.write(f'| 找到 | {"✅ 是" if result["found"] else "❌ 否"} |\n')
        f.write(f'| 所在块 | 块{result["chunk_index"]+1} |\n')
        f.write(f'| 段落编号 | {result["paragraphs"]} |\n')
        f.write(f'| 原文长度 | {len(result["text"])}字 |\n\n')
        f.write(f'## 原文内容\n\n')
        f.write(result["text"])
        f.write('\n\n')
        f.write(f'## 验证\n\n')
        f.write(f'> 原文中是否包含要点关键词？\n\n')
        contains_keywords = all(kw in result["text"] for kw in ["开发者", "年轻", "一线城市"])
        f.write(f'{"✅ 包含" if contains_keywords else "❌ 不包含"} "开发者"、"年轻"、"一线城市" 等关键词\n')

    print(f'\n✅ 结果已保存到: {final_file}')

if __name__ == '__main__':
    asyncio.run(main())
