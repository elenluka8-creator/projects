import { useScrollAnimation } from '../hooks/useScrollAnimation'

export default function PainSolutionSection() {
  const { ref, isVisible } = useScrollAnimation()

  return (
    <section
      ref={ref}
      className="relative py-24 px-4 sm:px-6 lg:px-8 overflow-hidden"
    >
      {/* Subtle separator glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-24 bg-gradient-to-b from-transparent via-violet-500/30 to-transparent" />

      <div className="max-w-6xl mx-auto">
        <div
          className={`transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
        >
          {/* Section badge */}
          <div className="flex justify-center mb-6">
            <span className="inline-flex items-center gap-2 bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-medium px-4 py-1.5 rounded-full">
              😤 Знакомо?
            </span>
          </div>

          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white text-center leading-tight tracking-tight mb-6">
            Хватит гуглить каждое слово
          </h2>
          <p className="text-lg text-slate-400 text-center max-w-2xl mx-auto mb-16 leading-relaxed">
            Учить язык по учебникам скучно, а читать книги в оригинале — тяжело. Постоянно переключаться между читалкой и переводчиком убивает всё удовольствие от сюжета.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {/* Pain card */}
          <div
            className={`transition-all duration-700 delay-100 ${isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-8'}`}
          >
            <div className="relative bg-[#111118] border border-red-500/15 rounded-3xl p-8 h-full overflow-hidden">
              <div className="absolute top-0 right-0 w-48 h-48 bg-red-500/5 rounded-full blur-3xl" />

              <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-6 text-2xl">
                😩
              </div>

              <h3 className="text-xl font-bold text-white mb-4">Сейчас это выглядит так</h3>

              <ul className="space-y-4">
                {[
                  { icon: '📖', text: 'Читаете абзац на английском' },
                  { icon: '🔄', text: 'Переключаетесь в Google Translate' },
                  { icon: '📋', text: 'Копируете непонятное слово' },
                  { icon: '😤', text: 'Теряете нить сюжета' },
                  { icon: '🔁', text: 'Повторяете сначала...' },
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="text-lg flex-shrink-0 mt-0.5">{item.icon}</span>
                    <span className="text-slate-400 text-sm leading-relaxed">{item.text}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-6 bg-red-500/5 border border-red-500/15 rounded-2xl p-4">
                <p className="text-red-400/80 text-sm italic">«Бросил читать на второй странице. Слишком тяжело.»</p>
              </div>
            </div>
          </div>

          {/* Solution card */}
          <div
            className={`transition-all duration-700 delay-200 ${isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}`}
          >
            <div className="relative bg-[#111118] border border-violet-500/20 rounded-3xl p-8 h-full overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-violet-500/8 rounded-full blur-3xl" />

              <div className="w-12 h-12 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mb-6 text-2xl">
                ✨
              </div>

              <h3 className="text-xl font-bold text-white mb-2">Решение Unfolda</h3>
              <p className="text-violet-400 text-sm font-medium mb-6">Параллельное чтение — один экран, два языка</p>

              <div className="space-y-4">
                <p className="text-slate-300 leading-relaxed text-sm">
                  Вы просто загружаете свою книгу. Приложение разбивает её на смысловые блоки и даёт перевод абзац в абзац.
                </p>
                <p className="text-slate-300 leading-relaxed text-sm">
                  Вы остаётесь в потоке чтения, а мозг запоминает контекст — так работает естественное усвоение языка.
                </p>
              </div>

              <div className="mt-6 grid grid-cols-3 gap-3">
                {[
                  { label: 'Без переключений', icon: '🎯' },
                  { label: 'В потоке чтения', icon: '🌊' },
                  { label: 'Живой контекст', icon: '🧠' },
                ].map((item) => (
                  <div key={item.label} className="bg-violet-500/5 border border-violet-500/15 rounded-xl p-3 text-center">
                    <div className="text-xl mb-1">{item.icon}</div>
                    <div className="text-[11px] text-slate-400 font-medium">{item.label}</div>
                  </div>
                ))}
              </div>

              <div className="mt-6 bg-violet-500/5 border border-violet-500/15 rounded-2xl p-4">
                <p className="text-violet-300/80 text-sm italic">«Наконец-то дочитал "1984" в оригинале. Занял три недели вместо трёх месяцев.»</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
