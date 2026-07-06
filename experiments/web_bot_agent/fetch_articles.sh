#!/bin/bash
# 搜索 → 抓取5篇文章正文 → 输出md文档
# 用法: bash fetch_articles.sh

cd "$(dirname "$0")"
source config/config.sh

proxy_on
RESULTS_FILE="results/fetch_test.md"

echo "🔍 搜索中..."
SEARCH_OUTPUT=$(web-forager search "site:stcn.com 宁德时代 市场占有率" --max-results 5 --output-format json 2>/dev/null)

# 提取 URL 和 Title
URLS=$(echo "$SEARCH_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data:
    print(item['url'])
")
TITLES=$(echo "$SEARCH_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data:
    print(item['title'].replace('|', '-').replace('*', ''))
")

mapfile -t URL_ARRAY <<< "$URLS"
mapfile -t TITLE_ARRAY <<< "$TITLES"
TOTAL=${#URL_ARRAY[@]}
echo "📝 共 $TOTAL 篇文章，开始抓取..."

# 生成 Markdown 头部
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
cat > "$RESULTS_FILE" << HEADER
# 正文抓取测试

> **搜索词:** \`site:stcn.com 宁德时代 市场占有率\`
> **抓取工具:** web-forager fetch (jina_fetch → r.jina.ai)
> **时间:** $TIMESTAMP

HEADER

for i in "${!URL_ARRAY[@]}"; do
    url="${URL_ARRAY[$i]}"
    title="${TITLE_ARRAY[$i]}"
    idx=$((i + 1))

    echo "  [$idx/$TOTAL] $title"

    # 先写元信息
    {
        echo ""
        echo "---"
        echo ""
        echo "## $idx. $title"
        echo ""
        echo "**URL:** $url"
        echo ""
    } >> "$RESULTS_FILE"

    # 抓取正文
    CONTENT=$(timeout 30 env http_proxy="$http_proxy" https_proxy="$https_proxy" web-forager fetch "$url" 2>/dev/null)

    if [ -z "$CONTENT" ]; then
        echo "> ⚠️ 抓取失败或返回空" >> "$RESULTS_FILE"
        echo "" >> "$RESULTS_FILE"
        echo "  ⚠️ 失败"
    else
        echo '```markdown' >> "$RESULTS_FILE"
        echo "$CONTENT" >> "$RESULTS_FILE"
        echo '```' >> "$RESULTS_FILE"
        echo "" >> "$RESULTS_FILE"
        echo "  ✅ 完成 ($(echo "$CONTENT" | wc -c) bytes)"
    fi

    sleep 1
done

echo ""
echo "✅ 全部完成！结果已保存到: $RESULTS_FILE"
echo "   文件大小: $(wc -c < "$RESULTS_FILE" | tr -d ' ') bytes"
