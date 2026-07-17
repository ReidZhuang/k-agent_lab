"""更新雪球token到配置文件"""
import json, os

config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
os.makedirs(config_dir, exist_ok=True)

token_file = os.path.join(config_dir, "xueqiu_token.json")

token = {
    "xq_a_token": "71dea811bf83f9356354ba120294af071646c44c",
    "u": "3755631005",
    "updated": "2026-07-17",
    "note": "手动从雪球网站cookie获取。浏览器登录 xueqiu.com → F12 → Application → Cookies → xq_a_token"
}

with open(token_file, "w", encoding="utf-8") as f:
    json.dump(token, f, ensure_ascii=False, indent=2)

print(f"Token 已保存到 {token_file}")
print("如需更新，编辑此文件或重新运行本脚本")
