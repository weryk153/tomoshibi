import { test } from 'node:test'
import assert from 'node:assert/strict'
import { validateBackgroundFile } from './background.ts'

function fakeFile(name: string, type: string, size: number): File {
  return { name, type, size } as File
}

test('接受 JPEG', () => {
  assert.equal(validateBackgroundFile(fakeFile('a.jpg', 'image/jpeg', 1024)), null)
})

test('接受 PNG 與 GIF', () => {
  assert.equal(validateBackgroundFile(fakeFile('a.png', 'image/png', 1024)), null)
  assert.equal(validateBackgroundFile(fakeFile('a.gif', 'image/gif', 1024)), null)
})

test('拒絕非圖片型別，回傳 notImage', () => {
  assert.equal(validateBackgroundFile(fakeFile('a.pdf', 'application/pdf', 1024)), 'notImage')
})

test('拒絕不在允許清單內的圖片型別（例如 webp）', () => {
  assert.equal(validateBackgroundFile(fakeFile('a.webp', 'image/webp', 1024)), 'notImage')
})

// 12 * 1024 * 1024 是寫死的字面值,不是 BACKGROUND_MAX_BYTES + 1——用常數自己去
// 建構樣本會讓測試自我指涉,改掉常數測試照樣全過。已跟 character_route.py 的
// BG_MAX_BYTES 核對過,後端目前確實是 12 * 1024 * 1024。
test('拒絕過大的檔案，回傳 tooLarge', () => {
  assert.equal(
    validateBackgroundFile(fakeFile('a.jpg', 'image/jpeg', 12 * 1024 * 1024 + 1)),
    'tooLarge',
  )
})

test('剛好等於上限的檔案要被接受', () => {
  assert.equal(validateBackgroundFile(fakeFile('a.jpg', 'image/jpeg', 12 * 1024 * 1024)), null)
})

test('型別檢查先於大小檢查', () => {
  // 一個又大又不是圖片的檔案，必須回報 notImage 而不是 tooLarge——
  // 先講「這不是圖片」比先講「太大了」更接近使用者的實際問題。
  assert.equal(
    validateBackgroundFile(fakeFile('a.pdf', 'application/pdf', 99 * 1024 * 1024)),
    'notImage',
  )
})

// file.type 在某些環境（尤其 Electron／OS 無法辨識 MIME 時）會是空字串——
// 這時應該退回用副檔名判斷，不能一律回報 notImage，否則一張合法的
// photo.jpg 會在送出前就被靜默擋下，使用者無法繼續。
test('MIME 為空字串時，副檔名合法就接受', () => {
  assert.equal(validateBackgroundFile(fakeFile('photo.jpg', '', 1024)), null)
  assert.equal(validateBackgroundFile(fakeFile('photo.jpeg', '', 1024)), null)
  assert.equal(validateBackgroundFile(fakeFile('photo.png', '', 1024)), null)
  assert.equal(validateBackgroundFile(fakeFile('photo.gif', '', 1024)), null)
})

test('MIME 為空字串且副檔名也不合法時，回傳 notImage', () => {
  assert.equal(validateBackgroundFile(fakeFile('photo.pdf', '', 1024)), 'notImage')
  assert.equal(validateBackgroundFile(fakeFile('photo', '', 1024)), 'notImage')
})

// 瀏覽器／OS 給出無法辨識的 MIME（不是空字串，但也不在允許清單內）時，
// 一樣要退回用副檔名判斷——跟空字串是同一種「MIME 判斷不出來」的情況。
test('MIME 無法辨識（非空但不在允許清單）時，副檔名合法就接受', () => {
  assert.equal(validateBackgroundFile(fakeFile('photo.png', 'application/octet-stream', 1024)), null)
})

// 副檔名比對必須大小寫不敏感，跟後端 character_route.py 的
// up_ext = os.path.splitext(up_name)[1].lower() 一致。
test('副檔名回退比對大小寫不敏感', () => {
  assert.equal(validateBackgroundFile(fakeFile('PHOTO.JPG', '', 1024)), null)
  assert.equal(validateBackgroundFile(fakeFile('Photo.PnG', '', 1024)), null)
})

// 副檔名回退仍然要跑大小檢查，不能因為走了 fallback 分支就跳過。
test('MIME 為空、副檔名合法但檔案過大，回傳 tooLarge', () => {
  assert.equal(
    validateBackgroundFile(fakeFile('photo.jpg', '', 12 * 1024 * 1024 + 1)),
    'tooLarge',
  )
})

// 刻意保留的另一個方向：.jfif 檔案帶著 image/jpeg 的 MIME，前端目前會接受
// （MIME 檢查直接放行，不會走副檔名回退），送到後端後才因為副檔名不在
// BG_ALLOWED_EXTS 而被 400 拒絕。這裡釘住現狀，避免未來有人「順手」把它
// 也擋掉、卻讓 MIME 判斷準確的一般案例跟著變嚴格。
test('jfif 檔案帶 image/jpeg MIME 時前端仍放行（後端才會 400）', () => {
  assert.equal(validateBackgroundFile(fakeFile('photo.jfif', 'image/jpeg', 1024)), null)
})
