"use client";

import { Header } from "@/components/Header";
import { HeroSection } from "@/components/HeroSection";
import { ProblemSection } from "@/components/ProblemSection";
import { HowItWorksSection } from "@/components/HowItWorksSection";
import { FeaturesSection } from "@/components/FeaturesSection";
import { AudienceSection } from "@/components/AudienceSection";
import { CTASection } from "@/components/CTASection";
import { Footer } from "@/components/Footer";
import { Analytics } from "@/components/Analytics";

export default function Home() {
  return (
    <>
      <Analytics />
      <Header />
      <main className="flex-1">
        <HeroSection />
        <ProblemSection />
        <HowItWorksSection />
        <FeaturesSection />
        <AudienceSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
