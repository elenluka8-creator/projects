import { useState, useEffect } from 'react'

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const handleCTAClick = () => {
    trackCTA('navbar_cta')
  }

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-[#0a0a0f]/90 backdrop-blur-xl border-b border-white/10'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 md:h-20">
          {/* Logo */}
          <a href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/30 group-hover:shadow-violet-500/50 transition-shadow">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M4 6h16M4 12h10M4 18h7" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="text-white font-bold text-xl tracking-tight">Unfolda</span>
          </a>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-8">
            <a href="#how-it-works" className="text-slate-400 hover:text-white text-sm font-medium transition-colors">Как работает</a>
            <a href="#features" className="text-slate-400 hover:text-white text-sm font-medium transition-colors">Возможности</a>
            <a href="#audience" className="text-slate-400 hover:text-white text-sm font-medium transition-colors">Для кого</a>
          </div>

          {/* CTA */}
          <div className="hidden md:block">
            <a
              href="https://www.unfolda.ai/en/jobs"
              target="_blank"
              rel="noopener noreferrer"
              onClick={handleCTAClick}
              className="inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-all duration-200 shadow-lg shadow-violet-600/30 hover:shadow-violet-500/40 hover:-translate-y-0.5"
            >
              Начать бесплатно
            </a>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden p-2 text-slate-400 hover:text-white transition-colors"
            aria-label="Toggle menu"
          >
            {menuOpen ? (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            ) : (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            )}
          </button>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden py-4 border-t border-white/10 space-y-3 animate-fade-in">
            <a href="#how-it-works" onClick={() => setMenuOpen(false)} className="block text-slate-300 hover:text-white py-2 text-sm font-medium transition-colors">Как работает</a>
            <a href="#features" onClick={() => setMenuOpen(false)} className="block text-slate-300 hover:text-white py-2 text-sm font-medium transition-colors">Возможности</a>
            <a href="#audience" onClick={() => setMenuOpen(false)} className="block text-slate-300 hover:text-white py-2 text-sm font-medium transition-colors">Для кого</a>
            <a
              href="https://www.unfolda.ai/en/jobs"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => { setMenuOpen(false); trackCTA('mobile_navbar_cta') }}
              className="block w-full text-center bg-violet-600 hover:bg-violet-500 text-white text-sm font-semibold px-5 py-3 rounded-xl transition-all duration-200 mt-2"
            >
              Начать бесплатно
            </a>
          </div>
        )}
      </div>
    </nav>
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
