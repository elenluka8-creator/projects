import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "cyrillic"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Unfolda — Читайте книги в оригинале. Понимайте каждое слово.",
  description:
    "Загружайте свои e-pub книги и читайте по методу параллельных абзацев. Учите английский и сербский языки естественно, не отвлекаясь на переводчики.",
  keywords: [
    "книги на английском",
    "параллельный перевод",
    "читать книги в оригинале",
    "изучение английского",
    "изучение сербского",
    "epub ридер",
    "языковое обучение",
    "Unfolda",
  ],
  authors: [{ name: "Unfolda" }],
  openGraph: {
    title: "Unfolda — Читайте книги в оригинале",
    description:
      "Загружайте свои e-pub книги и читайте по методу параллельных абзацев. Учите английский и сербский языки естественно.",
    url: "https://www.unfolda.ai",
    siteName: "Unfolda",
    type: "website",
    locale: "ru_RU",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Unfolda — параллельное чтение книг",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Unfolda — Читайте книги в оригинале",
    description:
      "Загружайте свои e-pub книги и читайте по методу параллельных абзацев.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
  metadataBase: new URL("https://www.unfolda.ai"),
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className={`${inter.variable} antialiased`}>
      <body className="min-h-screen flex flex-col">{children}</body>
    </html>
  );
}
