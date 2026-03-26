"use client";

import { FadeIn, StaggerContainer, FadeInChild } from "./FadeIn";
import { BookOpen, ArrowLeftRight, Frown } from "lucide-react";

const painPoints = [
  {
    icon: BookOpen,
    text: "Учить язык по учебникам скучно",
  },
  {
    icon: ArrowLeftRight,
    text: "Постоянно переключаться между читалкой и переводчиком",
  },
  {
    icon: Frown,
    text: "Теряется удовольствие от сюжета",
  },
];

export function ProblemSection() {
  return (
    <section id="problem" className="py-24 sm:py-32 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <div>
            <FadeIn>
              <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-6 leading-tight">
                Хватит гуглить{" "}
                <span className="gradient-text">каждое слово</span>
              </h2>
            </FadeIn>

            <FadeIn delay={0.1}>
              <p className="text-lg text-muted leading-relaxed mb-8">
                Учить язык по учебникам скучно, а читать книги в оригинале —
                тяжело. Постоянно переключаться между читалкой и переводчиком
                убивает всё удовольствие от сюжета.
              </p>
            </FadeIn>

            <StaggerContainer className="space-y-4">
              {painPoints.map((point) => (
                <FadeInChild key={point.text}>
                  <div className="flex items-center gap-4 p-4 rounded-2xl bg-surface border border-white/5">
                    <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center flex-shrink-0">
                      <point.icon size={20} className="text-red-400" />
                    </div>
                    <p className="text-foreground/80">{point.text}</p>
                  </div>
                </FadeInChild>
              ))}
            </StaggerContainer>
          </div>

          <div>
            <FadeIn direction="right">
              <div className="p-8 rounded-3xl bg-surface border border-white/5 relative">
                <div className="absolute -top-3 -left-3 px-4 py-1.5 rounded-full bg-gradient-to-r from-accent to-blue text-white text-sm font-semibold">
                  Решение Unfolda
                </div>
                <div className="pt-4 space-y-6">
                  <p className="text-lg text-foreground/90 leading-relaxed">
                    Вы просто загружаете свою книгу. Приложение разбивает её на
                    смысловые блоки и даёт перевод абзац в абзац.
                  </p>
                  <div className="h-px bg-gradient-to-r from-accent/30 via-blue/30 to-transparent" />
                  <p className="text-lg text-foreground/90 leading-relaxed">
                    Вы остаётесь в потоке чтения, а мозг запоминает контекст.
                    Никаких словарей, никаких переключений — только книга и
                    понимание.
                  </p>
                </div>
              </div>
            </FadeIn>
          </div>
        </div>
      </div>
    </section>
  );
}
