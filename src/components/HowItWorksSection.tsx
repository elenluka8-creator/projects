"use client";

import { FadeIn, StaggerContainer, FadeInChild } from "./FadeIn";
import { Upload, Languages, BookOpenCheck } from "lucide-react";

const steps = [
  {
    number: "01",
    icon: Upload,
    title: "Загрузите свою книгу",
    description:
      "Поддерживаются форматы EPUB, FB2 и PDF. Загрузите то, что уже купили или скачали.",
  },
  {
    number: "02",
    icon: Languages,
    title: "Выберите пару языков",
    description:
      "Английский, русский или сербский — в любых комбинациях. Идеально для экспатов в Сербии.",
  },
  {
    number: "03",
    icon: BookOpenCheck,
    title: "Читайте в удовольствие",
    description:
      "Сравнивайте абзацы на лету и учите живую лексику в контексте любимых книг.",
  },
];

export function HowItWorksSection() {
  return (
    <section id="how" className="py-24 sm:py-32 relative">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-accent/[0.02] to-transparent pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        <FadeIn>
          <div className="text-center mb-16">
            <span className="inline-block px-4 py-1.5 rounded-full bg-accent/10 border border-accent/20 text-accent-light text-sm font-medium mb-4">
              Простота в 3 шага
            </span>
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold">
              Как это <span className="gradient-text">работает</span>
            </h2>
          </div>
        </FadeIn>

        <StaggerContainer className="grid md:grid-cols-3 gap-8">
          {steps.map((step) => (
            <FadeInChild key={step.number}>
              <div className="group relative p-8 rounded-3xl bg-surface border border-white/5 hover:border-accent/20 transition-all duration-300 h-full">
                <div className="absolute top-6 right-6 text-5xl font-bold step-number opacity-30 group-hover:opacity-60 transition-opacity">
                  {step.number}
                </div>

                <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mb-6 group-hover:bg-accent/20 transition-colors">
                  <step.icon size={28} className="text-accent-light" />
                </div>

                <h3 className="text-xl font-semibold mb-3">{step.title}</h3>

                <p className="text-muted leading-relaxed">
                  {step.description}
                </p>
              </div>
            </FadeInChild>
          ))}
        </StaggerContainer>
      </div>
    </section>
  );
}
