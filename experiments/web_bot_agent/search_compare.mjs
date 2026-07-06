/**
 * 对比 ericthered926 duckduckgo-mcp 不同配置的搜索结果
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const query = 'site:stcn.com 宁德时代';

const proxy = { http_proxy: 'http://172.20.32.1:7890', https_proxy: 'http://172.20.32.1:7890' };

// 配置 A：默认 snippet（150字）
const transportA = new StdioClientTransport({
  command: 'node',
  args: ['/home/stockagent/project_space/research/experiments/web_bot_agent/node_modules/@ericthered926/duckduckgo-mcp-server/build/index.js'],
  env: {
    ...proxy,
    DDG_MAX_RESULTS: '20',
    DDG_MAX_SNIPPET_LENGTH: '150',
    DDG_ENABLE_FULL_CONTENT: 'false',
    DDG_OUTPUT_FORMAT: 'json',
  }
});

// 配置 B：完整 description + 最大结果
const transportB = new StdioClientTransport({
  command: 'node',
  args: ['/home/stockagent/project_space/research/experiments/web_bot_agent/node_modules/@ericthered926/duckduckgo-mcp-server/build/index.js'],
  env: {
    ...proxy,
    DDG_MAX_RESULTS: '20',
    DDG_MAX_SNIPPET_LENGTH: '500',
    DDG_ENABLE_FULL_CONTENT: 'true',
    DDG_OUTPUT_FORMAT: 'json',
  }
});

async function doSearch(transport, label) {
  const client = new Client({ name: 'search-test', version: '1.0.0' });
  await client.connect(transport);
  console.log(`\n========== ${label} ==========\n`);
  const result = await client.callTool({
    name: 'duckduckgo_web_search',
    arguments: { query },
  });
  const content = result.content?.[0]?.text || '';
  const data = JSON.parse(content);
  console.log(`返回 ${data.length} 条结果\n`);
  data.forEach((r, i) => {
    console.log(`  [${i + 1}] ${r.title}`);
    console.log(`      URL: ${r.url}`);
    console.log(`      ${label === '配置A' ? 'Snippet' : 'Description'}: ${r.description?.slice(0, 250)}`);
    console.log('');
  });
  await client.close();
}

await doSearch(transportA, '配置A - 默认 snippet (150字)');
await doSearch(transportB, '配置B - 完整 description');
