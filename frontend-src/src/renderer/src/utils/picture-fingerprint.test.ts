import { test } from 'node:test'
import assert from 'node:assert/strict'
import { fingerprintFromRgba, isSamePicture, FINGERPRINT_SIZE } from './picture-fingerprint.ts'

const solid = (value: number) => {
  const { width, height } = FINGERPRINT_SIZE
  const rgba = new Uint8ClampedArray(width * height * 4)
  for (let i = 0; i < rgba.length; i += 4) {
    rgba[i] = value; rgba[i + 1] = value; rgba[i + 2] = value; rgba[i + 3] = 255
  }
  return fingerprintFromRgba(rgba)
}

test('沒有上一張就算有變', () => {
  assert.equal(isSamePicture(null, solid(100)), false)
})

test('鏡頭雜訊程度的差異算同一張', () => {
  assert.equal(isSamePicture(solid(100), solid(104)), true)
})

test('明顯的變化（換人、開燈）算不同', () => {
  assert.equal(isSamePicture(solid(100), solid(140)), false)
})
