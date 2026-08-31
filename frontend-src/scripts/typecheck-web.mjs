// Typecheck the renderer, ignoring the vendored Live2D Cubism Web SDK.
//
// `src/renderer/WebSDK/` is Live2D's own sample source, vendored unmodified from
// CubismWebSamples. It does not compile clean under this project's `strict`
// settings (~580 possibly-null and uninitialised-property errors), and patching
// it would mean maintaining a fork of someone else's SDK for no runtime gain —
// the bundler never typechecks, so those errors have never affected the build.
//
// tsc has no per-directory strictness, and it typechecks the SDK regardless of
// `include`/`exclude` because our own files import it. So we run the real check,
// print everything it says, and fail only on errors in code we actually own.

import { spawnSync } from 'node:child_process';

const VENDORED = 'src/renderer/WebSDK/';

const result = spawnSync(
  'tsc',
  ['--noEmit', '-p', 'tsconfig.web.json', '--composite', 'false', '--pretty', 'false'],
  { encoding: 'utf-8', shell: true },
);

const lines = (result.stdout || '').split('\n').filter((line) => line.trim() !== '');
const errors = lines.filter((line) => /error TS\d+:/.test(line));
const ours = errors.filter((line) => !line.startsWith(VENDORED));
const vendored = errors.length - ours.length;

for (const line of ours) console.log(line);

if (result.stderr) process.stderr.write(result.stderr);

if (vendored > 0) {
  console.log(
    `\n${vendored} error(s) in the vendored Live2D SDK (${VENDORED}) ignored — ` +
      'see the comment at the top of scripts/typecheck-web.mjs.',
  );
}

if (ours.length > 0) {
  console.log(`\n${ours.length} error(s) in project code.`);
  process.exit(1);
}

console.log('No type errors in project code.');
