'use strict';

/**
 * 付费法律库适配器「模板」（占位，未启用）。
 *
 * 当你将来拿到付费法律库（如北大法宝、威科先行、法信等）的 API 凭证时，
 * 复制本文件为例如 `pkulaw.js`，按其官方文档填好下面的请求逻辑，
 * 再到 registry.js 里注册即可——合同审查会自动把它的真实案例/意见库结果一并纳入。
 *
 * ⚠️ 凭证安全：API key / token 必须通过环境变量或本地 config.json 注入，
 *    千万不要把密钥硬编码进代码或提交到公开仓库 / PR。
 */

async function search(keyword, opts = {}) {
  const apiKey = process.env.PAID_LEGAL_API_KEY || (opts.config && opts.config.apiKey);
  if (!apiKey) {
    return {
      ok: false,
      items: [],
      error: '未配置付费法律库凭证（PAID_LEGAL_API_KEY），该适配器处于未启用状态。',
    };
  }

  // TODO: 按你所购买服务的官方 API 文档实现真实请求，例如：
  //
  //   const res = await fetch(`https://api.<vendor>.com/v1/search`, {
  //     method: 'POST',
  //     headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
  //     body: JSON.stringify({ q: keyword, size: opts.size || 6 }),
  //   });
  //   const json = await res.json();
  //   const items = json.results.map((r) => ({
  //     title: r.title,
  //     summary: r.abstract,        // 真实案例/法律意见摘要
  //     court: r.court,             // 审理法院（案例）
  //     caseNo: r.caseNumber,       // 案号
  //     link: r.url,                // 详情链接
  //     source: 'paid-library',
  //   }));
  //   return { ok: true, items };

  return {
    ok: false,
    items: [],
    error: '付费适配器模板尚未实现，请按厂商 API 文档补全 search()。',
  };
}

module.exports = {
  name: 'paid-library',
  label: '付费法律库（模板·未启用）',
  authoritative: true,
  free: false,
  enabled: false, // 实现并配置好凭证后改为 true
  search,
};
