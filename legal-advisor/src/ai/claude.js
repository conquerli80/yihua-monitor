'use strict';

/**
 * 可选的 AI 叙述分析层（基于 Claude API）。
 *
 * - 完全可选：未设置 ANTHROPIC_API_KEY 时，整个工具仍可用（规则体检 + 真实法条核对）。
 * - 关键设计：把【已检索到的真实法条/官方结果】作为材料喂给模型，让 AI 在“有据可依”的
 *   前提下做通俗解读，而不是凭空发挥（即 RAG —— 检索增强生成）。
 * - 模型默认用 claude-sonnet-4-6（质量/成本均衡）。可用环境变量 CLAUDE_MODEL 覆盖。
 *
 * ⚠️ AI 输出同样是辅助参考，不构成法律意见。
 */

const https = require('https');

const DEFAULT_MODEL = process.env.CLAUDE_MODEL || 'claude-sonnet-4-6';

function isEnabled() {
  return !!process.env.ANTHROPIC_API_KEY;
}

function callAnthropic(payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const req = https.request(
      {
        method: 'POST',
        hostname: 'api.anthropic.com',
        path: '/v1/messages',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': process.env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01',
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: 60000,
      },
      (res) => {
        let data = '';
        res.setEncoding('utf8');
        res.on('data', (c) => (data += c));
        res.on('end', () => {
          try {
            const json = JSON.parse(data);
            if (res.statusCode !== 200) {
              return reject(
                new Error(
                  `Anthropic API ${res.statusCode}: ${json.error ? json.error.message : data}`
                )
              );
            }
            resolve(json);
          } catch (e) {
            reject(new Error('解析 Anthropic 返回失败: ' + e.message));
          }
        });
      }
    );
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error('Anthropic API 超时')));
    req.write(body);
    req.end();
  });
}

/**
 * @param {string} contractText
 * @param {object} review reviewContract() 的结果（含 findings 与 backend 真实法条）
 * @returns {Promise<{ok:boolean, text?:string, model?:string, error?:string}>}
 */
async function analyze(contractText, review) {
  if (!isEnabled()) {
    return { ok: false, error: '未设置 ANTHROPIC_API_KEY，已跳过 AI 分析（不影响规则与法条核对）。' };
  }

  const grounding = buildGrounding(review);
  const system = [
    '你是一名严谨、谨慎的中文合同审查助手，服务对象是没有法律背景、暂时请不起律师的普通人。',
    '原则：',
    '1) 只能基于【提供的真实法条材料】和合同文本进行分析；材料里没有的法条不要编造条号。',
    '2) 用通俗中文解释风险，并给出“签署前可以怎么做”的具体建议。',
    '3) 凡引用法条，必须写明法律名称与条号，并说明是“参考”。',
    '4) 明确告知：这是辅助参考，不构成法律意见，重大事项需咨询执业律师或拨打 12348。',
    '5) 不要给出过度自信的“一定/绝对”结论；不确定就说明不确定。',
  ].join('\n');

  const user = [
    '【合同文本】\n' + truncate(contractText, 12000),
    '\n【规则体检已发现的关注点（结构化）】\n' + summarizeFindings(review),
    '\n【已核验的真实法条材料（请基于这些作答，勿超出）】\n' + grounding,
    '\n请输出：①整体风险概述；②逐个关注点的通俗解读+建议（标注依据法条）；③给普通人的“签署前清单”。',
  ].join('\n');

  try {
    const json = await callAnthropic({
      model: DEFAULT_MODEL,
      max_tokens: 2000,
      system,
      messages: [{ role: 'user', content: user }],
    });
    const text = (json.content || [])
      .filter((b) => b.type === 'text')
      .map((b) => b.text)
      .join('\n')
      .trim();
    return { ok: true, text, model: json.model || DEFAULT_MODEL };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

function buildGrounding(review) {
  const lines = [];
  const statuteSet = new Map();
  for (const f of review.findings || []) {
    for (const s of f.statutes || []) {
      if (!statuteSet.has(s.code))
        statuteSet.set(s.code, `《${s.law}》${s.article}（${s.title}）：${s.text}`);
    }
  }
  lines.push('— 相关法条（本地精选库）—');
  for (const v of statuteSet.values()) lines.push('• ' + v);

  const be = review.backend || {};
  if (be.results && be.results.length) {
    lines.push('\n— 官方法规库核对结果（现行性/官方链接）—');
    be.results.slice(0, 10).forEach((r) =>
      lines.push(`• ${r.title} [${r.statusText || '状态未知'}] ${r.link}`)
    );
  }
  return lines.join('\n') || '（无）';
}

function summarizeFindings(review) {
  return (review.findings || [])
    .map(
      (f) =>
        `- [${sevText(f.severity)}] ${f.name}（${f.clauseLabel || '条款' + f.clauseIndex}）：${f.clauseExcerpt}`
    )
    .join('\n');
}

function sevText(s) {
  return s === 'high' ? '高' : s === 'medium' ? '中' : '提示';
}

function truncate(s, n) {
  s = s || '';
  return s.length > n ? s.slice(0, n) + '…（已截断）' : s;
}

module.exports = { analyze, isEnabled, DEFAULT_MODEL };
