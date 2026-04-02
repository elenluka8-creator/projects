import { NextRequest, NextResponse } from "next/server";

import { auth } from "@/lib/auth";
import { proxyToBackend } from "@/lib/backend-proxy";

async function handler(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const session = await auth();
  const userId = session?.user?.id;

  const { path } = await context.params;
  return proxyToBackend(request, path ?? [], userId);
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
