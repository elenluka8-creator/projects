import type { ReactNode } from "react";
import { getLocale } from "next-intl/server";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "./globals.css";

export const metadata = {
  title: "Unfolda",
  description: "Unfold books in foreign languages",
  icons: [{ rel: "icon", url: "/favicon.svg", type: "image/svg+xml" }],
};

type RootLayoutProps = {
  children: ReactNode;
};

export default async function RootLayout({ children }: RootLayoutProps) {
  const locale = await getLocale();
  return (
    <html lang={locale}>
      <body>{children}</body>
    </html>
  );
}
