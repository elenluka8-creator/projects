/**
 * Mint a short-lived HS256 JWT for backend API calls.
 *
 * Uses the Web Crypto API so this module is safe in Edge Runtime,
 * Node.js (v18+), and browser contexts — no node:crypto or Buffer.
 *
 * The backend's decode_bearer_jwt() expects:
 *   - alg: HS256
 *   - payload.user_id: UUID string
 *   - secret: NEXTAUTH_SECRET
 *
 * TTL is intentionally short (60 s) — tokens are minted per-request in the
 * API proxy route and never stored.
 */

function toBase64Url(data: string): string {
  const bytes = new TextEncoder().encode(data);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

async function signHS256(secret: string, data: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await globalThis.crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await globalThis.crypto.subtle.sign("HMAC", key, enc.encode(data));
  const bytes = new Uint8Array(sig);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

export async function createApiToken(userId: string): Promise<string> {
  const secret = process.env.NEXTAUTH_SECRET;
  if (!secret) {
    throw new Error("NEXTAUTH_SECRET is required to mint API tokens");
  }

  const now = Math.floor(Date.now() / 1000);
  const header = toBase64Url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = toBase64Url(
    JSON.stringify({
      user_id: userId,
      iat: now,
      exp: now + 60,
    }),
  );
  const signature = await signHS256(secret, `${header}.${payload}`);
  return `${header}.${payload}.${signature}`;
}
