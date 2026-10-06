import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { footerExtra } from './footer-extra.ts';

test('a one-line footer fills its slot exactly: no extra', () => {
  assert.equal(footerExtra({ panelHeight: 92, slotHeight: 92, collapsed: false }), 0);
});

test('a grown input pushes the panel above its slot by the difference', () => {
  assert.equal(footerExtra({ panelHeight: 136, slotHeight: 92, collapsed: false }), 44);
});

test('collapsed footer keeps the subtitle where it was', () => {
  // 收合時面板比 28px 的格子高（多出來的往下藏在畫面外），那不是往上長。
  assert.equal(footerExtra({ panelHeight: 92, slotHeight: 28, collapsed: true }), 0);
  assert.equal(footerExtra({ panelHeight: 136, slotHeight: 28, collapsed: true }), 0);
});

test('never negative, and sub-pixel noise rounds away', () => {
  assert.equal(footerExtra({ panelHeight: 90, slotHeight: 92, collapsed: false }), 0);
  assert.equal(footerExtra({ panelHeight: 92.4, slotHeight: 92, collapsed: false }), 0);
  assert.equal(footerExtra({ panelHeight: 114.6, slotHeight: 92, collapsed: false }), 23);
});
