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
