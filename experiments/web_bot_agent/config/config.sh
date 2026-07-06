#!/bin/bash
# ==============================================================
# web_bot_agent 项目配置
# source 此文件后可使用 proxy_on/off 及 ollama 快捷命令
# 用法: source config/config.sh
# ==============================================================

# ---- 代理 (WSL2 → Windows Clash) ----
proxy_on() {
    export http_proxy="http://172.20.32.1:7890"
    export https_proxy="http://172.20.32.1:7890"
    echo "✅ 代理已开启 (172.20.32.1:7890)"
}
proxy_off() {
    unset http_proxy https_proxy
    echo "❌ 代理已关闭"
}

# ---- Ollama (本地 LLM) ----
export PATH="$HOME/ollama/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/ollama/lib"

# 默认模型（3B 速度快，7B 质量更高）
OLLAMA_MODEL_DEFAULT="qwen2.5:7b"
OLLAMA_MODEL_LARGE="qwen2.5:7b"

# ---- Ollama 快捷命令 ----
ollama_run() {
    local prompt="$1"
    local model="${2:-$OLLAMA_MODEL_DEFAULT}"
    ollama run "$model" "$prompt" --nowordwrap
}

# ---- Web Forager (DuckDuckGo 搜索) ----
alias web-search='proxy_on && web-forager search'
alias web-fetch='proxy_on && web-forager fetch'

# ---- 正文提取 (trafilatura / readability) ----
ARTICLE_EXTRACTOR=${ARTICLE_EXTRACTOR:-trafilatura}  # 优先使用，可改为 readability

extract_article() {
    local url="$1"
    local method="${2:-$ARTICLE_EXTRACTOR}"
    proxy_on  # 确保代理开启
    python3 -c "
import sys, httpx, re
proxy = 'http://172.20.32.1:7890'
url = '''${url}'''
with httpx.Client(proxy=proxy, timeout=15, follow_redirects=True) as client:
    try:
        r = client.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        html = r.text
    except Exception as e:
        print(f'[HTTP error] {e}', file=sys.stderr)
        sys.exit(1)

method = '${method}'
if method == 'trafilatura':
    import trafilatura
    text = trafilatura.extract(html, output_format='markdown', include_images=False)
    if text:
        print(text)
    else:
        # fallback: trafilatura 失败时用 readability
        sys.stderr.write('trafilatura 提取为空，尝试 readability 备选...\n')
        method = 'readability'

if method == 'readability':
    from readability import Document
    import html2text
    doc = Document(html)
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_links = False
    h.ignore_images = True
    text = h.handle(doc.summary())
    if text.strip():
        print(text.strip())
    else:
        print('[提取失败]', file=sys.stderr)
"
}

# 快捷命令（交互式 alias，非交互式请直接用 extract_article）
alias extract='proxy_on && extract_article'

echo "⚙️  web_bot_agent 配置已加载"
echo "   代理:   proxy_on / proxy_off"
echo "   模型:   ollama_run \"提示词\" [模型名]"
echo "   搜索:   web-search \"关键词\""
echo "   提取:   extract_article \"URL\"              # 默认 trafilatura"
echo "   提取:   ARTICLE_EXTRACTOR=readability extract_article \"URL\""
