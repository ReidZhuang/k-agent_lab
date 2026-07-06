/**
 * 第一步：探索 duckduckgo-mcp + 提取 www.stcn.com 门户页面
 *
 * 这个脚本做两件事：
 * 1. 使用 duckduckgo-mcp 搜索 stcn.com 相关内容和最新新闻
 * 2. 使用 Node.js fetch 直接抓取门户首页原始内容
 *
 * 通过对比理解 MCP 搜索工具 vs 直接页面抓取的区别
 */

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { writeFileSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = resolve(__dirname, 'results');
mkdirSync(RESULTS_DIR, { recursive: true });

// ============================================================
// 第一部分：使用 duckduckgo-mcp 搜索 stcn.com
// ============================================================
async function searchWithDuckDuckGo() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  第一部分: duckduckgo-mcp 搜索              ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  const transport = new StdioClientTransport({
    command: 'node',
    args: [
      resolve(__dirname, 'node_modules/@ericthered926/duckduckgo-mcp-server/build/index.js')
    ],
  });

  const client = new Client({ name: 'stcn-fetcher', version: '1.0.0' });

  try {
    await client.connect(transport);
    console.log('✅ duckduckgo-mcp 连接成功\n');

    // --- 搜索1: 搜索 stcn.com 证券时报网 ---
    console.log('▶ 搜索 "证券时报网 stcn.com" ...');
    const search1 = await client.callTool({
      name: 'duckduckgo_web_search',
      arguments: { query: '证券时报网 stcn.com', limit: 10 }
    });
    console.log('  返回结果:\n');
    for (const item of search1.content || []) {
      console.log(`  ${item.text}\n`);
    }

    // --- 搜索2: 搜索最新新闻 ---
    console.log('▶ 搜索 stcn.com 最新财经新闻 ...');
    const search2 = await client.callTool({
      name: 'duckduckgo_news_search',
      arguments: { query: 'stcn.com 财经', limit: 10, time: 'day' }
    });
    console.log('  返回结果:\n');
    for (const item of search2.content || []) {
      console.log(`  ${item.text}\n`);
    }

    await client.close();
    return { search1, search2 };
  } catch (err) {
    console.error('❌ duckduckgo-mcp 搜索失败:', err.message);
    return null;
  }
}

// ============================================================
// 第二部分：直接使用 fetch 提取门户页面内容
// ============================================================
async function fetchPortalPage() {
  console.log('\n╔══════════════════════════════════════════════╗');
  console.log('║  第二部分: fetch 直接抓取门户页面           ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  const targetUrl = 'https://www.stcn.com';
  console.log(`▶ 正在抓取: ${targetUrl}\n`);

  try {
    const response = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      },
      signal: AbortSignal.timeout(15000)
    });

    console.log(`  状态码: ${response.status} ${response.statusText}`);
    console.log(`  内容类型: ${response.headers.get('content-type')}`);
    console.log(`  内容长度: ${response.headers.get('content-length') || '未知'}\n`);

    const html = await response.text();
    console.log(`  实际获取 HTML 长度: ${html.length} 字符\n`);

    // --- 提取页面结构信息 ---
    const title = html.match(/<title>([^<]*)<\/title>/i)?.[1]?.trim() || '(未找到)';
    console.log(`  页面标题: ${title}`);

    // 提取 meta description
    const description = html.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']*)["']/i)?.[1]?.trim() || '(无)';
    console.log(`  页面描述: ${description}\n`);

    // 提取所有链接（门户结构分析）
    const linkRegex = /<a[^>]*href=["']([^"']*)["'][^>]*>([\s\S]*?)<\/a>/gi;
    const links = [];
    let match;
    while ((match = linkRegex.exec(html)) !== null) {
      const href = match[1].trim();
      const text = match[2].replace(/<[^>]*>/g, '').trim();
      if (href && text && !href.startsWith('#') && !href.startsWith('javascript:')) {
        links.push({ href, text });
      }
    }

    // 去重并归类
    const internalLinks = links.filter(l => l.href.startsWith('/') || l.href.includes('stcn.com'));
    const categories = {};
    for (const link of internalLinks.slice(0, 50)) {
      const section = link.href.split('/').filter(Boolean)[0] || '(首页)';
      if (!categories[section]) categories[section] = [];
      if (categories[section].length < 5) {
        categories[section].push({ text: link.text, url: link.href });
      }
    }

    console.log(`  提取到 ${links.length} 个链接 (内部: ${internalLinks.length} 个)`);
    console.log('\n  ─── 栏目结构概览 ───\n');
    for (const [section, items] of Object.entries(categories)) {
      console.log(`  [${section}]`);
      for (const item of items) {
        console.log(`    - ${item.text || '(无文字)'} → ${item.url}`);
      }
      console.log('');
    }

    // --- 提取正文可见文本 ---
    const bodyText = html
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
      .replace(/<nav[^>]*>[\s\S]*?<\/nav>/gi, '')
      .replace(/<[^>]+>/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .replace(/&nbsp;/g, ' ')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&amp;/g, '&')
      .trim();

    return {
      url: targetUrl,
      status: response.status,
      title,
      description,
      htmlLength: html.length,
      totalLinks: links.length,
      internalLinks: internalLinks.length,
      categories,
      bodyText: bodyText.slice(0, 8000), // 限制长度
      rawHtml: html.slice(0, 5000),       // 保留原始 HTML 前 5000 字符用于参考
    };
  } catch (err) {
    console.error(`❌ 页面抓取失败:`, err.message);
    return null;
  }
}

// ============================================================
// 主流程
// ============================================================
async function main() {
  console.log('══════════════════════════════════════════════════');
  console.log('  stcn.com 门户页面提取报告');
  console.log(`  时间: ${new Date().toISOString()}`);
  console.log('══════════════════════════════════════════════════\n');

  // 第一部分: MCP 搜索
  const searchResults = await searchWithDuckDuckGo();

  // 第二部分: 页面抓取
  const pageData = await fetchPortalPage();

  // 保存结果
  console.log('\n╔══════════════════════════════════════════════╗');
  console.log('║  保存结果文件                               ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  // 1. 保存搜索报告
  const searchReport = [
    '=== duckduckgo-mcp 搜索结果 ===',
    '',
    '--- 搜索: "证券时报网 stcn.com" ---',
    ...((searchResults?.search1?.content || []).map(c => c.text)),
    '',
    '--- 新闻搜索: "stcn.com 财经" (近一天) ---',
    ...((searchResults?.search2?.content || []).map(c => c.text)),
  ].join('\n');
  writeFileSync(resolve(RESULTS_DIR, '01_mcp_search_results.txt'), searchReport, 'utf-8');
  console.log('  ✅ 01_mcp_search_results.txt');

  // 2. 保存页面结构分析
  if (pageData) {
    const structureReport = [
      '=== stcn.com 门户页面结构分析 ===',
      '',
      `URL: ${pageData.url}`,
      `状态码: ${pageData.status}`,
      `标题: ${pageData.title}`,
      `描述: ${pageData.description}`,
      `HTML长度: ${pageData.htmlLength} 字符`,
      `总链接数: ${pageData.totalLinks}`,
      `内部链接数: ${pageData.internalLinks}`,
      '',
      '--- 栏目结构 ---',
      ...Object.entries(pageData.categories).flatMap(([section, items]) => [
        `[${section}]`,
        ...items.map(item => `  - ${item.text} → ${item.url}`),
        '',
      ]),
      '',
      '--- 页面可见文本 (前8000字符) ---',
      '',
      pageData.bodyText,
    ].join('\n');
    writeFileSync(resolve(RESULTS_DIR, '02_page_structure.txt'), structureReport, 'utf-8');
    console.log('  ✅ 02_page_structure.txt');

    // 3. 保存原始 HTML 片段
    writeFileSync(resolve(RESULTS_DIR, '03_raw_html_sample.txt'), pageData.rawHtml, 'utf-8');
    console.log('  ✅ 03_raw_html_sample.txt');
  }

  // 4. 保存汇总报告
  const summary = [
    '══════════════════════════════════════════════════',
    'stcn.com 门户提取 - 工作汇总',
    '══════════════════════════════════════════════════',
    '',
    '工具:',
    '  - duckduckgo-mcp (@ericthered926/duckduckgo-mcp-server v0.6.0)',
    '  - Node.js fetch (原生)',
    '',
    'duckduckgo-mcp 提供的工具:',
    '  1. duckduckgo_web_search  - DuckDuckGo 网页搜索',
    '  2. duckduckgo_news_search - DuckDuckGo 新闻搜索',
    '',
    '特点:',
    '  - 返回搜索结果的标题、URL、摘要片段',
    '  - 支持 region/时间/安全搜索过滤',
    '  - 有速率限制 (1/sec, 15000/month)',
    '  - 默认返回 3 条结果 (可调 1-20)',
    '',
    '局限性:',
    '  - 仅搜索，不抓取完整页面内容',
    '  - 摘要长度有限 (~150 字符)',
    '  - 对中文网站的支持取决于 DuckDuckGo 索引',
    '',
    `报告时间: ${new Date().toISOString()}`,
  ].join('\n');
  writeFileSync(resolve(RESULTS_DIR, '00_summary.txt'), summary, 'utf-8');
  console.log('  ✅ 00_summary.txt');

  console.log('\n✅ 所有结果已保存到:', RESULTS_DIR);
}

main().catch(console.error);
