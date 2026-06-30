'use strict';

const $ = (id) => document.getElementById(id);

async function loadHealth() {
  try {
    const r = await fetch('/api/health').then((x) => x.json());
    const parts = [];
    parts.push(
      `法规库: ${r.backendDefault ? '<b>在线核对</b>' : '<span class="off">关闭</span>'}`
    );
    parts.push(
      r.aiEnabled
        ? `AI: <b>已启用</b> <span class="off">${r.aiModel || ''}</span>`
        : 'AI: <span class="off">未配置</span>'
    );
    $('status').innerHTML = parts.join('');
    $('useBackend').checked = r.backendDefault;
    if (!r.aiEnabled) {
      $('useAI').disabled = true;
      $('aiHint').textContent = '（需在服务器设置 ANTHROPIC_API_KEY）';
    } else {
      $('aiHint').textContent = '（基于真实法条做检索增强解读）';
    }
  } catch (e) {
    $('status').innerHTML = '<span class="off">未连接到服务器</span>';
  }
}

const SEVTEXT = { high: '高风险', medium: '中风险', low: '提示' };

async function runReview() {
  const text = $('contract').value.trim();
  if (!text) {
    alert('请先粘贴合同文本');
    return;
  }
  const btn = $('reviewBtn');
  btn.disabled = true;
  btn.textContent = '审查中…';
  $('report').innerHTML =
    '<div class="empty"><span class="spin"></span> 正在分条、跑规则、核对真实法条…</div>';

  try {
    const res = await fetch('/api/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        useBackend: $('useBackend').checked,
        useAI: $('useAI').checked,
      }),
    }).then((x) => x.json());

    if (!res.ok) {
      $('report').innerHTML = `<div class="empty">出错：${res.error || '未知错误'}</div>`;
      return;
    }
    renderReport(res.review, res.ai);
  } catch (e) {
    $('report').innerHTML = `<div class="empty">请求失败：${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '开始审查';
  }
}

function esc(s) {
  return (s || '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

function renderReport(review, ai) {
  const el = $('report');
  let html = '';

  html += `<div class="summary">${esc(review.summary)}</div>`;

  if (ai && ai.ok && ai.text) {
    html += `<h3 style="margin:6px 0">🤖 AI 解读 <span class="muted">(${esc(ai.model || '')}·辅助参考)</span></h3>`;
    html += `<div class="ai">${esc(ai.text)}</div>`;
  } else if (ai && !ai.ok) {
    html += `<div class="muted" style="margin-bottom:10px">AI 解读未运行：${esc(ai.error)}</div>`;
  }

  if (!review.findings.length) {
    html += '<div class="empty">未命中内置风险规则。注意：未命中 ≠ 没有风险，建议仍由律师把关。</div>';
  }

  for (const f of review.findings) {
    html += `<div class="finding">
      <div class="top">
        <span class="sev ${f.severity}">${SEVTEXT[f.severity] || f.severity}</span>
        <span class="fname">${esc(f.name)}</span>
        <span class="clause">· ${esc(f.clauseLabel || ('条款' + f.clauseIndex))}</span>
      </div>`;
    if (f.clauseExcerpt) html += `<div class="excerpt">${esc(f.clauseExcerpt)}</div>`;
    html += `<div class="row"><b>为什么要注意：</b>${esc(f.explain)}</div>`;
    html += `<div class="row"><b>建议怎么做：</b>${esc(f.suggest)}</div>`;
    if (f.statutes && f.statutes.length) {
      html += '<div class="statute">';
      for (const s of f.statutes) {
        html += `<div class="s"><span class="art">《${esc(s.law)}》${esc(s.article)}</span> ${esc(s.title)}<br>${esc(s.text)}</div>`;
      }
      html += '</div>';
    }
    html += '</div>';
  }

  // 官方法规库核对结果
  const be = review.backend || {};
  if (be.used) {
    html += '<div class="backend-box laws">';
    if (be.results && be.results.length) {
      html += '<b>📚 官方法规库核对（国家法律法规数据库，权威链接）：</b><br>';
      for (const r of be.results.slice(0, 12)) {
        html += `• <a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(r.title)}</a> <span class="muted">[${esc(r.statusText || '状态未知')}] ${esc(r.publishDate || '')}</span><br>`;
      }
    } else {
      html += `<span class="muted">官方法规库联网核对未返回结果${be.errors && be.errors.length ? '（' + esc(be.errors[0].error) + '）' : ''}。本次依据本地精选法条库，请以官方库为准。</span>`;
    }
    html += '</div>';
  }

  html += `<div class="disclaimer">${esc(review.disclaimer)}</div>`;

  el.innerHTML = html;
}

function loadSample() {
  $('contract').value = `第一条 乙方应于本合同签订之日起向甲方支付定金人民币80000元，作为履约担保。如乙方违约，定金不予退还。
第二条 乙方逾期付款的，每日按欠款金额的1%支付违约金。
第三条 甲方有权随时单方解除本合同并调整服务内容，乙方不得提出异议，由此产生的费用由乙方承担。
第四条 本合同最终解释权归甲方所有，甲方对因服务产生的任何损失概不负责。
第五条 本合同到期后自动续约一年，续约价格甲方有权另行调整。
第六条 因本合同产生的争议，由甲方所在地仲裁委员会仲裁解决。`;
}

loadHealth();
