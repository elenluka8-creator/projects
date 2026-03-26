"use client";

import { FadeIn, StaggerContainer, FadeInChild } from "./FadeIn";
import { Plane, GraduationCap, Heart } from "lucide-react";

const audiences = [
  {
    icon: Plane,
    title: "Для экспатов",
    description:
      "Быстрое погружение в языковую среду Сербии или англоязычного мира. Читайте местную прессу и литературу без барьеров.",
    tag: "Релокация",
  },
  {
    icon: GraduationCap,
    title: "Для студентов и профи",
    description:
      "Чтение профессиональной литературы без потери смыслов. Технические книги, бизнес-издания, научные статьи — всё в параллельном формате.",
    tag: "Карьера",
  },
  {
    icon: Heart,
    title: "Для книголюбов",
    description:
      "Наслаждение языком оригинала без чувства вины за «подглядывание» в перевод. Это не читинг — это умное чтение.",
    tag: "Удовольствие",
  },
];

export function AudienceSection() {
  return (
    <section id="audience" className="py-24 sm:py-32 relative">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-blue/[0.02] to-transparent pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        <FadeIn>
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-blue/10 border border-blue/20 text-blue text-sm font-medium mb-4">
              Найдите себя
            </span>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold">
              Для кого <span className="gradient-text">Unfolda</span>
            </h2>
          </div>
        </FadeIn>

        <StaggerContainer className="grid md:grid-cols-3 gap-8">
          {audiences.map((audience) => (
            <FadeInChild key={audience.title}>
              <div className="relative p-8 rounded-3xl bg-surface border border-white/5 h-full">
                <div className="absolute top-6 right-6">
                  <span className="text-xs px-3 py-1 rounded-full bg-accent/10 text-accent-light font-medium">
                    {audience.tag}
                  </span>
                </div>

                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent/10 to-blue/10 flex items-center justify-center mb-6">
                  <audience.icon size={28} className="text-accent-light" />
                </div>

                <h3 className="text-xl font-semibold mb-3">
                  {audience.title}
                </h3>

                <p className="text-muted leading-relaxed">
                  {audience.description}
                </p>
              </div>
            </FadeInChild>
          ))}
        </StaggerContainer>
      </div>
    </section>
  );
}
