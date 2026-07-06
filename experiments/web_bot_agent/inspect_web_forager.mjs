/**
 * 探查 web-forager (duckduckgo-mcp v3) 的工具列表
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

async function main() {
  console.log('=== 启动 web-forager (duckduckgo-mcp v3) 并探查工具列表 ===\n');

  const transport = new StdioClientTransport({
    command: 'web-forager',
    args: ['serve'],
  });

  const client = new Client({ name: 'inspect', version: '1.0.0' });

  try {
    await client.connect(transport);
    console.log('✅ 连接成功\n');

    const toolsResult = await client.listTools();
    console.log(`📦 工具数量: ${toolsResult.tools.length}\n`);

    for (const tool of toolsResult.tools) {
      console.log(`━━━ 工具: ${tool.name} ━━━`);
      console.log(`  说明: ${tool.description || '(无描述)'}`);
      console.log(`  Schema:\n${JSON.stringify(tool.inputSchema, null, 2)}`);
      console.log('');
    }

    await client.close();
  } catch (err) {
    console.error('❌ 错误:', err.message);
    process.exit(1);
  }
}

main();
