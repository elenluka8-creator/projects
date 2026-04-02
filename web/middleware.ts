import createIntlMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";
import { auth } from "./lib/auth";

const intlMiddleware = createIntlMiddleware(routing);

export default auth((req) => {
  const pathname = req.nextUrl.pathname;

  // Auth API routes pass through without locale handling
  if (pathname.startsWith("/api/auth") || pathname.startsWith("/api/backend")) {
    return;
  }

  const { locales, defaultLocale } = routing;

  // Detect active locale from path prefix
  const activeLocale =
    locales.find((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`)) ??
    defaultLocale;

  const isLoginPage =
    pathname === "/login" ||
    locales.some((l) => pathname === `/${l}/login`);

  const isPublicPage =
    isLoginPage ||
    locales.some(
      (l) =>
        pathname === `/${l}/terms` ||
        pathname === `/${l}/privacy`
    );

  // Redirect root "/" and "/{locale}" to the appropriate landing page.
  const isRootPath =
    pathname === "/" || locales.some((l) => pathname === `/${l}`);

  if (isRootPath) {
    return Response.redirect(
      new URL(
        req.auth ? `/${activeLocale}/jobs` : `/${activeLocale}/login`,
        req.url
      )
    );
  }

  if (!req.auth && !isPublicPage) {
    return Response.redirect(new URL(`/${activeLocale}/login`, req.url));
  }

  // Redirect authenticated users away from the login page
  if (req.auth && isLoginPage) {
    return Response.redirect(new URL(`/${activeLocale}/jobs`, req.url));
  }

  return intlMiddleware(req);
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|favicon\\.svg).*)"],
};
