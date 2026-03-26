import { useScrollAnimation } from '../hooks/useScrollAnimation'

export default function FooterCTASection() {
  const { ref, isVisible } = useScrollAnimation()

  const handleAppStoreClick = () => trackCTA('footer_appstore')
  const handleGooglePlayClick = () => trackCTA('footer_googleplay')
  const handleWebAppClick = () => trackCTA('footer_webapp')

  return (
    <>
      {/* CTA Section */}
      <section
        ref={ref}
        className="relative py-24 px-4 sm:px-6 lg:px-8 overflow-hidden"
      >
        {/* Big glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-violet-600/15 rounded-full blur-[120px]" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-600/10 rounded-full blur-[100px]" />
        </div>

        <div className="max-w-4xl mx-auto relative text-center">
          <div
            className={`transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
          >
            {/* Badge */}
            <span className="inline-flex items-center gap-2 bg-violet-500/10 border border-violet-500/30 text-violet-300 text-sm font-medium px-4 py-1.5 rounded-full mb-8">
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
              Начните прямо сейчас — бесплатно
            </span>

            {/* Headline */}
            <h2 className="text-3xl sm:text-4xl lg:text-6xl font-bold text-white leading-[1.1] tracking-tight mb-6">
              Откройте новую главу{' '}
              <br className="hidden sm:block" />
              <span className="bg-gradient-to-r from-violet-400 via-purple-400 to-indigo-400 bg-clip-text text-transparent">
                в изучении языков
              </span>
            </h2>

            <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-12 leading-relaxed">
              Загрузите любимую книгу, выберите языковую пару и начните читать. Никаких подписок сразу — первая книга бесплатно.
            </p>

            {/* Store buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
              {/* App Store */}
              <a
                href="https://www.unfolda.ai/en/jobs"
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleAppStoreClick}
                className="group flex items-center gap-4 bg-white text-black hover:bg-gray-100 font-semibold px-6 py-4 rounded-2xl transition-all duration-200 shadow-xl hover:-translate-y-0.5 min-w-[200px]"
              >
                <svg className="w-7 h-7 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
                </svg>
                <div className="text-left">
                  <div className="text-[10px] font-medium opacity-60 uppercase tracking-wide">Скачать в</div>
                  <div className="text-base font-bold leading-tight">App Store</div>
                </div>
              </a>

              {/* Google Play */}
              <a
                href="https://www.unfolda.ai/en/jobs"
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleGooglePlayClick}
                className="group flex items-center gap-4 bg-white text-black hover:bg-gray-100 font-semibold px-6 py-4 rounded-2xl transition-all duration-200 shadow-xl hover:-translate-y-0.5 min-w-[200px]"
              >
                <svg className="w-7 h-7 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3,20.5v-17c0-0.83,0.94-1.3,1.6-0.8l14,8.5c0.6,0.37,0.6,1.23,0,1.6l-14,8.5C3.94,21.8,3,21.33,3,20.5z"/>
                </svg>
                <div className="text-left">
                  <div className="text-[10px] font-medium opacity-60 uppercase tracking-wide">Скачать в</div>
                  <div className="text-base font-bold leading-tight">Google Play</div>
                </div>
              </a>

              {/* Web version */}
              <a
                href="https://www.unfolda.ai/en/jobs"
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleWebAppClick}
                className="group flex items-center gap-4 bg-violet-600 hover:bg-violet-500 text-white font-semibold px-6 py-4 rounded-2xl transition-all duration-200 shadow-xl shadow-violet-600/30 hover:shadow-violet-500/40 hover:-translate-y-0.5 min-w-[200px]"
              >
                <svg className="w-7 h-7 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                </svg>
                <div className="text-left">
                  <div className="text-[10px] font-medium opacity-80 uppercase tracking-wide">Открыть</div>
                  <div className="text-base font-bold leading-tight">Веб-версию</div>
                </div>
              </a>
            </div>

            {/* Trust badges */}
            <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-slate-500">
              {[
                { icon: '🔒', text: 'Ваши книги в безопасности' },
                { icon: '💳', text: 'Первая книга бесплатно' },
                { icon: '📱', text: 'iOS & Android & Web' },
              ].map((badge) => (
                <div key={badge.text} className="flex items-center gap-2">
                  <span>{badge.icon}</span>
                  <span>{badge.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/8 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8 mb-12">
            {/* Brand */}
            <div className="lg:col-span-2">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path d="M4 6h16M4 12h10M4 18h7" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
                  </svg>
                </div>
                <span className="text-white font-bold text-xl tracking-tight">Unfolda</span>
              </div>
              <p className="text-slate-500 text-sm leading-relaxed max-w-xs">
                Читайте книги в оригинале. Учите языки через живой контекст, не через учебники.
              </p>
              <div className="flex items-center gap-3 mt-5">
                <span className="text-xs font-semibold text-slate-500 bg-white/5 border border-white/10 px-2 py-1 rounded-lg">🇷🇺 RU</span>
                <span className="text-xs font-semibold text-slate-500 bg-white/5 border border-white/10 px-2 py-1 rounded-lg">🇬🇧 EN</span>
                <span className="text-xs font-semibold text-slate-500 bg-white/5 border border-white/10 px-2 py-1 rounded-lg">🇷🇸 SR</span>
              </div>
            </div>

            {/* Nav links */}
            <div>
              <h4 className="text-white font-semibold text-sm mb-4">Продукт</h4>
              <ul className="space-y-3">
                {['Как работает', 'Возможности', 'Для кого', 'Цены'].map((link) => (
                  <li key={link}>
                    <a href="#" className="text-slate-500 hover:text-white text-sm transition-colors">{link}</a>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h4 className="text-white font-semibold text-sm mb-4">Компания</h4>
              <ul className="space-y-3">
                {[
                  { label: 'О нас', href: 'https://www.unfolda.ai' },
                  { label: 'Вакансии', href: 'https://www.unfolda.ai/en/jobs' },
                  { label: 'Блог', href: '#' },
                  { label: 'Контакты', href: '#' },
                ].map((link) => (
                  <li key={link.label}>
                    <a href={link.href} target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-white text-sm transition-colors">{link.label}</a>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Bottom bar */}
          <div className="border-t border-white/8 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-slate-600 text-sm">© 2024 Unfolda. Все права защищены.</p>
            <div className="flex items-center gap-6">
              <a href="#" className="text-slate-600 hover:text-slate-400 text-sm transition-colors">Политика конфиденциальности</a>
              <a href="#" className="text-slate-600 hover:text-slate-400 text-sm transition-colors">Условия использования</a>
            </div>
          </div>
        </div>
      </footer>
    </>
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
