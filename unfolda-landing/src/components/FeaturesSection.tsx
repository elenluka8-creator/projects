import { useScrollAnimation } from '../hooks/useScrollAnimation'

const features = [
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
      </svg>
    ),
    title: 'Умный AI-перевод',
    tagline: 'Не машинный, а живой',
    description: 'Это не сухой машинный перевод. Система сохраняет идиомы, юмор и стиль автора — как делает профессиональный переводчик.',
    highlight: 'Идиомы и стиль автора сохранены',
    color: 'violet',
    gradient: 'from-violet-500/20 to-transparent',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 21l5.25-11.25L21 21m-9-3h7.5M3 5.621a48.474 48.474 0 016-.371m0 0c1.12 0 2.233.038 3.334.114M9 5.25V3m3.334 2.364C11.176 10.658 7.69 15.08 3 17.502m9.334-12.138c.896.061 1.785.147 2.666.257m-4.589 8.495a18.023 18.023 0 01-3.827-5.802" />
      </svg>
    ),
    title: 'Тройка языков',
    tagline: 'Идеально для экспатов',
    description: 'Идеально для тех, кто живёт в Сербии: качайте английский для работы и сербский для жизни — в одном приложении.',
    highlight: 'EN + RU + SR в любых парах',
    color: 'indigo',
    gradient: 'from-indigo-500/20 to-transparent',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
      </svg>
    ),
    title: 'Ваш контент',
    tagline: 'Никаких чужих библиотек',
    description: 'Вы не привязаны к скучной библиотеке приложения. Читайте то, что купили или скачали сами — любимые книги, статьи, материалы.',
    highlight: 'EPUB, FB2, PDF — всё ваше',
    color: 'purple',
    gradient: 'from-purple-500/20 to-transparent',
  },
]

const colorMap: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  violet: {
    bg: 'bg-violet-500/10',
    border: 'border-violet-500/20',
    text: 'text-violet-400',
    badge: 'bg-violet-500/5 border-violet-500/15 text-violet-400',
  },
  indigo: {
    bg: 'bg-indigo-500/10',
    border: 'border-indigo-500/20',
    text: 'text-indigo-400',
    badge: 'bg-indigo-500/5 border-indigo-500/15 text-indigo-400',
  },
  purple: {
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/20',
    text: 'text-purple-400',
    badge: 'bg-purple-500/5 border-purple-500/15 text-purple-400',
  },
}

export default function FeaturesSection() {
  const { ref, isVisible } = useScrollAnimation()

  return (
    <section
      id="features"
      ref={ref}
      className="relative py-24 px-4 sm:px-6 lg:px-8"
    >
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-0 w-[400px] h-[400px] bg-violet-600/8 rounded-full blur-[100px]" />
        <div className="absolute top-1/2 right-0 w-[400px] h-[400px] bg-indigo-600/8 rounded-full blur-[100px]" />
      </div>

      <div className="max-w-6xl mx-auto relative">
        {/* Header */}
        <div
          className={`text-center mb-16 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
        >
          <span className="inline-flex items-center gap-2 bg-violet-500/10 border border-violet-500/20 text-violet-300 text-sm font-medium px-4 py-1.5 rounded-full mb-6">
            ⚡ Возможности
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white leading-tight tracking-tight">
            Почему выбирают{' '}
            <span className="bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
              Unfolda
            </span>
          </h2>
          <p className="text-lg text-slate-400 mt-4 max-w-xl mx-auto">
            Не просто читалка с переводом — это целая система изучения языка через живые тексты.
          </p>
        </div>

        {/* Feature cards */}
        <div className="grid md:grid-cols-3 gap-6 lg:gap-8">
          {features.map((feature, index) => {
            const colors = colorMap[feature.color]
            return (
              <div
                key={feature.title}
                className={`transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'}`}
                style={{ transitionDelay: `${index * 150}ms` }}
              >
                <div className="relative bg-[#111118] border border-white/8 rounded-3xl p-8 h-full group hover:border-white/15 transition-all duration-300 hover:-translate-y-1 overflow-hidden">
                  {/* Gradient overlay */}
                  <div className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none`} />

                  <div className="relative z-10">
                    {/* Icon */}
                    <div className={`w-12 h-12 rounded-2xl ${colors.bg} border ${colors.border} flex items-center justify-center ${colors.text} mb-6`}>
                      {feature.icon}
                    </div>

                    {/* Tagline */}
                    <div className={`inline-block text-xs font-semibold ${colors.text} ${colors.bg} border ${colors.border} px-2.5 py-1 rounded-lg mb-3`}>
                      {feature.tagline}
                    </div>

                    <h3 className="text-xl font-bold text-white mb-3">{feature.title}</h3>
                    <p className="text-slate-400 text-sm leading-relaxed mb-6">{feature.description}</p>

                    {/* Highlight chip */}
                    <div className={`flex items-center gap-2 text-xs font-medium ${colors.badge} border rounded-xl px-3 py-2`}>
                      <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                      {feature.highlight}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Comparison table — mobile friendly */}
        <div
          className={`mt-16 transition-all duration-700 delay-500 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
        >
          <div className="bg-[#111118] border border-white/8 rounded-3xl overflow-hidden">
            <div className="px-6 py-5 border-b border-white/8">
              <h3 className="text-lg font-bold text-white">Unfolda vs Традиционные методы</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left px-6 py-4 text-slate-500 text-sm font-medium">Параметр</th>
                    <th className="px-6 py-4 text-violet-400 text-sm font-semibold text-center">Unfolda</th>
                    <th className="px-6 py-4 text-slate-500 text-sm font-medium text-center">Переводчик</th>
                    <th className="px-6 py-4 text-slate-500 text-sm font-medium text-center">Учебники</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {[
                    ['Живой контекст', '✅', '❌', '❌'],
                    ['Ваши книги', '✅', '✅', '❌'],
                    ['В потоке чтения', '✅', '❌', '❌'],
                    ['Стиль автора', '✅', '❌', '❌'],
                    ['Тройка языков', '✅', '✅', '❌'],
                  ].map(([param, ...vals]) => (
                    <tr key={param} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-6 py-3.5 text-sm text-slate-400">{param}</td>
                      {vals.map((val, i) => (
                        <td key={i} className="px-6 py-3.5 text-center text-sm">{val}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
