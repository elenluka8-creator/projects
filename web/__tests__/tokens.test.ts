// @vitest-environment node

import { describe, expect, it, beforeEach } from "vitest";
import { createApiToken } from "../lib/tokens";

describe("createApiToken", () => {
  beforeEach(() => {
    process.env.NEXTAUTH_SECRET = "x".repeat(32);
  });

  it("returns a three-part JWT", async () => {
    const token = await createApiToken("550e8400-e29b-41d4-a716-446655440000");
    const parts = token.split(".");
    expect(parts).toHaveLength(3);
  });

  it("embeds user_id in payload", async () => {
    const uid = "550e8400-e29b-41d4-a716-446655440000";
    const token = await createApiToken(uid);
    const payloadB64 = token.split(".")[1];
    const json = JSON.parse(
      Buffer.from(payloadB64, "base64url").toString("utf8"),
    ) as { user_id: string; iat: number; exp: number };
    expect(json.user_id).toBe(uid);
    expect(json.exp).toBeGreaterThan(json.iat);
  });
});
