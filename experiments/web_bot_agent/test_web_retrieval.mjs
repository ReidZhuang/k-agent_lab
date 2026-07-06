/**
 * 用 @iflow-mcp/guangxiangdebizi-web-retrieval-mcp 解析 stcn.com
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { writeFileSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = resolve(__dirname, 'results');
mkdirSync(RESULTS_DIR, { recursive: true });

const transport = new StdioClientTransport({
  command: 'node',
  args: [
    '/home/stockagent/project_space/research/experiments/web_bot_agent/node_modules/@iflow-mcp/guangxiangdebizi-web-retrieval-mcp/build/index.js'
  ],
});

const client = new Client({ name: 'stcn-test', version: '1.0.0' });
await client.connect(transport);
console.log('✅ 连接成功\n');

console.log('▶ 调用 analyze_web_structure...');
const result = await client.callTool({
  name: 'analyze_web_structure',
  arguments: { url: 'https://www.stcn.com' },
});

const content = result.content?.[0]?.text || JSON.stringify(result, null, 2);
writeFileSync(resolve(RESULTS_DIR, '05_web_retrieval_structure.md'), content, 'utf-8');
console.log(`   结果长度: ${content.length} 字符`);
console.log('   已保存到: results/05_web_retrieval_structure.md\n');
console.log('   ── 预览 ──\n');
console.log(content.slice(0, 2000) + '\n...\n\n✅ 完成');

await client.close();
