"""快速检查新浪研报列表页结构"""
import httpx, re

url = 'https://stock.finance.sina.com.cn/stock/go.php/vReport_List/kind/search/index.phtml?symbol=300750&t1=all'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
resp.encoding = 'gb2312'
html = resp.text

print(f'状态码: {resp.status_code}')
print(f'页面长度: {len(html)} 字符')
print()

# 表格行
rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
print(f'表格行数: {len(rows)}')
for i, row in enumerate(rows[:25]):
    text = re.sub(r'<[^>]+>', ' ', row).strip()
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 3:
        print(f'  Row[{i}]: {text[:150]}')

# 链接
print(f'\n--- 新闻/报告链接 ---')
# 用 simpler regex
atags = re.findall(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
count=0
for href, text in atags:
    text = re.sub(r'<[^>]+>', '', text).strip()
    if len(text) > 5 and ('sina' in href or 'sinajs' in href):
        count+=1
        print(f'  [{count}] {text[:70]} -> {href[:90]}')
