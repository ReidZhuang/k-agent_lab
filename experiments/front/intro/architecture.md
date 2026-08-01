# 系统架构设计

## 一、整体架构

```
┌──── 用户 PC (浏览器) ────┐
│  Tailscale IP 透传        │
└──────────┬────────────────┘
           │ HTTP (8320 或 5173)
           ▼
┌─────────────────────────────────────────────┐
│  Linux 服务器                                │
│                                              │
│  ┌──────────┐     ┌──────────────────────┐  │
│  │ 前端      │     │ 后端 FastAPI          │  │
│  │ Vue 3    │────▶│ :8320                 │  │
│  │ SPA      │     │ 托管 dist/ 静态文件    │  │
│  └──────────┘     └──────────┬───────────┘  │
│                              │               │
│               ┌──────────────┼───────────┐   │
│               ▼              ▼           ▼   │
│        ┌──────────┐  ┌──────────┐  ┌──────┐ │
│        │ SQLite   │  │ Tushare  │  │ Office│ │
│        │ DB       │  │ Pro API  │  │ 系统  │ │
│        └──────────┘  └──────────┘  └──────┘ │
└─────────────────────────────────────────────┘
```

## 二、前后端交互模式

系统支持两种运行模式：

### 2.1 开发模式（双端口）

```
前端 Vite Dev Server :5173  ←── 浏览器访问
    │
    └─ proxy /api/* ──→ 后端 FastAPI :8320
```

前端通过 Vite 的 `proxy` 配置将 `/api` 请求转发到后端，避免跨域问题。

### 2.2 生产模式（单端口）

```
后端 FastAPI :8320  ←── 浏览器访问（直接打开根路径）
    │
    ├─ /api/*        → API 路由处理
    └─ /*             → 托管 frontend/dist/（Vite 构建产物）
```

前端 `build` 后的静态文件由 FastAPI 的 `StaticFiles` 挂载，只需暴露一个端口。

## 三、后端架构

### 3.1 模块划分

```
backend/
├── main.py         # FastAPI 入口，路由定义，CORS，静态文件托管
├── database.py     # SQLite 数据库操作（CRUD + 建表）
├── auth.py         # 用户认证（密码哈希 + Token）
├── stock_api.py    # Tushare 数据接口封装
├── explorer.py     # 文件浏览、MD→DOCX 转换、打包下载
├── models.py       # Pydantic 数据模型
├── config.py       # 全局配置（路径、端口、密钥）
└── test_api.py     # 端到端测试
```

### 3.2 请求生命周期

```
浏览器请求
    │
    ▼
CORS 中间件 ──→ Token 验证（_get_user 依赖注入）
    │
    ├─ /api/auth/*       → 免验证，登录/用户信息
    ├─ /api/stock/*      → 股票搜索/股票池 CRUD
    ├─ /api/explorer/*   → 文件浏览/下载/收藏
    └─ /*                 → 静态文件
```

### 3.3 认证机制

- 密码使用 SHA256 哈希存储（生产环境建议改为 bcrypt）
- 登录成功后颁发 24 小时有效 Token（内存存储，服务重启后失效）
- 所有非登录接口通过 `Depends(_get_user)` 依赖注入验证 Token
- Token 在 HTTP Header `Authorization` 中传递

### 3.4 延迟初始化

为加速服务启动，以下组件使用延迟加载：

```python
# Tushare API 延迟初始化（避免模块导入时阻塞）
_PRO = None
def _get_pro():
    global _PRO
    if _PRO is None:
        _PRO = ts.pro_api()
    return _PRO

# 股票基础信息预热在后台线程中进行
threading.Thread(target=ensure_stock_basic_refreshed, daemon=True).start()
```

## 四、前端架构

### 4.1 组件树

```
App.vue
├── Login.vue              # 登录页
├── Main.vue               # 主界面布局
│   ├── FileTree.vue       # 文件树（复选框 + 收藏）
│   ├── StockPool.vue      # 股票池页签
│   ├── DocPreview.vue     # 文档预览页签
│   └── DownloadOverlay.vue # 全局下载进度浮层
```

### 4.2 数据流

- 全局状态：`downloadStore.js` 通过 Vue 3 `provide/inject` 提供下载进度状态
- 路由：Vue Router `createWebHashHistory`（hash 模式，无需服务端配合）
- API 调用：`api/index.js` 封装所有 `fetch` 请求，统一处理 Token 和 401 跳转

### 4.3 设计系统

| 设计变量 | 值 |
|---------|-----|
| 基础字号 | 18px（移动端 16px） |
| 原木主色 | `#C4A882` |
| 深木色 | `#8B7355` |
| 米白底色 | `#FFF8F0` |
| 深棕文字 | `#4A3728` |
| 涨/跌 | `#2E7D32` / `#C62828` |
| 控制高度 | 48px（按钮/输入框） |
| 边框圆角 | 8px |

## 五、数据流

### 5.1 股票池数据流

```
用户输入股票名称
    │
    ▼
后端 /api/stock/resolve
    │
    ├─ stock_basic 缓存（每日首次自动刷新）→ 名称→代码查询
    │
    ▼
返回标准化股票信息 → 用户确认加入
    │
    ▼
后端 /api/stock/pool (POST)
    │
    └─ 写入 stock_pool 表（数据库持久化）
    │
    ▼
后端 /api/stock/pool (GET)
    │
    ├─ 从 stock_pool 表读取自选列表
    ├─ 调 Tushare daily + daily_basic 获取昨日行情
    └─ 合并返回前端展示
```

### 5.2 文档下载数据流

```
用户选择文件 → 点"下载选中文档"
    │
    │ 单文件 → /api/explorer/download → md_to_docx.convert_file() → .docx 流式返回
    │ 多文件 → /api/explorer/download-batch → md_to_docx 批量 → .zip 返回
    │
    ▼
浮动进度条（模拟进度） → 完成后自动下载
```

### 5.3 文件浏览数据流

```
用户展开目录 → /api/explorer/list?path=xxx
    │
    ├─ 读取 user_001/ 目录下的文件和文件夹
    ├─ 标记收藏状态（user_favorite 表）
    └─ 返回树形结构数据

用户点击文件 → /api/explorer/content?path=xxx
    │
    ├─ 读取 .md 文件内容
    └─ 前端用 marked + highlight.js 渲染
```
