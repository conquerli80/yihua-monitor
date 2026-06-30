'use strict';

/**
 * 合同审查助手 —— 本地服务器（零依赖，仅用 Node 内置模块）。
 *
 * 运行：
 *   node server.js            # 默认 http://localhost:8787
 *   PORT=9000 node server.js
 *
 * 可选环境变量：
 *   ANTHROPIC_API_KEY   设置后启用 AI 叙述分析（基于真实法条做检索增强解读）
 *   CLAUDE_MODEL        覆盖默认模型（默认 claude-sonnet-4-6）
 *   DISABLE_BACKEND=1   关闭联网核对官方法规库（仅用本地精选法条）
 *
 * 接口：
 *   GET  /                     前端页面
 *   GET  /api/health           健康检查 + 已启用的法律后端列表
 *   POST /api/review           合同审查（body: { text, useAI?:bool, useBackend?:bool }）
 *   GET  /api/laws?q=合同      直接检索官方法规库（透传适配器，规避浏览器跨域）
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const { reviewContract } = require('./src/review/engine');
const registry = require('./src/adapters/registry');
const claude = require('./src/ai/claude');

const PORT = process.env.PORT || 8787;
const PUBLIC_DIR = path.join(__dirname, 'public');
const BACKEND_DEFAULT = process.env.DISABLE_BACKEND !== '1';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

function sendJSON(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

function readBody(req, limit = 2 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    let data = '';
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > limit) {
        reject(new Error('请求体过大'));
        req.destroy();
        return;
      }
      data += c;
    });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

function serveStatic(req, res) {
  let urlPath = decodeURIComponent(req.url.split('?')[0]);
  if (urlPath === '/') urlPath = '/index.html';
  const filePath = path.join(PUBLIC_DIR, path.normalize(urlPath));
  if (!filePath.startsWith(PUBLIC_DIR)) {
    res.writeHead(403);
    return res.end('Forbidden');
  }
  fs.readFile(filePath, (err, content) => {
    if (err) {
      res.writeHead(404);
      return res.end('Not Found');
    }
    const ext = path.extname(filePath);
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
    res.end(content);
  });
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);

    if (req.method === 'GET' && url.pathname === '/api/health') {
      return sendJSON(res, 200, {
        ok: true,
        backendDefault: BACKEND_DEFAULT,
        aiEnabled: claude.isEnabled(),
        aiModel: claude.isEnabled() ? claude.DEFAULT_MODEL : null,
        adapters: registry.listAdapters(),
      });
    }

    if (req.method === 'GET' && url.pathname === '/api/laws') {
      const q = url.searchParams.get('q') || '';
      if (!q.trim()) return sendJSON(res, 400, { ok: false, error: '缺少查询参数 q' });
      const r = await registry.searchAll(q, { size: 6 });
      return sendJSON(res, 200, { ok: true, query: q, ...r });
    }

    if (req.method === 'POST' && url.pathname === '/api/review') {
      const raw = await readBody(req);
      let payload;
      try {
        payload = JSON.parse(raw || '{}');
      } catch (_e) {
        return sendJSON(res, 400, { ok: false, error: '请求体不是合法 JSON' });
      }
      const text = (payload.text || '').toString();
      if (!text.trim())
        return sendJSON(res, 400, { ok: false, error: '请粘贴合同文本' });

      const useBackend =
        payload.useBackend === undefined ? BACKEND_DEFAULT : !!payload.useBackend;
      const review = await reviewContract(text, { useBackend });

      let ai = null;
      if (payload.useAI && claude.isEnabled()) {
        ai = await claude.analyze(text, review);
      } else if (payload.useAI && !claude.isEnabled()) {
        ai = { ok: false, error: '服务器未配置 ANTHROPIC_API_KEY，无法运行 AI 分析。' };
      }

      return sendJSON(res, 200, { ok: true, review, ai });
    }

    if (req.method === 'GET') return serveStatic(req, res);

    sendJSON(res, 404, { ok: false, error: 'Not Found' });
  } catch (e) {
    sendJSON(res, 500, { ok: false, error: e.message });
  }
});

server.listen(PORT, () => {
  console.log('────────────────────────────────────────────────');
  console.log('  合同审查助手 已启动');
  console.log('  打开浏览器访问: http://localhost:' + PORT);
  console.log('  法律后端: ' + registry.listAdapters().map((a) => `${a.label}${a.enabled ? '' : '(未启用)'}`).join(' | '));
  console.log('  联网核对官方法规库: ' + (BACKEND_DEFAULT ? '开启' : '关闭'));
  console.log('  AI 分析: ' + (claude.isEnabled() ? '已启用(' + claude.DEFAULT_MODEL + ')' : '未启用(可选)'));
  console.log('  提示: 本工具为辅助参考，不构成法律意见。重大事项请咨询律师/12348。');
  console.log('────────────────────────────────────────────────');
});
