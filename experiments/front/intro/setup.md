# 环境搭建与部署

## 前置条件

- **Python** ≥ 3.10（推荐 conda 环境 `stock_agent`）
- **Node.js** ≥ 18（仅前端开发需要，生产部署只需一次 `build`）
- **Tushare Pro Token**（配置在 `~/tk.csv` 或环境变量 `TUSHARE_TOKEN`）
- **Tailscale**（可选，用于远程连接）

## 一、开发环境搭建

### 1.1 克隆代码

```bash
# 项目在以下路径
cd /home/stockagent/project_space/research/experiments/front
```

### 1.2 安装后端依赖

```bash
conda activate stock_agent
pip install fastapi uvicorn tushare python-docx pydantic
```

已安装的依赖：
- `fastapi` + `uvicorn` — API 服务框架
- `tushare` — A 股数据接口
- `python-docx` — Word 文档生成
- `pydantic` — 数据模型验证

### 1.3 安装前端依赖

```bash
cd frontend
npm install
```

### 1.4 配置 Tushare Token

Tushare Token 配置方式（任选其一）：

```bash
# 方式一：环境变量
export TUSHARE_TOKEN=your_token_here

# 方式二：配置文件（tushare 库自动读取）
echo "token,your_token_here" > ~/tk.csv
```

## 二、启动开发环境

### 2.1 一键启动（生产模式）

```bash
cd /home/stockagent/project_space/research/experiments/front
bash start.sh
```

启动后：
- 前端自动 `build` 到 `frontend/dist/`
- 后端启动在 `http://0.0.0.0:8320`
- 直接访问 `http://localhost:8320` 即可

### 2.2 分步启动（开发模式）

**终端 1 — 后端 API：**

```bash
cd /home/stockagent/project_space/research/experiments/front/backend
conda run -n stock_agent python main.py
# → http://localhost:8320
```

**终端 2 — 前端 Vite HMR：**

```bash
cd /home/stockagent/project_space/research/experiments/front/frontend
npx vite --host 0.0.0.0
# → http://localhost:5173（自动代理 /api 到 :8320）
```

### 2.3 脚本启动（开发模式）

```bash
bash start_dev.sh
```

同时启动后端和前端，并在退出时自动清理子进程。

## 三、生产部署

### 3.1 单端口部署（推荐）

```bash
cd /home/stockagent/project_space/research/experiments/front
bash start.sh
```

后端监听 `0.0.0.0:8320`，托管前端静态文件 + API 路由。

### 3.2 Tailscale 透传访问

在服务器上安装 Tailscale 后：

```bash
# 启动服务
bash start.sh

# 获取 Tailscale IP
tailscale ip -4
# → 100.x.x.x

# 在本地 PC 浏览器访问
http://100.x.x.x:8320
```

Tailscale 会自动处理 NAT 穿透、加密传输，无需额外配置 HTTPS。

### 3.3 后台持久运行

```bash
cd /home/stockagent/project_space/research/experiments/front/backend
nohup conda run -n stock_agent python main.py > /tmp/frontend.log 2>&1 &
```

或使用 `tmux` / `screen` 保持会话。

## 四、注意事项

### 4.1 数据库

- 数据库文件：`/home/stockagent/project_space/database/report_market.db`
- 系统启动时自动创建所需表（`user`、`stock_pool`、`user_favorite`、`stg_stock_basic`）
- 首次启动会自动创建默认用户（如已配置 `init_default_users()`）

### 4.2 端口占用

如果端口被占用：

```bash
# 查看端口占用
fuser 8320/tcp
ss -tlnp | grep 8320

# 强制释放
fuser -k 8320/tcp
```

### 4.3 Tushare API 限流

- `stock_basic`：每分钟最多 50 次，一次拉取即可缓存到本地
- `daily` + `daily_basic`：基础积分每分钟 500 次，一次全量查询即可覆盖所有股票
- 系统会在每日首次查询时自动刷新 `stg_stock_basic` 缓存

### 4.4 用户管理

添加用户（需在服务器上执行）：

```bash
cd /home/stockagent/project_space/research/experiments/front/backend
conda run -n stock_agent python -c "
from database import db
from auth import hash_password
db.create_user('用户名', hash_password('密码'))
"
```

删除用户：

```bash
conda run -n stock_agent python -c "
from database import db
db.execute('DELETE FROM user WHERE username=?', ('用户名',))
"
```
