"use client";

export function PhoneMockup() {
  return (
    <div className="phone-mockup w-[280px] sm:w-[320px] animate-float">
      <div className="flex justify-center pt-3 pb-2">
        <div className="w-20 h-1.5 rounded-full bg-white/10" />
      </div>

      <div className="px-4 pb-2">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-muted">Unfolda Reader</span>
          <div className="flex gap-1">
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/20 text-accent-light">
              EN
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue/20 text-blue">
              RU
            </span>
          </div>
        </div>
      </div>

      <div className="px-4 space-y-3 pb-6">
        <div className="rounded-xl bg-accent/5 border border-accent/10 p-3">
          <p className="text-xs leading-relaxed text-foreground/90">
            It was a bright cold day in April, and the clocks were striking
            thirteen. Winston Smith, his chin nuzzled into his breast in an
            effort to escape the vile wind, slipped quickly through the glass
            doors of Victory Mansions.
          </p>
        </div>

        <div className="flex justify-center">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            className="text-muted/40"
          >
            <path
              d="M8 3v10m0 0l-3-3m3 3l3-3"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        <div className="rounded-xl bg-blue/5 border border-blue/10 p-3">
          <p className="text-xs leading-relaxed text-foreground/90">
            Был яркий холодный апрельский день, и часы пробили тринадцать.
            Уинстон Смит, прижав подбородок к груди, чтобы спастись от
            пронизывающего ветра, быстро проскользнул сквозь стеклянные двери
            жилого дома «Победа».
          </p>
        </div>

        <div className="rounded-xl bg-accent/5 border border-accent/10 p-3">
          <p className="text-xs leading-relaxed text-foreground/90">
            The hallway smelt of boiled cabbage and old rag mats. At one end of
            it a coloured poster, too large for indoor display, had been tacked
            to the wall.
          </p>
        </div>

        <div className="flex justify-center">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            className="text-muted/40"
          >
            <path
              d="M8 3v10m0 0l-3-3m3 3l3-3"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        <div className="rounded-xl bg-blue/5 border border-blue/10 p-3">
          <p className="text-xs leading-relaxed text-foreground/90">
            В подъезде пахло варёной капустой и старыми половиками. На стене, у
            входа, был приколот цветной плакат, слишком большой для помещения.
          </p>
        </div>
      </div>

      <div className="flex justify-center pb-3">
        <div className="w-24 h-1 rounded-full bg-white/10" />
      </div>
    </div>
  );
}
