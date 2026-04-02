import crypto from "crypto";

import NextAuth, { type DefaultSession } from "next-auth";
import Google from "next-auth/providers/google";

type ExtendedToken = {
  user_id?: string;
  google_sub?: string;
  email?: string;
  name?: string;
  exp?: number;
};

declare module "next-auth" {
  interface Session extends DefaultSession {
    user: DefaultSession["user"] & {
      id?: string;
    };
  }
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function createProvisioningToken(payload: {
  google_sub: string;
  email: string;
  name?: string;
}): string {
  const secret = requireEnv("NEXTAUTH_SECRET");
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString(
    "base64url",
  );
  const body = Buffer.from(
    JSON.stringify({
      ...payload,
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 5 * 60,
    }),
  ).toString("base64url");
  const signature = crypto
    .createHmac("sha256", secret)
    .update(`${header}.${body}`)
    .digest("base64url");
  return `${header}.${body}.${signature}`;
}

async function provisionUser(payload: {
  google_sub: string;
  email: string;
  name?: string;
}): Promise<string> {
  const backendUrl = requireEnv("BACKEND_URL");
  const token = createProvisioningToken(payload);
  const response = await fetch(`${backendUrl}/auth/provision`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Provisioning failed with status ${response.status}`);
  }

  const data = (await response.json()) as { user_id: string };
  if (!data.user_id) {
    throw new Error("Provisioning response missing user_id");
  }
  return data.user_id;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  secret: process.env.NEXTAUTH_SECRET,
  session: {
    strategy: "jwt",
    maxAge: 60 * 60 * 8,
  },
  providers: [
    Google({
      clientId: requireEnv("GOOGLE_CLIENT_ID"),
      clientSecret: requireEnv("GOOGLE_CLIENT_SECRET"),
    }),
  ],
  callbacks: {
    async jwt({ token, profile }) {
      const extendedToken = token as ExtendedToken;
      if (profile?.sub && profile.email) {
        const userId = await provisionUser({
          google_sub: profile.sub,
          email: profile.email,
          name: profile.name ?? undefined,
        });
        extendedToken.user_id = userId;
        extendedToken.google_sub = profile.sub;
        extendedToken.email = profile.email;
        extendedToken.name = profile.name ?? undefined;
      }

      return token;
    },
    async session({ session, token }) {
      const extendedToken = token as ExtendedToken;
      if (session.user && extendedToken.user_id) {
        session.user.id = extendedToken.user_id;
      }
      return session;
    },
  },
  pages: {
    signIn: "/en/login",
  },
});
