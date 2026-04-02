import { auth } from "@/lib/auth";
import { createApiToken } from "@/lib/tokens";

export type ServerProfile = {
  user_id: string;
  email: string;
  is_admin: boolean;
  balance: number;
};

/**
 * Load the current user's profile from the FastAPI backend (server-only).
 * Used by the admin layout to enforce is_admin before rendering /admin.
 */
export async function fetchServerProfile(): Promise<ServerProfile | null> {
  const session = await auth();
  if (!session?.user?.id) {
    return null;
  }
  const token = await createApiToken(session.user.id);
  const base = process.env.BACKEND_URL ?? "http://localhost:8000";
  const res = await fetch(`${base}/config/profile`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    return null;
  }
  return (await res.json()) as ServerProfile;
}
