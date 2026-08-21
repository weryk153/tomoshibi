import { test } from 'node:test'
import assert from 'node:assert/strict'
import net from 'node:net'
import http from 'node:http'
import { buildUrl, normalizeError, apiPost, apiPut } from './http.ts'

test('buildUrl 串接 baseUrl 與 path，去除重複斜線', () => {
  assert.equal(buildUrl('http://127.0.0.1:12393', '/api/llm-config'), 'http://127.0.0.1:12393/api/llm-config')
  assert.equal(buildUrl('http://127.0.0.1:12393/', '/api/llm-config'), 'http://127.0.0.1:12393/api/llm-config')
  assert.equal(buildUrl('http://127.0.0.1:12393', 'api/llm-config'), 'http://127.0.0.1:12393/api/llm-config')
})

test('normalizeError 從後端的 {ok:false,error} 取出訊息', () => {
  assert.equal(normalizeError({ ok: false, error: '缺少模型名稱' }, 400), '缺少模型名稱')
})

test('normalizeError 從後端的 {error} 取出訊息（GET 端點用這個形狀）', () => {
  assert.equal(normalizeError({ error: 'could not read config' }, 500), 'could not read config')
})

test('normalizeError 在沒有可用訊息時回傳含狀態碼的字串，不回傳 undefined', () => {
  const msg = normalizeError({}, 502)
  assert.match(msg, /502/)
})

test('apiPost 在連線被拒絕時回傳 ok:false（而非拋出例外）', async () => {
  // 指向一個保證會被拒絕連線的位址（沒有服務在監聽）。
  // 注意：這條路徑是 TypeError: fetch failed（ECONNREFUSED），幾乎立即發生，
  // 根本走不到逾時／AbortError 分支——這不是在測逾時，只是在測「不拋例外」。
  const r = await apiPost('http://127.0.0.1:1', '/api/x', {}, 1000)
  assert.equal(r.ok, false)
  if (!r.ok) assert.ok(r.error.length > 0)
})

test('apiPost 在逾時時回傳 ok:false，且錯誤訊息是逾時訊息（不是泛用網路錯誤）', async () => {
  // 用一個真正會「掛起」的連線來逼出 AbortError 分支：伺服器接受 TCP 連線，
  // 但永遠不回應 HTTP，逼 fetch 一路等到我們設定的逾時觸發 AbortController。
  // 若只斷言 ok === false，刪掉 http.ts 的 AbortError 分支測試依然會過——
  // 所以這裡額外斷言錯誤訊息帶有「逾時」字樣。
  const sockets: net.Socket[] = []
  const server = net.createServer((socket) => {
    sockets.push(socket)
    // 刻意什麼都不做：不回應、不關閉連線。
  })
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', () => resolve()))
  const address = server.address()
  if (address === null || typeof address === 'string') {
    throw new Error('unexpected server address: ' + String(address))
  }
  try {
    const r = await apiPost(`http://127.0.0.1:${address.port}`, '/api/x', {}, 50)
    assert.equal(r.ok, false)
    if (!r.ok) assert.match(r.error, /逾時/)
  } finally {
    for (const socket of sockets) socket.destroy()
    await new Promise<void>((resolve) => server.close(() => resolve()))
  }
})

test('apiPut 實際送出 HTTP method PUT 與 JSON body——不是悄悄退回 GET/POST', async () => {
  // apiPut 是新加的方法；request() 內部用 method === 'POST' || method === 'PUT'
  // 才會帶 body/header，若條件寫錯（例如漏了 PUT）body 就會悄悄消失，後端會收到
  // 空物件而不是報錯，是最容易被忽略的迴歸。所以這裡起一個真的 HTTP 伺服器，
  // 直接斷言收到的 method 與 body，而不是只看 apiPut 有沒有 resolve。
  let receivedMethod = ''
  let receivedBody = ''
  const server = http.createServer((req, res) => {
    receivedMethod = req.method ?? ''
    const chunks: Buffer[] = []
    req.on('data', (c) => chunks.push(c))
    req.on('end', () => {
      receivedBody = Buffer.concat(chunks).toString('utf8')
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ ok: true }))
    })
  })
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', () => resolve()))
  const address = server.address()
  if (address === null || typeof address === 'string') {
    throw new Error('unexpected server address: ' + String(address))
  }
  try {
    const r = await apiPut(`http://127.0.0.1:${address.port}`, '/api/characters/mao.yaml', {
      voice: '',
    })
    assert.equal(receivedMethod, 'PUT')
    assert.equal(receivedBody, JSON.stringify({ voice: '' }))
    assert.equal(r.ok, true)
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()))
  }
})

test('apiPut 在連線被拒絕時回傳 ok:false（而非拋出例外）', async () => {
  const r = await apiPut('http://127.0.0.1:1', '/api/x', {}, 1000)
  assert.equal(r.ok, false)
  if (!r.ok) assert.ok(r.error.length > 0)
})
