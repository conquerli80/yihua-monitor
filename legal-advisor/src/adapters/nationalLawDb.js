'use strict';

/**
 * 适配器：国家法律法规数据库（官方、免费、权威）
 * 数据源：https://flk.npc.gov.cn  （全国人大常委会法制工作委员会主办）
 *
 * 作用：在审查合同时，实时检索相关法律法规，确认其【现行有效性】并返回【官方链接】，
 *      让 AI 给出的意见有真实、权威的法条作为支撑，而不是凭空生成。
 *
 * 重要说明：
 * - 官方网站接口为非公开 API，参数/返回结构可能随官网改版变化。本适配器对返回结构做了
 *   容错解析；若官方改版导致检索失败，程序会自动降级到本地精选法条库（statutes.js），
 *   并在结果中标注 source=local，提示你以官方库为准。
 * - 该接口需要联网访问 flk.npc.gov.cn。部分云/受限网络会拦截该域名，请在本机运行。
 * - 仅做检索与引用，不抓取、不缓存大量正文，遵守对方网站的合理使用。
 */

const https = require('https');
const { URL } = require('url');

const DEFAULT_BASE = 'https://flk.npc.gov.cn';
const SEARCH_PATH = '/api/';

function httpRequest(method, urlStr, { body, headers, timeout } = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlStr);
    const opts = {
      method,
      hostname: u.hostname,
      path: u.pathname + u.search,
      port: u.port || 443,
      headers: {
        'User-Agent':
          'Mozilla/5.0 (compatible; legal-advisor/1.0; contract-review tool)',
        Accept: 'application/json, text/plain, */*',
        ...(headers || {}),
      },
      timeout: timeout || 12000,
    };
    const req = https.request(opts, (res) => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (c) => (data += c));
      res.on('end', () =>
        resolve({ status: res.statusCode, headers: res.headers, body: data })
      );
    });
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy(new Error('请求超时（官方法规库无响应）'));
    });
    if (body) req.write(body);
    req.end();
  });
}

/** 容错地从官方返回中提取条目数组。 */
function extractItems(json) {
  if (!json) return [];
  const r = json.result || json.data || json;
  const arr = (r && (r.data || r.list || r.records)) || (Array.isArray(r) ? r : []);
  return Array.isArray(arr) ? arr : [];
}

function normalizeItem(it, base) {
  const path = it.url || it.path || it.detailUrl || '';
  const link = path
    ? path.startsWith('http')
      ? path
      : `${base}${path.startsWith('/') ? '' : '/'}${path}`
    : `${base}`;
  return {
    title: it.title || it.name || it.fileName || '(未命名法律文件)',
    office: it.office || it.publishOrg || it.department || '',
    publishDate: it.publish || it.publishDate || it.f_gbrq || it.gbrq || '',
    expiryDate: it.expiry || it.f_sxrq || it.sxrq || '',
    statusText: it.status || it.statusText || it.state || '',
    type: it.type || it.flType || '',
    id: it.id || it.f_id || it.lawId || '',
    link,
    source: 'national-law-db',
  };
}

/**
 * 检索官方法规库。
 * @param {string} keyword  关键词，如「合同 违约金」「民法典」
 * @param {object} opts     { page, size, type, base }
 * @returns {Promise<{ok:boolean, items:Array, raw?:any, error?:string}>}
 */
async function search(keyword, opts = {}) {
  const base = opts.base || DEFAULT_BASE;
  const page = opts.page || 1;
  const size = opts.size || 6;
  const type = opts.type || 'flfg'; // flfg=法律法规
  const params = new URLSearchParams({
    type,
    searchType: 'title;vague',
    sortTr: 'f_bbrq_s;desc',
    gbrqStart: '',
    gbrqEnd: '',
    sxrqStart: '',
    sxrqEnd: '',
    sort: 'true',
    page: String(page),
    size: String(size),
    'q.s': keyword,
    keyword,
  });

  // 官方接口对 GET / POST 都较宽容；优先 POST（更接近官网行为），失败再尝试 GET。
  const attempts = [
    {
      method: 'POST',
      url: `${base}${SEARCH_PATH}`,
      body: params.toString(),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    },
    { method: 'GET', url: `${base}${SEARCH_PATH}?${params.toString()}` },
  ];

  let lastErr = '';
  for (const a of attempts) {
    try {
      const res = await httpRequest(a.method, a.url, {
        body: a.body,
        headers: a.headers,
      });
      if (res.status !== 200) {
        lastErr = `HTTP ${res.status}`;
        continue;
      }
      let json;
      try {
        json = JSON.parse(res.body);
      } catch (_e) {
        lastErr = '返回非 JSON（官网可能改版或被网络拦截）';
        continue;
      }
      const items = extractItems(json).map((it) => normalizeItem(it, base));
      return { ok: true, items, raw: json };
    } catch (e) {
      lastErr = e.message;
    }
  }
  return { ok: false, items: [], error: lastErr || '检索失败' };
}

module.exports = {
  name: 'national-law-db',
  label: '国家法律法规数据库（官方·免费）',
  authoritative: true,
  free: true,
  search,
};

// CLI 自测： node src/adapters/nationalLawDb.js 合同 违约金
if (require.main === module) {
  const kw = process.argv.slice(2).join(' ') || '合同';
  search(kw)
    .then((r) => {
      if (!r.ok) {
        console.error('检索失败：', r.error);
        console.error('（若在受限网络中运行，请改在本机运行；官方库域名可能被拦截。）');
        process.exit(1);
      }
      console.log(`命中 ${r.items.length} 条：`);
      r.items.forEach((it, i) =>
        console.log(
          `${i + 1}. ${it.title}  [${it.statusText || '状态未知'}]  ${it.publishDate}\n   ${it.link}`
        )
      );
    })
    .catch((e) => {
      console.error('异常：', e.message);
      process.exit(1);
    });
}
