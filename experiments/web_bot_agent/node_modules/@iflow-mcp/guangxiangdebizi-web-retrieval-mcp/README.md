# 🌐 Web Retrieval MCP

一个专门用于解析网页设计结构的 Model Context Protocol (MCP) 工具。通过提供URL，即可获得详细的页面结构分析，包括布局、导航、内容区域、表单、图片等元素的完整信息。

## ✨ 功能特性

- 🏗️ **页面布局分析** - 自动识别头部、底部、侧边栏等布局元素
- 📝 **标题结构解析** - 提取并分析H1-H6标题层次结构
- 🧭 **导航结构识别** - 解析网站导航菜单和链接结构
- 📄 **内容区域提取** - 识别主要内容区域和文本内容
- 📋 **表单信息分析** - 解析表单字段、提交方式等信息
- 🖼️ **图片资源统计** - 统计页面图片资源和属性信息
- 🔗 **链接关系分析** - 区分内部链接和外部链接
- 🎨 **样式特征检测** - 检测响应式设计、字体等样式信息

## 🚀 快速开始

### 安装依赖

```bash
npm install
```

### 构建项目

```bash
npm run build
```

### 启动服务

#### Stdio 模式（本地开发）

```bash
npm start
```

#### SSE 模式（通过 Supergateway）

```bash
# 安装 supergateway
npm install -g supergateway

# 启动 SSE 服务器
npm run sse
```

服务将在 `http://localhost:3100` 启动。

## 🔧 Claude 配置

### Stdio 模式配置

在 Claude 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "web-retrieval-mcp": {
      "command": "node",
      "args": ["path/to/web-retrieval-mcp/build/index.js"]
    }
  }
}
```

### SSE 模式配置

```json
{
  "mcpServers": {
    "web-retrieval-mcp": {
      "type": "sse",
      "url": "http://localhost:3100/sse",
      "timeout": 600
    }
  }
}
```

## 📖 使用方法

### 工具：analyze_web_structure

深度解析指定URL网页的前端设计架构与后端交互面。

#### 参数

- `url` (必需): 要解析的网页URL地址

#### 示例

```typescript
analyze_web_structure({
  url: "https://example.com"
})
```

#### 输出示例（节选）

```markdown
# 🌐 网页结构分析报告

**URL:** https://example.com
**标题:** Example Domain
**描述:** This domain is for use in illustrative examples

---

## 🏗️ 前端架构画像

- 框架候选: React, Next.js
- SPA 判定: ✅ 可能是 SPA
- 路由线索: React Router
- 构建工具线索: Webpack, Next.js build
- CSS 框架: Tailwind
- 微前端线索: 无

## 🔌 后端交互面（可通向后端的触点）

### 表单
- 表单 1: POST -> https://example.com/api/login [CSRF]
  - 字段: hidden token(_csrf), text(username), password(password)

### API/HTTP 端点
- https://example.com/api/v1/user
- https://api.example.com/graphql

### WebSocket
- wss://ws.example.com/realtime

...
```

## 🛠️ 开发

### 项目结构

```
src/
├── index.ts                    # MCP服务器主入口
└── tools/                      # 业务工具模块
    └── web-structure-analyzer.ts # 网页结构解析工具
```

### 开发模式

```bash
# 监听文件变化并自动重新编译
npm run dev
```

## 📋 技术栈

- **TypeScript** - 类型安全的JavaScript
- **@modelcontextprotocol/sdk** - MCP SDK
- **Cheerio** - 服务端jQuery实现，用于HTML解析
- **Axios** - HTTP客户端，用于获取网页内容

## 🔒 安全考虑

- 请求超时设置为10秒，避免长时间等待
- 使用标准浏览器User-Agent，提高兼容性
- 限制链接和内容提取数量，避免内存溢出
- URL格式验证，确保输入安全

## 📄 许可证

Apache License 2.0

## 👨‍💻 作者

**Xingyu Chen**
- 📧 Email: guangxiangdebizi@gmail.com
- 🔗 GitHub: [guangxiangdebizi](https://github.com/guangxiangdebizi/)
- 💼 LinkedIn: [Xingyu Chen](https://www.linkedin.com/in/xingyu-chen-b5b3b0313/)
- 📦 NPM: [xingyuchen](https://www.npmjs.com/~xingyuchen)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📝 更新日志

### v1.0.0
- 🎉 初始版本发布
- ✅ 基础网页结构解析功能
- ✅ 支持布局、导航、内容、表单、图片、链接分析
- ✅ 样式特征检测
- ✅ MCP协议支持