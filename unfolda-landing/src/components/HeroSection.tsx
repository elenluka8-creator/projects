import { useEffect, useRef } from 'react'

export default function HeroSection() {
  const heroRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animate-in')
          }
        })
      },
      { threshold: 0.1 }
    )

    const elements = heroRef.current?.querySelectorAll('[data-animate]')
    elements?.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])

  const handleCTAClick = () => {
    trackCTA('hero_primary_cta')
  }

  return (
    <section
      ref={heroRef}
      className="relative min-h-screen flex items-center justify-center pt-20 pb-16 px-4 sm:px-6 lg:px-8 overflow-hidden"
    >
      {/* Background glow effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-violet-600/20 rounded-full blur-[120px]" />
        <div className="absolute top-1/3 left-1/4 w-[300px] h-[300px] bg-indigo-600/15 rounded-full blur-[80px]" />
        <div className="absolute bottom-1/4 right-1/4 w-[250px] h-[250px] bg-purple-500/10 rounded-full blur-[80px]" />
        {/* Grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)`,
            backgroundSize: '60px 60px',
          }}
        />
      </div>

      <div className="max-w-6xl mx-auto w-full">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left — text */}
          <div className="text-center lg:text-left">
            {/* Superlabel */}
            <div
              data-animate
              className="opacity-0 translate-y-4 transition-all duration-700 delay-100"
              style={{ ['--tw-translate-y' as any]: '16px' }}
            >
              <span className="inline-flex items-center gap-2 bg-violet-500/10 border border-violet-500/30 text-violet-300 text-sm font-medium px-4 py-1.5 rounded-full mb-6">
                <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-pulse" />
                Чтение без словарей и боли
              </span>
            </div>

            {/* Headline */}
            <h1
              data-animate
              className="opacity-0 translate-y-4 transition-all duration-700 delay-200 text-4xl sm:text-5xl lg:text-6xl font-bold text-white leading-[1.1] tracking-tight mb-6"
            >
              Читайте любимые книги{' '}
              <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-indigo-400 bg-clip-text text-transparent">
                в оригинале.
              </span>{' '}
              Понимайте каждое слово.
            </h1>

            {/* Subheadline */}
            <p
              data-animate
              className="opacity-0 translate-y-4 transition-all duration-700 delay-300 text-lg text-slate-400 leading-relaxed mb-10 max-w-lg mx-auto lg:mx-0"
            >
              Загружайте свои e-pub книги и читайте по методу параллельных абзацев. Учите <strong className="text-slate-200 font-semibold">английский</strong> и <strong className="text-slate-200 font-semibold">сербский</strong> языки естественно, не отвлекаясь на переводчики.
            </p>

            {/* CTA buttons */}
            <div
              data-animate
              className="opacity-0 translate-y-4 transition-all duration-700 delay-[400ms] flex flex-col sm:flex-row gap-4 justify-center lg:justify-start"
            >
              <a
                href="https://www.unfolda.ai/en/jobs"
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleCTAClick}
                className="group relative inline-flex items-center justify-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-semibold text-base px-8 py-4 rounded-2xl transition-all duration-200 shadow-xl shadow-violet-600/40 hover:shadow-violet-500/50 hover:-translate-y-1"
              >
                <span>Начать читать бесплатно</span>
                <svg
                  className="w-5 h-5 group-hover:translate-x-0.5 transition-transform"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
              </a>

              <a
                href="#how-it-works"
                className="inline-flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white font-medium text-base px-8 py-4 rounded-2xl transition-all duration-200"
              >
                Как это работает
              </a>
            </div>

            {/* Social proof */}
            <div
              data-animate
              className="opacity-0 translate-y-4 transition-all duration-700 delay-500 flex items-center gap-4 mt-10 justify-center lg:justify-start"
            >
              <div className="flex -space-x-2">
                {['🇷🇺', '🇬🇧', '🇷🇸'].map((flag, i) => (
                  <div
                    key={i}
                    className="w-8 h-8 rounded-full bg-slate-700 border-2 border-[#0a0a0f] flex items-center justify-center text-sm"
                  >
                    {flag}
                  </div>
                ))}
              </div>
              <p className="text-sm text-slate-500">
                <span className="text-slate-300 font-semibold">3 языка</span> — русский, английский, сербский
              </p>
            </div>
          </div>

          {/* Right — Phone mockup */}
          <div
            data-animate
            className="opacity-0 scale-95 transition-all duration-1000 delay-300 flex justify-center lg:justify-end"
          >
            <PhoneMockup />
          </div>
        </div>
      </div>

      <style>{`
        [data-animate].animate-in {
          opacity: 1 !important;
          transform: translateY(0) scale(1) !important;
        }
      `}</style>
    </section>
  )
}

function PhoneMockup() {
  return (
    <div className="relative">
      {/* Glow behind phone */}
      <div className="absolute inset-0 bg-violet-500/20 rounded-[3rem] blur-3xl scale-110" />

      {/* Phone frame */}
      <div className="relative w-[280px] sm:w-[300px] bg-[#111118] rounded-[2.5rem] border border-white/10 shadow-2xl overflow-hidden">
        {/* Status bar */}
        <div className="flex items-center justify-between px-6 pt-4 pb-2">
          <span className="text-white/60 text-xs font-medium">9:41</span>
          <div className="w-24 h-5 bg-[#111118] rounded-full" />
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 border border-white/40 rounded-sm relative">
              <div className="absolute inset-0.5 right-auto w-2/3 bg-green-400 rounded-sm" />
            </div>
          </div>
        </div>

        {/* App header */}
        <div className="px-5 py-3 flex items-center justify-between border-b border-white/5">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <path d="M4 6h16M4 12h10M4 18h7" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="text-white text-sm font-semibold">Unfolda</span>
          </div>
          <div className="text-xs text-violet-400 font-medium bg-violet-400/10 px-2 py-0.5 rounded-full">EN → RU</div>
        </div>

        {/* Book progress bar */}
        <div className="px-5 pt-3 pb-2">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] text-slate-500">Глава 3 / 24</span>
            <span className="text-[10px] text-violet-400">12%</span>
          </div>
          <div className="w-full h-1 bg-white/5 rounded-full">
            <div className="w-[12%] h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full" />
          </div>
        </div>

        {/* Paragraph blocks */}
        <div className="px-5 py-3 space-y-3">
          {/* Original paragraph */}
          <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-2xl p-4">
            <div className="flex items-center gap-1.5 mb-2">
              <span className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider">English</span>
              <div className="w-1 h-1 bg-indigo-400/50 rounded-full" />
              <span className="text-[10px] text-slate-500">оригинал</span>
            </div>
            <p className="text-white text-xs leading-relaxed">
              It was a bright cold day in April, and the clocks were striking thirteen. Winston Smith, his chin nuzzled into his breast in an effort to escape the vile wind...
            </p>
          </div>

          {/* Translated paragraph */}
          <div className="bg-violet-500/10 border border-violet-500/20 rounded-2xl p-4">
            <div className="flex items-center gap-1.5 mb-2">
              <span className="text-[10px] font-semibold text-violet-400 uppercase tracking-wider">Русский</span>
              <div className="w-1 h-1 bg-violet-400/50 rounded-full" />
              <span className="text-[10px] text-slate-500">перевод</span>
            </div>
            <p className="text-slate-300 text-xs leading-relaxed">
              Был ясный холодный апрельский день, и часы пробили тринадцать. Уинстон Смит, втянув подбородок в грудь, чтобы спастись от злого ветра...
            </p>
          </div>

          {/* Next paragraph hint */}
          <div className="flex items-center gap-3 pt-1">
            <div className="flex-1 h-px bg-white/5" />
            <span className="text-[10px] text-slate-600">следующий абзац</span>
            <div className="flex-1 h-px bg-white/5" />
          </div>

          <div className="bg-white/[0.03] rounded-2xl p-4 space-y-1.5">
            <div className="h-2 bg-white/10 rounded-full w-full" />
            <div className="h-2 bg-white/10 rounded-full w-4/5" />
            <div className="h-2 bg-white/10 rounded-full w-3/4" />
          </div>
        </div>

        {/* Bottom nav */}
        <div className="px-5 pb-6 pt-2 flex items-center justify-around border-t border-white/5">
          {[
            { icon: '📚', label: 'Библиотека', active: false },
            { icon: '📖', label: 'Читать', active: true },
            { icon: '⚙️', label: 'Настройки', active: false },
          ].map((item) => (
            <div key={item.label} className="flex flex-col items-center gap-1">
              <span className="text-base">{item.icon}</span>
              <span className={`text-[9px] ${item.active ? 'text-violet-400' : 'text-slate-600'}`}>
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function trackCTA(label: string) {
  if (typeof window !== 'undefined' && (window as any).gtag) {
    ;(window as any).gtag('event', 'cta_click', { event_label: label })
  }
  if (typeof window !== 'undefined' && (window as any).ym) {
    ;(window as any).ym('XXXXXXXX', 'reachGoal', 'cta_click', { label })
  }
}
