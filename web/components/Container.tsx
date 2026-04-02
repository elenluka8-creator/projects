import type { ReactNode } from "react";

type ContainerProps = {
  children: ReactNode;
  /** "content" = 680px, "wide" = 1024px. Defaults to "content". */
  size?: "content" | "wide";
  className?: string;
};

/**
 * Centered layout container with horizontal padding.
 * Uses brand max-width values from tailwind.config.ts.
 */
export function Container({
  children,
  size = "content",
  className = "",
}: ContainerProps) {
  const maxW = size === "wide" ? "max-w-wide" : "max-w-content";
  return (
    <div className={`mx-auto w-full px-4 sm:px-6 ${maxW} ${className}`}>
      {children}
    </div>
  );
}
