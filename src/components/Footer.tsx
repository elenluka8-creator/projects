"use client";

export function Footer() {
  return (
    <footer className="border-t border-white/5 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent to-blue flex items-center justify-center">
              <span className="text-white font-bold text-xs">U</span>
            </div>
            <span className="text-sm font-semibold text-foreground">
              Unfolda
            </span>
          </div>

          <div className="flex items-center gap-6 text-sm text-muted">
            <a
              href="https://www.unfolda.ai/en/terms"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              Условия использования
            </a>
            <a
              href="https://www.unfolda.ai/en/privacy"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              Конфиденциальность
            </a>
            <a
              href="mailto:support@unfolda.ai"
              className="hover:text-foreground transition-colors"
            >
              Поддержка
            </a>
          </div>

          <p className="text-xs text-muted/60">
            &copy; {new Date().getFullYear()} Unfolda. Все права защищены.
          </p>
        </div>
      </div>
    </footer>
  );
}
