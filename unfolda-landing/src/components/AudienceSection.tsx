import { useScrollAnimation } from '../hooks/useScrollAnimation'

const audiences = [
  {
    emoji: '✈️',
    title: 'Для экспатов',
    subtitle: 'Жизнь в новой стране',
    description: 'Быстрое погружение в языковую среду Сербии или англоязычного мира. Учите язык через литературу, которую вам интересно читать.',
    tags: ['Сербский для жизни', 'Английский для работы', 'Быстрая адаптация'],
    color: 'violet',
  },
  {
    emoji: '🎓',
    title: 'Для студентов и профи',
    subtitle: 'Профессиональный рост',
    description: 'Чтение профессиональной литературы без потери смыслов. Юридические документы, технические книги, академические статьи — всё в контексте.',
    tags: ['Профессиональная лексика', 'Академический язык', 'Без потери смысла'],
    color: 'indigo',
  },
  {
    emoji: '📚',
    title: 'Для книголюбов',
    subtitle: 'Удовольствие без вины',
    description: 'Наслаждение языком оригинала без чувства вины за «подглядывание» в перевод. Это не слабость — это метод.',
    tags: ['Оригинальные тексты', 'Без чувства вины', 'Поток чтения'],
    color: 'purple',
  },
]

const colorMap: Record<string, { icon: string; tag: string; dot: string }> = {
  violet: {
    icon: 'bg-violet-500/10 border-violet-500/20',
    tag: 'bg-violet-500/5 border-violet-500/15 text-violet-400',
    dot: 'bg-violet-400',
  },
  indigo: {
    icon: 'bg-indigo-500/10 border-indigo-500/20',
    tag: 'bg-indigo-500/5 border-indigo-500/15 text-indigo-400',
    dot: 'bg-indigo-400',
  },
  purple: {
    icon: 'bg-purple-500/10 border-purple-500/20',
    tag: 'bg-purple-500/5 border-purple-500/15 text-purple-400',
    dot: 'bg-purple-400',
  },
}

export default function AudienceSection() {
  const { ref, isVisible } = useScrollAnimation()

  return (
    <section
      id="audience"
      ref={ref}
      className="relative py-24 px-4 sm:px-6 lg:px-8"
    >
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-px h-32 bg-gradient-to-b from-transparent via-violet-500/20 to-transparent" />
        <div className="absolute bottom-1/3 right-0 w-[300px] h-[300px] bg-purple-600/8 rounded-full blur-[80px]" />
      </div>

      <div className="max-w-6xl mx-auto relative">
        {/* Header */}
        <div
          className={`text-center mb-16 transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
        >
          <span className="inline-flex items-center gap-2 bg-purple-500/10 border border-purple-500/20 text-purple-300 text-sm font-medium px-4 py-1.5 rounded-full mb-6">
            👥 Для кого Unfolda
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white leading-tight tracking-tight">
            Узнайте себя
          </h2>
          <p className="text-lg text-slate-400 mt-4 max-w-xl mx-auto">
            Unfolda создан для тех, кто хочет читать, а не зубрить.
          </p>
        </div>

        {/* Audience cards */}
        <div className="grid md:grid-cols-3 gap-6 lg:gap-8 mb-16">
          {audiences.map((audience, index) => {
            const colors = colorMap[audience.color]
            return (
              <div
                key={audience.title}
                className={`transition-all duration-700 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'}`}
                style={{ transitionDelay: `${index * 150}ms` }}
              >
                <div className="bg-[#111118] border border-white/8 rounded-3xl p-8 h-full group hover:border-white/15 hover:-translate-y-1 transition-all duration-300">
                  {/* Emoji icon */}
                  <div className={`w-14 h-14 rounded-2xl ${colors.icon} border flex items-center justify-center text-2xl mb-6`}>
                    {audience.emoji}
                  </div>

                  <div className="mb-1">
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{audience.subtitle}</span>
                  </div>
                  <h3 className="text-xl font-bold text-white mb-3">{audience.title}</h3>
                  <p className="text-slate-400 text-sm leading-relaxed mb-6">{audience.description}</p>

                  {/* Tags */}
                  <div className="flex flex-wrap gap-2">
                    {audience.tags.map((tag) => (
                      <span
                        key={tag}
                        className={`text-xs font-medium ${colors.tag} border px-3 py-1 rounded-lg`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Testimonials / Quote banner */}
        <div
          className={`transition-all duration-700 delay-500 ${isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
        >
          <div className="relative bg-gradient-to-br from-violet-900/30 to-indigo-900/30 border border-violet-500/20 rounded-3xl p-8 lg:p-12 overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-violet-500/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute bottom-0 left-0 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

            <div className="relative text-center">
              <div className="text-5xl mb-6 opacity-30 font-serif text-violet-300">"</div>
              <p className="text-xl lg:text-2xl text-white font-medium leading-relaxed max-w-3xl mx-auto mb-6">
                Я жил в Белграде три месяца и не мог связать двух слов по-сербски. С Unfolda я начал читать сербские книги с переводом — и через месяц уже общался с соседями.
              </p>
              <div className="flex items-center justify-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm">
                  АК
                </div>
                <div className="text-left">
                  <p className="text-white font-semibold text-sm">Алексей К.</p>
                  <p className="text-slate-500 text-xs">Экспат в Белграде · Software Engineer</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
