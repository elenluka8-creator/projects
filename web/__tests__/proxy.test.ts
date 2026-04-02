// @vitest-environment node

import { NextRequest } from "next/server";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { proxyToBackend } from "../lib/backend-proxy";

describe("proxyToBackend", () => {
  beforeEach(() => {
    process.env.NEXTAUTH_SECRET = "x".repeat(32);
    process.env.BACKEND_URL = "http://127.0.0.1:9";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns 401 when userId is missing", async () => {
    const req = new NextRequest("http://localhost/api/backend/jobs");
    const res = await proxyToBackend(req, ["jobs"], undefined);
    expect(res.status).toBe(401);
    const body = (await res.json()) as { error: string };
    expect(body.error).toBe("Unauthorized");
  });

  it("forwards GET and returns JSON from upstream", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ hello: "world" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const req = new NextRequest("http://localhost/api/backend/jobs");
    const res = await proxyToBackend(req, ["jobs"], "550e8400-e29b-41d4-a716-446655440000");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("http://127.0.0.1:9/jobs");
    const headers = call[1]?.headers as Record<string, string>;
    expect(headers.Authorization).toMatch(/^Bearer /);

    expect(res.status).toBe(200);
    const data = (await res.json()) as { hello: string };
    expect(data.hello).toBe("world");
  });
});
