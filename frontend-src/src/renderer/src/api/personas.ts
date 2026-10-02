import {
  apiGet, apiPost, apiPut, buildUrl, normalizeError, type ApiResult,
} from './http.ts';

export interface PersonaRecord {
  id: string
  name: string
  prompt: string
}

export interface PersonaListResponse {
  personas: PersonaRecord[]
  active_persona_id: string | null
}

export interface PersonaDraft {
  name: string
  prompt: string
  id?: string
}

export const fetchPersonas = (
  baseUrl: string,
  confUid: string,
): Promise<ApiResult<PersonaListResponse>> => apiGet<PersonaListResponse>(
  baseUrl,
  `/api/personas?conf_uid=${encodeURIComponent(confUid)}`,
);

export const createPersona = (
  baseUrl: string,
  body: PersonaDraft,
): Promise<ApiResult<{ persona: PersonaRecord }>> => apiPost(
  baseUrl,
  '/api/personas',
  body,
);

export const updatePersona = (
  baseUrl: string,
  personaId: string,
  body: PersonaDraft,
): Promise<ApiResult<{ persona: PersonaRecord }>> => apiPut(
  baseUrl,
  `/api/personas/${encodeURIComponent(personaId)}`,
  body,
);

export async function deletePersona(
  baseUrl: string,
  personaId: string,
): Promise<ApiResult<unknown>> {
  try {
    const response = await fetch(
      buildUrl(baseUrl, `/api/personas/${encodeURIComponent(personaId)}`),
      { method: 'DELETE' },
    );
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // normalizeError supplies a useful HTTP fallback below.
    }
    if (!response.ok) return { ok: false, error: normalizeError(body, response.status) };
    return { ok: true, data: body };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : '網路錯誤',
    };
  }
}

export const activePersonaBody = (
  confUid: string,
  personaId: string | null,
): { conf_uid: string; persona_id: string | null } => ({ conf_uid: confUid, persona_id: personaId })

// 替「不是正在用的」角色選人設版本：存起來，切換到她時生效。正在用的角色走
// WebSocket 的 switch-persona（立刻換），不走這裡。
export const setActivePersona = (
  baseUrl: string,
  confUid: string,
  personaId: string | null,
): Promise<ApiResult<{ ok: boolean; active_persona_id: string | null }>> => apiPut(
  baseUrl,
  '/api/personas/active',
  activePersonaBody(confUid, personaId),
)
