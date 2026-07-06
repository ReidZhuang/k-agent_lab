/**
 * 使用 web-forager MCP 搜索 "www.stcn.com 宁德时代"
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const transport = new StdioClientTransport({
  command: 'web-forager',
  args: ['serve'],
});

const client = new Client({ name: 'search-stcn', version: '1.0.0' });
await client.connect(transport);

console.log('✅ 已连接 web-forager\n');

// 先列出可用工具
const tools = await client.listTools();
console.log('📋 可用工具:', tools.tools.map(t => t.name).join(', '), '\n');

// 搜索
console.log('🔍 搜索: "www.stcn.com 宁德时代"\n');
const result = await client.callTool({
  name: 'duckduckgo_search',
  arguments: {
    query: 'www.stcn.com 宁德时代',
  },
});

const content = result.content?.[0]?.text || JSON.stringify(result, null, 2);
console.log(content);

await client.close();
console.log('\n✅ 完成');
