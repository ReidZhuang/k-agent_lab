# 注意事项与 FAQ

---

## 一、硬件与性能

### Q: 需要什么硬件？

最低配置（可运行，较慢）：
- GPU：6GB+ 显存（GLM4:9b 占用约 6.3GB）
- 内存：16GB+
- 硬盘：10GB+ 空闲（存放模型文件）

推荐配置：
- GPU：8GB+ 显存
- 内存：32GB
- SSD

### Q: 处理一篇 8000 字的文章要多久？

取决于 GPU。以 8GB VRAM / GLM4:9b 为例：
- 单次 LLM 推理：15-35 秒
- segments 模式全文处理：30-120 秒
- summary 模式全文处理：15-60 秒（只需一次合并 LLM 调用）

### Q: 可以换其他模型吗？

可以。在 `config/config.json` 中修改 `ollama.models.default`：

```json
"models": {
  "default": "deepseek-r1:8b"
}
```

注意不同模型的有效注意力窗口可能不同，需要自行测试。

---

## 二、LLM 行为

### Q: 为什么 temperature 要设为 0？

temperature=0 保证**确定性输出**：同样输入每次结果一样，方便调试和复现。

如果设为 >0（如 0.1-0.3），相同的正文每次分组结果可能不同，导致结果不一致。

### Q: 为什么长文本（>5000 字）会处理不全？

这是本地小模型的**有效注意力窗口**限制。GLM4:9b 对超过约 5,000 字的正文可能出现格式漂移、内容遗漏。

**解决方案**：系统自动将超长文本按 token 阈值分块（`max_tokens: 2000`），每块独立处理后再合并。

### Q: summary 模式下长文本怎么处理？

分段处理：每块独立生成概括/摘要/要点 → LLM 合并各方概括 → 硬合并摘要和要点。

---

## 三、搜索与提取

### Q: 搜索 API 返回空结果？

常见原因：
1. **代理问题**：`web-forager` 需要代理访问外网，检查 `config.json` 中的代理配置
2. **DuckDuckGo 限制**：频繁搜索可能被临时限制，稍等后再试
3. **关键词太偏**：尝试更通用的搜索词

### Q: 正文提取失败？

系统使用 `trafilatura` 作为主要提取器，失败时自动降级到 `readability-lxml`：
- 某些动态渲染的页面（SPA、大量 JS）可能提取不到内容
- 反爬严格的网站可能返回空
- PDF 页面不支持

### Q: 如何确认提取到了正文？

通过 `/status` 接口查看 `article_count`。如果 count > 0 但没有 segments，说明提取到了 HTML 但正文内容极少（<10 字符）。

---

## 四、API 使用

### Q: 需要轮询多久？

一般来说：
- segments 模式（3 篇）：30-120 秒
- summary 模式（3 篇）：15-60 秒

建议轮询间隔 5 秒。

### Q: 会话会过期吗？

会。默认 TTL 为 60 分钟，超时自动关闭。也可通过 `POST /close/{session_id}` 主动关闭。

### Q: 可以同时发起多个搜索吗？

可以。每次 `/search` 创建一个独立会话，多个搜索可以并行处理。

### Q: summary 模式下如何查看要点的原文？

使用 `POST /point-text` 端点：

```bash
curl -s -X POST http://localhost:8300/point-text \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s_...", "article_id": "a_01", "point_indices": [7]}'
```

系统自动定位该要点来自哪一块，只送那一块给 LLM，找到对应的原文段落返回。

---

## 五、常见错误

| 错误信息 | 原因 | 解决方法 |
|---|---|---|
| `Ollama connection refused` | Ollama 服务未运行 | 启动 Ollama：`ollama serve` |
| `Ollama 错误: 500` | 模型未拉取或显存不足 | `ollama pull glm4:9b-chat-q4_K_M` |
| 分组数 = 0 | LLM 输出格式异常（长文本注意力问题） | 调小 `max_tokens` 或检查 prompt |
| 搜索返回空列表 | 网络或代理问题 | 检查代理配置和网络连通性 |
| Session not found | 会话已过期或 session_id 错误 | 重新发起搜索 |
| `point-text only available in summary mode` | 用 segments 模式调用了 /point-text | 确认 mode 为 summary |

---

## 六、版本说明

**当前版本**: 1.0.0

### 本版本包含
- ✅ 网络搜索（web-forager）
- ✅ 网页正文提取（trafilatura + readability 降级）
- ✅ 文本按 Token 分块
- ✅ segments 模式：LLM 分组（要点 + 概括 + 关键字）
- ✅ summary 模式：LLM 整篇摘要 + 相关摘要 + 核心要点
- ✅ 跨块偏移还原与合并
- ✅ 跨块 LLM 概括合并（summary 模式）
- ✅ 要点→原文反向定位（POST /point-text）
- ✅ 多块要点批量并行定位
- ✅ 会话管理与自动过期清理
- ✅ RESTful API（FastAPI）
- ✅ 两阶段并行架构（提取+切块 → LLM → 合并）

### 本版本未包含
- ❌ Stage 2：跨分组 LLM 再合并（实验分支中）
- ❌ Stage 3：分组结果精炼复核（实验分支中）
- ❌ 前端 UI
- ❌ 持久化存储

---

**上一节：[完整使用示例](05_完整使用示例.md)** | **[返回首页](01_快速开始.md)**
