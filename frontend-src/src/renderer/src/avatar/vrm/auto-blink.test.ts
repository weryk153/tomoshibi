import assert from "node:assert/strict";
import test from "node:test";
import { AutoBlink } from "./auto-blink.ts";

test("等待期眼睛全開，之後閉眼再張開", () => {
  const b = new AutoBlink(() => 0); // rng=0 → 等 2 秒
  assert.equal(b.update(1.0), 0);
  assert.equal(b.update(0.9), 0);
  const closing = b.update(0.15); // 跨過 2 秒，進入閉眼
  assert.ok(closing > 0);
  let opened = false;
  for (let i = 0; i < 20; i++) {
    if (b.update(0.02) === 0) { opened = true; break; }
  }
  assert.ok(opened, "0.4 秒內應該張開");
});

test("rng=1 等 6 秒", () => {
  const b = new AutoBlink(() => 1);
  assert.equal(b.update(5.9), 0);
  assert.ok(b.update(0.2) > 0);
});
