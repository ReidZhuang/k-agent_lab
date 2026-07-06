/**
 * 探查 @iflow-mcp/guangxiangdebizi-web-retrieval-mcp 的工具
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const transport = new StdioClientTransport({
  command: 'node',
  args: [
    '/home/stockagent/project_space/research/experiments/web_bot_agent/node_modules/@iflow-mcp/guangxiangdebizi-web-retrieval-mcp/build/index.js'
  ],
});

const client = new Client({ name: 'inspect', version: '1.0.0' });
await client.connect(transport);
console.log('✅ 连接成功\n');

const tools = await client.listTools();
for (const tool of tools.tools) {
  console.log(`━━━ ${tool.name} ━━━`);
  console.log(`说明: ${tool.description || '(无)'}`);
  console.log(`输入模式:\n${JSON.stringify(tool.inputSchema, null, 2)}`);
  console.log('');
}

await client.close();
