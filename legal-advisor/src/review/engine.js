'use strict';

const { segmentContract } = require('./segment');
const { RULES } = require('./rules');
const { getStatuteByCode, searchLocalStatutes } = require('./statutes');
const registry = require('../adapters/registry');

const ESSENTIAL_TERMS = [
  { key: '当事人/主体', re: /(甲方|乙方|出卖人|买受人|委托人|受托人|双方当事人|名称|住所)/ },
  { key: '标的', re: /(标的|货物|服务内容|商品|项目|工作内容)/ },
  { key: '数量', re: /(数量|规格|面积|数额)/ },
  { key: '质量', re: /(质量|标准|验收)/ },
  { key: '价款/报酬', re: /(价款|价格|报酬|费用|金额|总价|单价)/ },
  { key: '履行期限/地点/方式', re: /(履行|交付|期限|时间|地点|方式|付款方式)/ },
  { key: '违约责任', re: /(违约|赔偿|责任)/ },
  { key: '争议解决', re: /(管辖|仲裁|诉讼|争议)/ },
];

/**
 * 核心审查：分条 -> 跑规则 -> 关联本地法条 -> （联网时）调适配器核对真实法条。
 * @param {string} contractText
 * @param {object} opts { useBackend:boolean }
 */
async function reviewContract(contractText, opts = {}) {
  const clauses = segmentContract(contractText);
  const fullText = contractText || '';

  // 1) 逐条跑规则
  const findings = [];
  for (const clause of clauses) {
    for (const rule of RULES) {
      let hit = false;
      try {
        hit = rule.test(clause.text, fullText);
      } catch (_e) {
        hit = false;
      }
      if (!hit) continue;
      const statutes = (rule.statutes || [])
        .map((c) => getStatuteByCode(c))
        .filter(Boolean);
      findings.push({
        ruleId: rule.id,
        clauseIndex: clause.index,
        clauseLabel: clause.label,
        clauseExcerpt: excerpt(clause.text),
        name: rule.name,
        severity: rule.severity,
        explain: rule.explain,
        suggest: rule.suggest,
        statutes,
      });
    }
  }

  // 2) 必备条款完整性检查（整篇维度）
  const missingTerms = ESSENTIAL_TERMS.filter((t) => !t.re.test(fullText)).map(
    (t) => t.key
  );
  if (missingTerms.length) {
    const s = getStatuteByCode('MFD-470');
    findings.push({
      ruleId: 'missing-essentials',
      clauseIndex: -1,
      clauseLabel: '整篇',
      clauseExcerpt: '',
      name: '可能缺少合同必备/重要条款',
      severity: missingTerms.length >= 3 ? 'high' : 'medium',
      explain: `合同未明显出现以下要素：${missingTerms.join('、')}。《民法典》第470条列举了合同一般应包含的条款，缺失可能导致权利义务不清、日后举证困难。`,
      suggest: '逐项补齐缺失要素；尤其“标的、数量、价款、履行、违约责任、争议解决”要写清楚。',
      statutes: s ? [s] : [],
    });
  }

  // 3) 联网核对：用命中的法条/规则关键词去真实法律后端检索（确认现行有效 + 官方链接）
  let backend = { used: false, results: [], errors: [], queries: [] };
  if (opts.useBackend !== false) {
    const keywords = buildKeywords(findings);
    backend.queries = keywords;
    backend.used = true;
    const perKeyword = await Promise.all(
      keywords.map(async (kw) => {
        const r = await registry.searchAll(kw, { size: 4 });
        return { keyword: kw, ...r };
      })
    );
    // 汇总去重官方条目
    const seen = new Set();
    for (const pk of perKeyword) {
      for (const res of pk.results) {
        for (const item of res.items) {
          const id = item.link || item.title;
          if (seen.has(id)) continue;
          seen.add(id);
          backend.results.push({ keyword: pk.keyword, ...item });
        }
      }
      for (const err of pk.errors) backend.errors.push({ keyword: pk.keyword, ...err });
    }
  }

  const summary = buildSummary(findings, clauses.length, missingTerms, backend);

  return {
    meta: {
      reviewedAt: new Date().toISOString(),
      clauseCount: clauses.length,
      findingCount: findings.length,
      backendUsed: backend.used,
      adapters: registry.listAdapters(),
    },
    summary,
    findings: sortBySeverity(findings),
    backend,
    disclaimer:
      '本报告由「规则体检 + 真实法条核对（+可选AI分析）」自动生成，属辅助参考，不构成法律意见，也不替代执业律师。涉及金额较大、担保、股权、知识产权、诉讼等重大事项，请务必咨询律师，或拨打全国法律援助热线 12348（免费）。',
  };
}

function buildKeywords(findings) {
  const set = new Set();
  for (const f of findings) {
    for (const s of f.statutes || []) {
      // 用法条标题中的关键词去检索官方库，确认现行有效性
      if (s.law) set.add(s.law); // 例：中华人民共和国民法典
    }
    // 规则名里的核心词
    if (/违约金/.test(f.name)) set.add('违约金');
    if (/定金|订金/.test(f.name)) set.add('定金');
    if (/格式|霸王/.test(f.name)) set.add('格式条款');
    if (/利率|利息/.test(f.name)) set.add('民间借贷 利率');
    if (/担保|连带/.test(f.name)) set.add('担保');
  }
  if (set.size === 0) set.add('中华人民共和国民法典');
  return Array.from(set).slice(0, 6);
}

function buildSummary(findings, clauseCount, missingTerms, backend) {
  const high = findings.filter((f) => f.severity === 'high').length;
  const med = findings.filter((f) => f.severity === 'medium').length;
  const low = findings.filter((f) => f.severity === 'low').length;
  const lines = [];
  lines.push(
    `共识别 ${clauseCount} 个条款，发现 ${findings.length} 处可关注点：高风险 ${high}、中风险 ${med}、提示 ${low}。`
  );
  if (high) lines.push('⚠ 存在高风险条款，建议在签署前重点处理或咨询律师。');
  if (missingTerms.length)
    lines.push(`可能缺少要素：${missingTerms.join('、')}。`);
  if (backend.used) {
    if (backend.results.length)
      lines.push(
        `已联网核对官方《国家法律法规数据库》，关联到 ${backend.results.length} 条权威法规链接。`
      );
    else if (backend.errors.length)
      lines.push(
        '联网核对官方法规库失败（可能网络受限或官网改版），本次依据本地精选法条库给出依据，请以官方库为准。'
      );
  }
  return lines.join('\n');
}

function sortBySeverity(findings) {
  const order = { high: 0, medium: 1, low: 2 };
  return [...findings].sort(
    (a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9)
  );
}

function excerpt(t, n = 120) {
  const s = (t || '').replace(/\s+/g, ' ').trim();
  return s.length > n ? s.slice(0, n) + '…' : s;
}

module.exports = { reviewContract, searchLocalStatutes };
