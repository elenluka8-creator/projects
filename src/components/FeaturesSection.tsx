"use client";

import { FadeIn, StaggerContainer, FadeInChild } from "./FadeIn";
import { Sparkles, Globe, FolderOpen } from "lucide-react";

const features = [
  {
    icon: Sparkles,
    title: "Умный AI-перевод",
    description:
      "Это не сухой машинный перевод. Система сохраняет идиомы, юмор и стиль автора. Вы читаете книгу, а не подстрочник.",
    gradient: "from-purple-500/20 to-pink-500/20",
    iconColor: "text-purple-400",
  },
  {
    icon: Globe,
    title: "Тройка языков",
    description:
      "Идеально для тех, кто живёт в Сербии: качайте английский для работы и сербский для жизни. Русский, английский, сербский — в любых парах.",
    gradient: "from-blue-500/20 to-cyan-500/20",
    iconColor: "text-blue-400",
  },
  {
    icon: FolderOpen,
    title: "Ваш контент",
    description:
      "Вы не привязаны к скучной библиотеке приложения. Читайте то, что купили или скачали сами. Ваши книги — ваш выбор.",
    gradient: "from-emerald-500/20 to-teal-500/20",
    iconColor: "text-emerald-400",
  },
];

export function FeaturesSection() {
  return (
    <section id="features" className="py-24 sm:py-32 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <FadeIn>
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-accent-light text-sm font-medium mb-4">
              Уникальные преимущества
            </span>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold">
              Почему <span className="gradient-text">Unfolda</span>
            </h2>
          </div>
        </FadeIn>

        <StaggerContainer className="grid md:grid-cols-3 gap-8">
          {features.map((feature) => (
            <FadeInChild key={feature.title}>
              <div className="group relative p-8 rounded-3xl bg-surface border border-white/5 hover:border-accent/20 transition-all duration-300 h-full overflow-hidden">
                <div
                  className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500`}
                />

                <div className="relative">
                  <div className="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300">
                    <feature.icon size={28} className={feature.iconColor} />
                  </div>

                  <h3 className="text-xl font-semibold mb-3">
                    {feature.title}
                  </h3>

                  <p className="text-muted leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </div>
            </FadeInChild>
          ))}
        </StaggerContainer>
      </div>
    </section>
  );
}
