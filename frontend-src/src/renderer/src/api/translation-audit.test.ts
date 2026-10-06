import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mapTranslationAudit, translationAuditPath } from './translation-audit.ts'

test('mapTranslationAudit keeps the counts and the suggestions', () => {
  const audit = mapTranslationAudit({
    ok: true,
    enabled: true,
    audited: 12,
    flagged: 3,
    suggestions: {
      protected_names: [{ source: 'ペコラ', target: 'ぺこら', count: 2 }],
      catchphrases: [{ source: 'peko', target: 'ぺこ', count: 4 }],
    },
    suspicious: [{ original: '句', translated: '文', issues: [] }],
  })
  assert.deepEqual(audit, {
    enabled: true,
    audited: 12,
    flagged: 3,
    suggestions: {
      protected_names: [{ source: 'ペコラ', target: 'ぺこら', count: 2 }],
      catchphrases: [{ source: 'peko', target: 'ぺこ', count: 4 }],
    },
  })
})

test('mapTranslationAudit drops malformed rows instead of crashing the page', () => {
  const audit = mapTranslationAudit({
    suggestions: { protected_names: [null, { source: 1, target: 'x' }, 'x'], catchphrases: 'no' },
  })
  assert.deepEqual(audit, {
    enabled: false,
    audited: 0,
    flagged: 0,
    suggestions: { protected_names: [], catchphrases: [] },
  })
  assert.equal(mapTranslationAudit(null).audited, 0)
})

test('translationAuditPath encodes the character file name', () => {
  assert.equal(
    translationAuditPath('我的 角色.yaml'),
    '/api/characters/%E6%88%91%E7%9A%84%20%E8%A7%92%E8%89%B2.yaml/translation-audit',
  )
})
