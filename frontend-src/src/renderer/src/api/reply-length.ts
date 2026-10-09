// 她每次回幾句（全部角色共用）。後端見 src/open_llm_vtuber/reply_length.py 與
// player_route.py 的 GET/POST /api/reply-length。每一輪才讀，存了馬上生效。

import { apiGet, apiPost, type ApiResult } from './http.ts'

export const REPLY_LENGTHS = ['short', 'medium', 'free'] as const
export type ReplyLength = typeof REPLY_LENGTHS[number]

export const fetchReplyLength = async (baseUrl: string): Promise<ApiResult<ReplyLength>> => {
  const result = await apiGet<{ length: ReplyLength }>(baseUrl, '/api/reply-length')
  return result.ok ? { ok: true, data: result.data.length } : result
}

export const saveReplyLength = (baseUrl: string, length: ReplyLength) =>
  apiPost<{ ok: boolean, length: ReplyLength }>(baseUrl, '/api/reply-length', { length })
