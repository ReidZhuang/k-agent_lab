/**
 * 探查 @ericthered926/duckduckgo-mcp-server 的 capabilities
 */
import { spawn } from 'child_process';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

async function main() {
  console.log('=== 启动 @ericthered926/duckduckgo-mcp-server 并探查工具列表 ===\n');

  const transport = new StdioClientTransport({
    command: 'node',
    args: [
      '/home/stockagent/project_space/research/experiments/web_bot_agent/node_modules/@ericthered926/duckduckgo-mcp-server/build/index.js'
    ],
  });

  const client = new Client({
    name: 'inspect-client',
    version: '1.0.0',
  });

  try {
    await client.connect(transport);
    console.log('✅ MCP 连接成功\n');

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
