/**
 * 探查 duckduckgo-mcp 的 capabilities
 * 连接 MCP server，列出所有可用工具
 */
const { spawn } = require('child_process');
const { Client } = require('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = require('@modelcontextprotocol/sdk/client/stdio.js');

async function main() {
  console.log('=== 启动 duckduckgo-mcp 并探查工具列表 ===\n');

  const transport = new StdioClientTransport({
    command: 'npx',
    args: ['duckduckgo-mcp'],
  });

  const client = new Client({
    name: 'inspect-client',
    version: '1.0.0',
  });

  try {
    await client.connect(transport);
    console.log('✅ MCP 连接成功\n');

    // 列出 tools
    const toolsResult = await client.listTools();
    console.log(`📦 工具数量: ${toolsResult.tools.length}\n`);

    for (const tool of toolsResult.tools) {
      console.log(`━━━ 工具: ${tool.name} ━━━`);
      console.log(`  说明: ${tool.description || '(无描述)'}`);
      console.log(`  输入模式:`);
      console.log(JSON.stringify(tool.inputSchema, null, 4));
      console.log('');
    }

    await client.close();
  } catch (err) {
    console.error('❌ 错误:', err.message);
    process.exit(1);
  }
}

main();
