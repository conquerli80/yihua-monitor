'use strict';

/**
 * 法律后端适配器注册表 —— 系统的「插槽」中枢。
 *
 * 设计目标：合同审查引擎只依赖统一的 search(keyword) 接口，不关心数据来自哪个库。
 * 想新增数据源（免费或付费），只需在这里 register() 一个实现了 search() 的适配器即可。
 *
 * 每个适配器需暴露：
 *   { name, label, authoritative, free, enabled?, search(keyword, opts) }
 *   search 返回 { ok:boolean, items:Array, error?:string }
 */

const nationalLawDb = require('./nationalLawDb');
const paidLibraryStub = require('./paidLibrary.stub');

const adapters = [];

function register(adapter) {
  if (!adapter || typeof adapter.search !== 'function') {
    throw new Error('适配器必须实现 search() 方法');
  }
  adapters.push(adapter);
}

// 默认注册：官方免费法规库（启用）+ 付费库模板（默认不启用）
register(nationalLawDb);
register(paidLibraryStub);

function listAdapters() {
  return adapters.map((a) => ({
    name: a.name,
    label: a.label,
    authoritative: !!a.authoritative,
    free: !!a.free,
    enabled: a.enabled !== false,
  }));
}

/**
 * 并行查询所有【已启用】适配器，聚合结果。
 * 任一适配器失败不影响其它适配器；失败信息会回传到 errors。
 */
async function searchAll(keyword, opts = {}) {
  const active = adapters.filter((a) => a.enabled !== false);
  const settled = await Promise.allSettled(
    active.map((a) => a.search(keyword, opts))
  );
  const results = [];
  const errors = [];
  settled.forEach((s, i) => {
    const a = active[i];
    if (s.status === 'fulfilled' && s.value && s.value.ok) {
      results.push({ adapter: a.name, label: a.label, items: s.value.items || [] });
    } else {
      const msg =
        s.status === 'rejected' ? s.reason && s.reason.message : s.value && s.value.error;
      errors.push({ adapter: a.name, label: a.label, error: msg || '未知错误' });
    }
  });
  return { results, errors };
}

module.exports = { register, listAdapters, searchAll, adapters };
