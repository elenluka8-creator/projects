import { useScrollAnimation } from '../hooks/useScrollAnimation'

const steps = [
  {
    number: '01',
    title: 'Загрузите свою книгу',
    description: 'Поддерживаем форматы EPUB, FB2 и PDF. Просто выберите файл из хранилища — никакой регистрации на сторонних сервисах.',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
    ),
    formats: ['EPUB', 'FB2', 'PDF'],
    color: 'from-violet-500 to-indigo-600',
    bgColor: 'bg-violet-500/10',
    borderColor: 'border-violet-500/20',
    textColor: 'text-violet-400',
  },
  {
    number: '02',
    title: 'Выберите пару языков',
    description: 'Английский, русский или сербский — в любых комбинациях. AI автоматически адаптирует перевод под ваш уровень.',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 21l5.25-11.25L21 21m-9-3h7.5M3 5.621a48.474 48.474 0 016-.371m0 0c1.12 0 2.233.038 3.334.114M9 5.25V3m3.334 2.364C11.176 10.658 7.69 15.08 3 17.502m9.334-12.138c.896.061 1.785.147 2.666.257m-4.589 8.495a18.023 18.023 0 01-3.827-5.802" />
      </svg>
    ),
    langs: ['🇬🇧 EN', '🇷🇺 RU', '🇷🇸 SR'],
    color: 'from-purple-500 to-violet-600',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/20',
    textColor: 'text-purple-400',
  },
  {
    number: '03',
    title: 'Читайте в удовольствие',
    description: 'Сравнивайте абзацы на лету и учите живую лексику в контексте. Мозг сам запоминает слова — никакой зубрёжки.',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
      </svg>
    ),
    color: 'from-indigo-500 to-blue-600',
    bgColor: 'bg-indigo-500/10',
    borderColor: 'border-indigo-500/20',
    textColor: 'text-indigo-400',
  },
]

export default function HowItWorksSection() {
  const { ref, isVisible } = useScrollAnimation()

  return (
    <section
      id="how-it-works"
      ref={ref}
      className="relative py-24 px-4 sm:px-6 lg:px-8"
    >
      {/* Background accent */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-indigo-600/10 rounded-full blur-[100px]" />
      </div>

      <div className="max-w-6xl mx-auto relative">
        {/* Header */}
        <div
          className={`text-center mb-16 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
        >
          <span className="inline-flex items-center gap-2 bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-sm font-medium px-4 py-1.5 rounded-full mb-6">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
            </svg>
            Три шага до языка
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white leading-tight tracking-tight">
            Как это работает
          </h2>
          <p className="text-lg text-slate-400 mt-4 max-w-xl mx-auto">
            Никаких сложных настроек. Просто книга — и два языка рядом.
          </p>
        </div>

        {/* Steps */}
        <div className="grid md:grid-cols-3 gap-6 lg:gap-8">
          {steps.map((step, index) => (
            <div
              key={step.number}
              className={`transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'}`}
              style={{ transitionDelay: `${index * 150}ms` }}
            >
              <div className="relative bg-[#111118] border border-white/8 rounded-3xl p-8 h-full group hover:border-white/15 transition-colors duration-300">
                {/* Number badge */}
                <div className="flex items-start justify-between mb-6">
                  <div className={`w-12 h-12 rounded-2xl ${step.bgColor} border ${step.borderColor} flex items-center justify-center ${step.textColor}`}>
                    {step.icon}
                  </div>
                  <span className={`text-4xl font-black ${step.textColor} opacity-30 font-mono`}>{step.number}</span>
                </div>

                <h3 className="text-xl font-bold text-white mb-3">{step.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed mb-6">{step.description}</p>

                {/* Formats or langs */}
                {step.formats && (
                  <div className="flex gap-2 flex-wrap">
                    {step.formats.map((fmt) => (
                      <span key={fmt} className={`text-xs font-semibold ${step.textColor} ${step.bgColor} border ${step.borderColor} px-3 py-1 rounded-lg`}>
                        {fmt}
                      </span>
                    ))}
                  </div>
                )}
                {step.langs && (
                  <div className="flex gap-2 flex-wrap">
                    {step.langs.map((lang) => (
                      <span key={lang} className={`text-xs font-semibold ${step.textColor} ${step.bgColor} border ${step.borderColor} px-3 py-1 rounded-lg`}>
                        {lang}
                      </span>
                    ))}
                  </div>
                )}
                {!step.formats && !step.langs && (
                  <div className="flex gap-2 flex-wrap">
                    {['Без зубрёжки', 'Живой контекст', 'В потоке'].map((tag) => (
                      <span key={tag} className={`text-xs font-semibold ${step.textColor} ${step.bgColor} border ${step.borderColor} px-3 py-1 rounded-lg`}>
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Connector arrow for non-last cards */}
                {index < steps.length - 1 && (
                  <div className="hidden md:block absolute -right-4 top-1/2 -translate-y-1/2 z-10">
                    <div className="w-8 h-8 bg-[#111118] border border-white/8 rounded-full flex items-center justify-center">
                      <svg className="w-3 h-3 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                      </svg>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
