// 翻譯審核的建議（角色頁「語言」區）。後端見 character_route.py 的
// GET  /api/characters/{filename}/translation-audit
// POST /api/characters/{filename}/translation-audit/accept
// 後端只回出現夠多次、角色設定裡還沒有的建議；加進去之後就不再列出。

import { apiGet, apiPost, type ApiResult } from './http.ts'

export type SuggestionKind = 'protected_names' | 'catchphrases'

export interface AuditSuggestion {
  // 名字：source 是譯句裡的錯誤寫法、target 是正確寫法。
  // 口頭禪：source 是原句裡的寫法、target 是語音語言要用的寫法。
  source: string
  target: string
  count: number
}

export interface TranslationAudit {
  enabled: boolean
  audited: number
  flagged: number
  suggestions: Record<SuggestionKind, AuditSuggestion[]>
}

export function translationAuditPath(filename: string): string {
  return `/api/characters/${encodeURIComponent(filename)}/translation-audit`
}

const asNumber = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0

function asSuggestions(value: unknown): AuditSuggestion[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((row) => {
    if (!row || typeof row !== 'object') return []
    const { source, target, count } = row as Record<string, unknown>
    if (typeof source !== 'string' || typeof target !== 'string') return []
    return [{ source, target, count: asNumber(count) }]
  })
}

export function mapTranslationAudit(data: unknown): TranslationAudit {
  const body = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
  const suggestions = (
    body.suggestions && typeof body.suggestions === 'object' ? body.suggestions : {}
  ) as Record<string, unknown>
  return {
    enabled: body.enabled === true,
    audited: asNumber(body.audited),
    flagged: asNumber(body.flagged),
    suggestions: {
      protected_names: asSuggestions(suggestions.protected_names),
      catchphrases: asSuggestions(suggestions.catchphrases),
    },
  }
}

export async function fetchTranslationAudit(
  baseUrl: string,
  filename: string,
): Promise<ApiResult<TranslationAudit>> {
  const result = await apiGet<unknown>(baseUrl, translationAuditPath(filename))
  return result.ok ? { ok: true, data: mapTranslationAudit(result.data) } : result
}

export async function acceptTranslationAuditSuggestion(
  baseUrl: string,
  filename: string,
  kind: SuggestionKind,
  suggestion: Pick<AuditSuggestion, 'source' | 'target'>,
): Promise<ApiResult<TranslationAudit>> {
  const result = await apiPost<unknown>(baseUrl, `${translationAuditPath(filename)}/accept`, {
    kind,
    source: suggestion.source,
    target: suggestion.target,
  })
  return result.ok ? { ok: true, data: mapTranslationAudit(result.data) } : result
}
