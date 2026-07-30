#!/usr/bin/env python3
"""端到端 API 测试"""
import json, time, urllib.request, urllib.parse, subprocess, sys, os

# 切换到 backend 目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

proc = subprocess.Popen(
    ["conda", "run", "-n", "stock_agent", "python", "-c",
     "import uvicorn; from main import app, init_default_users; init_default_users(); uvicorn.run(app, host='0.0.0.0', port=8320, log_level='error')"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

def api(method, path, data=None, token=None):
    req = urllib.request.Request(f"http://localhost:8320{path}", method=method)
    if data:
        req.data = json.dumps(data).encode()
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

# Wait for startup
for i in range(30):
    try:
        urllib.request.urlopen("http://localhost:8320/docs", timeout=2)
        break
    except:
        time.sleep(1)
else:
    print("❌ 服务器启动超时")
    proc.terminate()
    sys.exit(1)

print("✅ 服务器就绪")

# 1. Login
r = api("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
assert r and "token" in r, f"Login failed: {r}"
TOKEN = r["token"]
print(f"✅ 登录成功")

# 2. Search
q = urllib.parse.quote("平安")
r = api("GET", f"/api/stock/search?q={q}", token=TOKEN)
print(f"✅ 搜索'平安': {len(r.get('results',[]))} 条结果")
if r and r.get("results"):
    print(f"   首条: {r['results'][0]['name']} ({r['results'][0]['ts_code']})")

# 3. Add to pool
r = api("POST", "/api/stock/pool", {"stock_names": ["宁德时代", "比亚迪", "平安银行"]}, token=TOKEN)
print(f"✅ 加入股票池: {r.get('count',0)} 只")

# 4. Get pool
r = api("GET", "/api/stock/pool", token=TOKEN)
print(f"✅ 股票池: {r.get('total',0)} 只")
for s in (r or {}).get("stocks", [])[:3]:
    daily = s.get("daily")
    chg = f"{daily['pct_chg']:.2f}%" if daily and daily.get("pct_chg") else "N/A"
    print(f"   {s['stock_name']} ({s['ts_code']}) {chg}")

# 5. Favorites
r = api("POST", "/api/explorer/favorites", {"file_path": "test.md", "file_name": "测试"}, token=TOKEN)
print(f"✅ 收藏: 成功")

r = api("GET", "/api/explorer/favorites", token=TOKEN)
print(f"✅ 收藏列表: {len(r.get('favorites',[]))} 项")

# 6. File explorer
r = api("GET", "/api/explorer/list", token=TOKEN)
print(f"✅ 文件浏览: {len(r.get('items',[]))} 项")

proc.terminate()
proc.wait()
print("\n🎉 全部测试通过!")
