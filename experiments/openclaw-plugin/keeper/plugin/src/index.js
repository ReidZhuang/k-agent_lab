// ==========================================================================
// U7 插件入口（薄适配层）：把装配逻辑包进 OpenClaw 插件契约
// ==========================================================================
import { definePluginEntry } from 'openclaw/plugin-sdk/plugin-entry';
import { createKeeper, KEEPER_PREFIX } from './assembly.js';

export { KEEPER_PREFIX };

export default definePluginEntry({
  id: 'keeper-corpus-compress',
  name: 'keeper 语料语义压缩',
  description: '语义级语料压缩：取数结果 tag 为 JSON 行集(doc_id+行号)，模型按 discard_lines 申报删除，api.on("context") 只删发给模型的内存视图 —— 不动盘上 transcript，省 token 不减可用信息。',
  register(api) {
    // ⚠️ register 必须同步（OpenClaw 强制）：createKeeper 的同步段（cfg 解析→logger 同步构造
    // →各钩子 api.on 挂载）会在本函数返回前全部完成；钩子体内的 async 属运行时，不受限。
    createKeeper(api);
  },
});