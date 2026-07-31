# 开发指南

## 一、目录结构

```
front/
├── backend/                     # FastAPI 后端
│   ├── main.py                  # API 路由 + 启动入口
│   ├── database.py              # SQLite 数据库操作
│   ├── stock_api.py             # Tushare 数据接口
│   ├── explorer.py              # 文件浏览 + MD→DOCX 转换
│   ├── auth.py                  # 登录认证 + Token
│   ├── models.py                # Pydantic 数据模型
│   ├── config.py                # 全局配置
│   └── test_api.py              # 端到端测试
├── frontend/                    # Vue 3 前端
│   ├── src/
│   │   ├── views/
│   │   │   ├── Login.vue        # 登录页面
│   │   │   └── Main.vue         # 主界面布局
│   │   ├── components/
│   │   │   ├── FileTree.vue     # 文件树组件
│   │   │   ├── StockPool.vue    # 股票池组件
│   │   │   ├── DocPreview.vue   # 文档预览组件
│   │   │   └── DownloadOverlay.vue # 下载进度浮层
│   │   ├── api/
│   │   │   ├── index.js         # API 调用封装
│   │   │   └── downloadStore.js # 下载状态管理
│   │   ├── assets/style.css     # 全局样式
│   │   └── main.js              # 入口（路由 + Element Plus）
│   ├── index.html               # HTML 模板
│   ├── vite.config.js           # Vite 配置
│   └── package.json
├── intro/                       # 文档（本目录）
│   ├── README.md                # 概览
│   ├── architecture.md          # 架构设计
│   ├── setup.md                 # 环境搭建
│   ├── development.md           # 开发指南
│   ├── api.md                   # API 文档
│   ├── usage.md                 # 用户手册
│   └── database.md              # 数据库设计
├── start.sh                     # 生产启动
└── start_dev.sh                 # 开发启动
```

## 二、开发规范

### 2.1 Python 后端

- 遵循 PEP 8，使用 4 空格缩进
- 所有 API 路由必须添加完整的类型注解
- 新增路由需要添加 `Depends(_get_user)` 认证依赖
- 敏感操作（如删除股票池）完成后返回 `{"status": "ok"}` 统一格式
- 所有 Tushare 调用需有 try/except 保护，避免前端收到 500

### 2.2 Vue 3 前端

- 使用 Composition API (`<script setup>`) 写法
- 组件命名：大驼峰（`StockPool.vue`、`DocPreview.vue`）
- API 调用统一通过 `api/index.js` 封装
- 全局下载状态通过 `downloadStore.js` 的 `provide/inject` 管理
- 所有异步操作需要 try/catch + 用户提示（`ElMessage`）

### 2.3 Git 提交规范

```
feat:       新功能
fix:        修复
docs:       文档
style:      样式
refactor:   重构
perf:       性能优化
chore:      杂项
```

## 三、后端开发

### 3.1 新增 API 路由

```python
# 1. 在 models.py 中定义请求/响应模型
class MyRequest(BaseModel):
    field1: str
    field2: int

# 2. 在 main.py 中添加路由
@app.post("/api/my-endpoint")
def my_endpoint(req: MyRequest, user: dict = Depends(_get_user)):
    # 业务逻辑
    return {"status": "ok", "data": ...}
```

### 3.2 新增数据源

如果要接入新的 Tushare 接口：

```python
# 在 stock_api.py 中添加新函数
def fetch_new_data(params) -> dict:
    pro = _get_pro()
    try:
        df = pro.new_api(**params)
        # 处理 DataFrame
        return result
    except Exception as e:
        print(f"  ⚠️  new_api 失败: {e}")
        return {}
```

### 3.3 命令行直接测试

```bash
cd /home/stockagent/project_space/research/experiments/front/backend
conda run -n stock_agent python -c "
from stock_api import search_stock
print(search_stock('宁德'))
"
```

## 四、前端开发

### 4.1 新增页面

1. 在 `src/views/` 下新建 `.vue` 文件
2. 在 `src/main.js` 的路由表中添加路由
3. 如果是主界面的新标签页，在 `Main.vue` 的 `el-tabs` 中添加新 `el-tab-pane`

### 4.2 调用 API

```javascript
import { searchStock } from '../api/index.js'

// 自动处理 Token 注入和 401 跳转
const data = await searchStock('宁德时代')
// data.results → [{ts_code, symbol, name, industry}]
```

### 4.3 新增全局状态

如果要添加新的全局状态（类似下载进度浮层）：

```javascript
// 1. 在 src/api/ 下创建 store
import { ref, provide, inject } from 'vue'
const KEY = Symbol('myStore')
export function provideMyStore() { provide(KEY, { ... }) }
export function useMyStore() { return inject(KEY, { ... }) }

// 2. 在 App.vue 中 provide
import { provideMyStore } from './api/myStore.js'
provideMyStore()

// 3. 在组件中 inject
import { useMyStore } from '../api/myStore.js'
const store = useMyStore()
```

### 4.4 调整样式

全局样式在 `src/assets/style.css` 中，覆盖 Element Plus 主题色：

```css
/* 覆盖 Element Plus 主题色 */
.el-button--primary {
  --el-button-bg-color: var(--wood-400);
}
```

组件样式使用 `<style scoped>` 避免污染，深度选择器用 `:deep()`。

## 五、调试技巧

### 5.1 后端调试

```bash
# 查看后端日志
tail -f /tmp/backend_8320.log

# 直接调 API 验证
curl -s http://localhost:8320/api/stock/search?q=宁德 \
  -H "Authorization: $(curl -s -X POST http://localhost:8320/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"username":"zgx","password":"68697311"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])'
  )"
```

### 5.2 数据库查询

```bash
cd /home/stockagent/project_space/research/experiments/front/backend
conda run -n stock_agent python -c "
from database import db
rows = db.execute('SELECT * FROM stock_pool')
for r in rows:
    print(r)
"
```

### 5.3 前端调试

- Vite HMR 模式下修改代码即时生效
- 浏览器开发者工具 Network 面板查看 API 请求和响应
- Vue DevTools 可以检查组件的状态和 props

## 六、常见问题

### 登录后一直跳转回登录页

Token 过期或后端重启导致内存中的 Token 丢失。重新登录即可。

### 搜索股票无结果

检查 Tushare Token 是否配置正确，以及 `stg_stock_basic` 表是否有数据：

```bash
conda run -n stock_agent python -c "
from database import db
r = db.execute('SELECT COUNT(*) as c FROM stg_stock_basic')
print(f'股票基础信息: {r[0][\"c\"]} 条')
"
```

### 换手率不显示

确认 `daily_basic` 接口在对应交易日是否有数据：
- 数据在每个交易日 15:00-16:00 入库
- 非交易日无新数据

### DOCX 字体问题

Word 文档样式在以下文件修改：
```
/home/stockagent/project_space/research/experiments/report_machine/office/output/md_to_docx.py
```
修改后无需重启前端，只需重启后端即可生效。
