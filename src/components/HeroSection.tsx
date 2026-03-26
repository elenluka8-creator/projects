"use client";

import { motion } from "framer-motion";
import { FadeIn } from "./FadeIn";
import { PhoneMockup } from "./PhoneMockup";

export function HeroSection() {
  return (
    <section className="relative min-h-screen flex items-center pt-20 pb-16 overflow-hidden">
      <div className="hero-glow top-[-200px] left-1/2 -translate-x-1/2" />
      <div className="hero-glow bottom-[-200px] right-[-200px]" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          <div className="text-center lg:text-left">
            <FadeIn>
              <span className="inline-block px-4 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-accent-light text-sm font-medium mb-6">
                Чтение без словарей и боли
              </span>
            </FadeIn>

            <FadeIn delay={0.1}>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight tracking-tight mb-6">
                Читайте любимые книги в оригинале.{" "}
                <span className="gradient-text">Понимайте каждое слово.</span>
              </h1>
            </FadeIn>

            <FadeIn delay={0.2}>
              <p className="text-lg sm:text-xl text-muted max-w-xl mx-auto lg:mx-0 mb-8 leading-relaxed">
                Загружайте свои e-pub книги и читайте по методу параллельных
                абзацев. Учите английский и сербский языки естественно, не
                отвлекаясь на переводчики.
              </p>
            </FadeIn>

            <FadeIn delay={0.3}>
              <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
                <motion.a
                  href="https://www.unfolda.ai/en/jobs"
                  target="_blank"
                  rel="noopener noreferrer"
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  className="px-8 py-4 rounded-full bg-gradient-to-r from-accent to-blue text-white font-semibold text-lg shadow-lg shadow-accent/25 hover:shadow-accent/40 transition-shadow animate-pulse-glow"
                >
                  Начать читать бесплатно
                </motion.a>
                <a
                  href="#how"
                  className="px-8 py-4 rounded-full border border-white/10 text-foreground font-medium text-lg hover:bg-white/5 transition-colors text-center"
                >
                  Как это работает?
                </a>
              </div>
            </FadeIn>
          </div>

          <FadeIn direction="right" delay={0.2}>
            <div className="flex justify-center lg:justify-end">
              <PhoneMockup />
            </div>
          </FadeIn>
        </div>
      </div>
    </section>
  );
}
