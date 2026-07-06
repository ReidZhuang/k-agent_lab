/**
 * web-forager (duckduckgo-mcp v3) 提取 stcn.com 门户页面
 *
 * 使用 web-forager MCP server 的 jina_fetch 工具
 * 提取 https://www.stcn.com 门户页面内容并转为 Markdown
 */

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { writeFileSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = resolve(__dirname, 'results');
mkdirSync(RESULTS_DIR, { recursive: true });

const TARGET_URL = 'https://www.stcn.com';

async function main() {
  console.log('══════════════════════════════════════════════════');
  console.log('  web-forager (duckduckgo-mcp v3) 提取 stcn.com');
  console.log(`  时间: ${new Date().toISOString()}`);
  console.log('══════════════════════════════════════════════════\n');

  // 启动 MCP 连接
  const transport = new StdioClientTransport({
    command: 'web-forager',
    args: ['serve'],
  });

  const client = new Client({ name: 'stcn-extractor', version: '1.0.0' });
  await client.connect(transport);
  console.log('✅ web-forager MCP 连接成功\n');

  // =====================================================
  // 1. 搜索 stcn.com
  // =====================================================
  console.log('▶ 1/3: duckduckgo_search 搜索证券时报网...');
  try {
    const searchResult = await client.callTool({
      name: 'duckduckgo_search',
      arguments: {
        query: '证券时报网 stcn.com',
        max_results: 10,
        output_format: 'json'
      }
    });
    const searchText = typeof searchResult.content[0]?.text === 'string'
      ? searchResult.content[0].text : JSON.stringify(searchResult.content, null, 2);
    writeFileSync(resolve(RESULTS_DIR, '01_search_results.json'), searchText, 'utf-8');
    console.log(`   结果已保存 → results/01_search_results.json\n`);
    console.log(`   预览:\n${searchText.slice(0, 500)}...\n`);
  } catch (err) {
    console.log(`   ⚠️ 搜索失败: ${err.message}\n`);
  }

  // =====================================================
  // 2. jina_fetch 提取 stcn.com 门户内容
  // =====================================================
  console.log('▶ 2/3: jina_fetch 提取门户页面...');
  try {
    const fetchResult = await client.callTool({
      name: 'jina_fetch',
      arguments: {
        url: TARGET_URL,
        format: 'markdown',
        max_length: null,
        with_images: false,
      }
    });

    const content = typeof fetchResult.content[0]?.text === 'string'
      ? fetchResult.content[0].text : JSON.stringify(fetchResult.content, null, 2);

    // 保存完整内容
    writeFileSync(resolve(RESULTS_DIR, '02_jina_fetch_markdown.md'), content, 'utf-8');
    console.log(`   结果已保存 → results/02_jina_fetch_markdown.md`);
    console.log(`   内容长度: ${content.length} 字符\n`);
    console.log(`   ── 内容预览 ──\n${content.slice(0, 3000)}\n...\n`);

  } catch (err) {
    console.log(`   ⚠️ jina_fetch 失败: ${err.message}\n`);
    // 回退：用 CLI 命令
    console.log('   ▶ 改用 CLI 命令 web-forager fetch ...');
    await fallbackFetch();
  }

  // =====================================================
  // 3. 新闻搜索
  // =====================================================
  console.log('▶ 3/3: duckduckgo_news_search 搜索 stcn 最新新闻...');
  try {
    const newsResult = await client.callTool({
      name: 'duckduckgo_news_search',
      arguments: {
        query: '证券时报',
        max_results: 10,
        output_format: 'json'
      }
    });
    const newsText = typeof newsResult.content[0]?.text === 'string'
      ? newsResult.content[0].text : JSON.stringify(newsResult.content, null, 2);
    writeFileSync(resolve(RESULTS_DIR, '03_news_search.json'), newsText, 'utf-8');
    console.log(`   结果已保存 → results/03_news_search.json\n`);
  } catch (err) {
    console.log(`   ⚠️ 新闻搜索失败: ${err.message}\n`);
  }

  await client.close();
  console.log('\n✅ 全部完成！结果保存在:', RESULTS_DIR);
}

/**
 * 备用方案：直接用 CLI 命令
 */
async function fallbackFetch() {
  const { execSync } = await import('child_process');
  try {
    const output = execSync(`web-forager fetch "${TARGET_URL}" --format markdown 2>&1`, {
      encoding: 'utf-8',
      timeout: 30000,
    });
    writeFileSync(resolve(RESULTS_DIR, '02_cli_fetch_markdown.md'), output, 'utf-8');
    console.log(`   CLI 结果已保存 → results/02_cli_fetch_markdown.md`);
    console.log(`   内容长度: ${output.length} 字符\n`);
  } catch (err2) {
    console.log(`   ⚠️ CLI 回退也失败: ${err2.message}`);
  }
}

main().catch(err => {
  console.error('❌ 主流程错误:', err);
  process.exit(1);
});
