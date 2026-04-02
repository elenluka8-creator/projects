import { type NextRequest, NextResponse } from "next/server";
import { createApiToken } from "@/lib/tokens";

const DEFAULT_BACKEND = "http://localhost:8000";

/**
 * Forward an authenticated request to the FastAPI backend.
 * Extracted for unit testing without Next.js route wiring.
 */
export async function proxyToBackend(
  req: NextRequest,
  pathSegments: string[],
  userId: string | undefined,
): Promise<NextResponse> {
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const backendUrl = process.env.BACKEND_URL ?? DEFAULT_BACKEND;
  const backendPath = pathSegments.join("/");
  const search = req.nextUrl.search;
  const url = `${backendUrl}/${backendPath}${search}`;

  const forwardHeaders: Record<string, string> = {
    Authorization: `Bearer ${await createApiToken(userId)}`,
  };

  const contentType = req.headers.get("content-type");
  if (contentType) {
    forwardHeaders["Content-Type"] = contentType;
  }

  let body: BodyInit | undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers: forwardHeaders,
      body,
      cache: "no-store",
    });
  } catch (err) {
    console.error("[proxy] backend unreachable", { url, err });
    return NextResponse.json({ error: "Backend unreachable" }, { status: 502 });
  }

  const upstreamType = upstream.headers.get("content-type") ?? "";
  if (upstreamType.includes("application/json")) {
    const data: unknown = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  }

  const blob = await upstream.arrayBuffer();
  return new NextResponse(blob, {
    status: upstream.status,
    headers: {
      "Content-Type": upstreamType || "application/octet-stream",
    },
  });
}
