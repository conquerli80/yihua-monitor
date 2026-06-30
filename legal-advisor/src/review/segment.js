'use strict';

/**
 * 合同文本分条。尽量把整段合同切成可逐条审查的「条款」。
 * 识别：第X条 / 一、二、 / 1. 2. / （一）（二） / 1.1 / 空行段落 等常见编号。
 */
function segmentContract(text) {
  if (!text || !text.trim()) return [];
  const normalized = text.replace(/\r\n?/g, '\n');

  // 优先按「第X条」切分（最常见的正式合同结构）
  const articleRe = /(第\s*[零〇一二三四五六七八九十百千0-9]+\s*条)/g;
  if (articleRe.test(normalized)) {
    const parts = normalized.split(/(?=第\s*[零〇一二三四五六七八九十百千0-9]+\s*条)/);
    return parts
      .map((p, i) => ({ index: i, label: detectLabel(p), text: p.trim() }))
      .filter((c) => c.text.length > 0);
  }

  // 否则按行/段落切，过滤过短的行
  const lines = normalized
    .split(/\n{1,}/)
    .map((l) => l.trim())
    .filter((l) => l.length >= 4);

  return lines.map((l, i) => ({ index: i, label: detectLabel(l), text: l }));
}

function detectLabel(s) {
  const m =
    s.match(/^第\s*[零〇一二三四五六七八九十百千0-9]+\s*条/) ||
    s.match(/^[（(]\s*[一二三四五六七八九十0-9]+\s*[)）]/) ||
    s.match(/^[一二三四五六七八九十]+、/) ||
    s.match(/^\d+(\.\d+)*[、.．]/);
  return m ? m[0].trim() : '';
}

module.exports = { segmentContract };
