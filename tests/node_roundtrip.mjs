/**
 * 浏览器解密链路验证：用 Node 的 WebCrypto（与浏览器 crypto.subtle 同一套 API）
 * 解密 tests/fixtures/sample.enc.json，确认前端能解开 Python 生成的密文。
 *
 * 用法：node tests/node_roundtrip.mjs
 */

import { readFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const { subtle } = webcrypto;
const encoder = new TextEncoder();
const decoder = new TextDecoder();

const b64ToBytes = (value) => Uint8Array.from(Buffer.from(value, 'base64'));

async function decryptEnvelope(envelope, passphrase) {
  const baseKey = await subtle.importKey('raw', encoder.encode(passphrase), 'PBKDF2', false, ['deriveKey']);
  const key = await subtle.deriveKey(
    { name: 'PBKDF2', salt: b64ToBytes(envelope.salt), iterations: envelope.iter, hash: 'SHA-256' },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['decrypt'],
  );
  const plaintext = await subtle.decrypt({ name: 'AES-GCM', iv: b64ToBytes(envelope.iv) }, key, b64ToBytes(envelope.ct));
  return JSON.parse(decoder.decode(plaintext));
}

const envelope = JSON.parse(readFileSync(join(here, 'fixtures', 'sample.enc.json'), 'utf8'));
const expected = JSON.parse(readFileSync(join(here, 'fixtures', 'sample.plain.json'), 'utf8'));

/** 递归排序键，避免因键顺序差异误判。 */
const canonical = (value) => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  }
  return value;
};

const decrypted = await decryptEnvelope(envelope, 'demo-pass');
if (JSON.stringify(canonical(decrypted)) !== JSON.stringify(canonical(expected))) {
  console.error('✗ WebCrypto 解密结果与 sample.plain.json 不一致');
  process.exit(1);
}
console.log(`✓ WebCrypto 解密通过：${decrypted.courses.length} 条课程安排，学期 ${decrypted.term}`);
