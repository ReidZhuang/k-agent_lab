这三款工具的安装都不复杂，主要都依赖 **Docker** 或 **Go** 环境，你可以根据你的技术栈来选择。

### 🐳 OrioSearch：功能最全的 Tavily 替代品

**OrioSearch** 是一个功能非常全面的 Tavily 替代品，集成了 SearXNG 搜索引擎、FastAPI、Redis 缓存等组件。

**安装前提**：需要安装 **Docker** 和 **Docker Compose**。

**安装步骤**：

1.  **克隆仓库**：
    ```bash
    git clone https://github.com/vkfolio/orio-search.git
    cd orio-search
    ```
2.  **启动服务**（这会同时启动 API、SearXNG 和 Redis 三个服务）：
    ```bash
    docker compose up --build
    ```
3.  **（可选）启用 AI 答案生成**：如果需要使用 AI 总结功能，可以拉取 Ollama 服务：
    ```bash
    docker compose --profile llm up --build
    ```
4.  **验证**：服务启动后，访问 `http://localhost:8000/health`，返回 `{"status":"ok"}` 即表示成功。

---

### ⚙️ tavily-open：灵活的分层抓取工具

**tavily-open** 同样是 SearXNG 的封装，其特点是采用了分层抓取策略：优先轻量级 HTTP 抓取，必要时才动用 Jina Reader 或浏览器渲染。

**安装前提**：需要安装 **Docker** 和 **Docker Compose**。

**安装步骤**：

1.  **克隆仓库**：
    ```bash
    git clone https://github.com/jianjungki/tavily-open.git
    cd tavily-open
    ```
2.  **启动服务**：根据官方文档，通常也是使用 Docker Compose 一键启动。
3.  **验证**：服务启动后，可以通过 Swagger 文档（通常是 `http://localhost:8000/docs`）查看 API 详情。

---

### 🤖 SearXNG MCP Server：与 AI Agent 集成的多种选择

“SearXNG MCP Server”并非特指某一个项目，而是指一类将 SearXNG 封装成 MCP 服务的工具。这里介绍几种主流的安装方式：

#### 方式一：一体化 Docker 部署 (推荐，最简单)

**`codeprimate/searxng_docker`** 项目提供了一个预配置的完整 Docker 栈。

*   **安装前提**：**Docker** 和 **Docker Compose**。
*   **安装步骤**：
    1.  克隆仓库并进入目录。
    2.  复制并编辑环境变量文件：
        ```bash
        cp env.example .env
        # 使用 openssl 生成一个随机密钥，填入 .env 文件中的 SEARXNG_SECRET_KEY
        openssl rand -hex 32
        ```
    3.  启动所有服务：
        ```bash
        docker compose up -d
        ```
    4.  **验证**：
        *   **Web UI**：访问 `http://localhost:7777`。
        *   **搜索 API**：执行 `curl "http://localhost:7777/search?q=test&format=json"`。
        *   **MCP 服务**：访问 `http://localhost:7778/health`。

#### 方式二：轻量级 Go 二进制文件

**`denysvitali/searxng-mcp`** 是一个用 Go 编写的轻量级 MCP 服务器。

*   **安装前提**：需要安装 **Go** 语言环境。
*   **安装步骤**：
    1.  直接使用 `go install` 命令安装：
        ```bash
        go install github.com/denysvitali/searxng-mcp@v0.0.7
        ```
    2.  确保 `~/go/bin` 目录在系统的 `PATH` 环境变量中。
    3.  运行服务（需要指定一个公网 SearXNG 实例地址，或自己搭建一个）：
        ```bash
        searxng-mcp serve --instance-url https://your-searxng-instance.com
        ```

#### 方式三：其他安装途径

*   **Docker Compose + 源码编译 (`aicrafted/searxng-mcp`)**：这个项目提供了 `docker-compose.yml` 文件，可以一键启动 SearXNG 和 MCP 服务。
*   **NPM 安装 (`searxng-crawl4ai-mcp`)**：这是一个 Node.js 包，可以通过 NPM 安装：
    ```bash
    npm install -g searxng-crawl4ai-mcp
    ```
*   **Smithery 一键安装**：对于 Claude Desktop 用户，可以通过 Smithery 平台自动安装：
    ```bash
    npx -y @smithery/cli install @kevinwatt/mcp-server-searxng --client claude
    ```

### 💎 如何选择？

*   **追求功能全面、开箱即用**：选择 **OrioSearch**，它集成了搜索、缓存、AI 总结等全套功能。
*   **需要高度定制化的抓取策略**：选择 **tavily-open**，它的分层抓取设计提供了更多控制。
*   **希望在 AI Agent (如 Claude) 中简单集成**：
    *   最省心：使用 **`codeprimate/searxng_docker`** 一键部署完整环境。
    *   最轻量：如果已有 SearXNG 实例，使用 **`denysvitali/searxng-mcp`** 的 Go 二进制文件。