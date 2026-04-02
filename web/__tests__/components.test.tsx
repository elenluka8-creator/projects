import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import en from "../messages/en.json";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/en/upload",
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
}));
import { AppShell } from "../components/AppShell";
import { Container } from "../components/Container";
import { JobStatusBadge } from "../components/JobStatusBadge";

function IntlWrapper({ children }: { children: React.ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={en}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("Container", () => {
  it("renders children", () => {
    render(
      <Container>
        <p>hello</p>
      </Container>,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
});

describe("AppShell", () => {
  it("renders brand and footer", () => {
    render(
      <IntlWrapper>
        <AppShell>
          <p>content</p>
        </AppShell>
      </IntlWrapper>,
    );
    expect(screen.getByText("Unfolda")).toBeInTheDocument();
    expect(screen.getByText(/read deeper/i)).toBeInTheDocument();
    expect(screen.getByText("content")).toBeInTheDocument();
  });
});

describe("JobStatusBadge", () => {
  it("shows translated label for failed status", () => {
    render(
      <IntlWrapper>
        <JobStatusBadge status="failed" />
      </IntlWrapper>,
    );
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows raw status when unknown", () => {
    render(
      <IntlWrapper>
        <JobStatusBadge status="custom_state" />
      </IntlWrapper>,
    );
    expect(screen.getByText("custom_state")).toBeInTheDocument();
  });
});
