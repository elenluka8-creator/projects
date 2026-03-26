"use client";

import { motion } from "framer-motion";
import { FadeIn } from "./FadeIn";

export function CTASection() {
  return (
    <section className="py-24 sm:py-32 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <FadeIn>
          <div className="relative rounded-[2rem] overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-accent via-accent/80 to-blue" />
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.1),transparent_60%)]" />

            <div className="relative px-8 py-16 sm:px-16 sm:py-24 text-center">
              <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white mb-6 leading-tight">
                Откройте новую главу
                <br />в изучении языков
              </h2>

              <p className="text-lg text-white/80 max-w-2xl mx-auto mb-10">
                Загрузите свою первую книгу и начните читать в оригинале уже
                сегодня. Без словарей, без переводчиков — только вы и книга.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <motion.a
                  href="https://www.unfolda.ai/en/jobs"
                  target="_blank"
                  rel="noopener noreferrer"
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-full bg-white text-accent font-semibold text-lg shadow-xl hover:shadow-2xl transition-shadow"
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 2a10 10 0 1 0 10 10h-10z" />
                    <path d="M21.18 8.02A10 10 0 0 0 15.97 2.82" />
                    <path d="M12 2v10l6.95-4.01" />
                  </svg>
                  Скачать Unfolda App
                </motion.a>
              </div>

              <div className="flex items-center justify-center gap-8 mt-8">
                <a
                  href="#"
                  className="flex items-center gap-2 text-white/70 hover:text-white transition-colors text-sm"
                >
                  <svg
                    width="20"
                    height="24"
                    viewBox="0 0 20 24"
                    fill="currentColor"
                  >
                    <path d="M13.545 0c.327 3.17-2.355 5.46-4.905 5.32C8.29 3.05 10.64 0 13.545 0zM17.86 8.67c-1.91 1.1-2.87 3.02-2.71 5.27.18 2.51 1.9 4.28 3.76 4.67-.38 1.18-.88 2.34-1.56 3.4-1.05 1.63-2.14 3.26-3.86 3.29-1.7.03-2.24-.99-4.18-.99-1.94 0-2.55.96-4.15 1.02-1.66.06-2.92-1.76-3.98-3.39C-.85 18.66-.37 12.97 2.07 9.99c1.49-1.82 3.67-3 5.72-3 1.7-.03 3.3 1.15 4.34 1.15 1.04 0 2.98-1.42 5.03-1.21.86.04 3.26.35 4.8 2.62-.12.08-2.87 1.68-2.84 5.01l-.26.01z" />
                  </svg>
                  App Store
                </a>
                <a
                  href="#"
                  className="flex items-center gap-2 text-white/70 hover:text-white transition-colors text-sm"
                >
                  <svg
                    width="20"
                    height="22"
                    viewBox="0 0 20 22"
                    fill="currentColor"
                  >
                    <path d="M1.004.513C.678.856.5 1.39.5 2.09v17.82c0 .7.178 1.234.504 1.577l.083.075L11.17 11.458v-.216L1.087.438l-.083.075z" />
                    <path d="M14.525 14.828l-3.355-3.37v-.216l3.355-3.37.075.043 3.976 2.258c1.136.645 1.136 1.7 0 2.345l-3.976 2.258-.075.052z" />
                    <path d="M14.6 14.776L11.17 11.35.924 21.567c.375.396.993.445 1.694.05L14.6 14.776z" />
                    <path d="M14.6 7.924L2.618.083C1.917-.312 1.3-.263.924.133L11.17 10.35l3.43-3.426z" />
                  </svg>
                  Google Play
                </a>
              </div>
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
