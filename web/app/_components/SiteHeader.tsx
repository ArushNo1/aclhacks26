import Link from "next/link";

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-bg)]/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
        <Link
          href="/"
          className="flex items-center gap-2 text-[15px] font-bold tracking-tight text-[var(--color-text)]"
        >
          <span aria-hidden className="block h-2 w-2 rounded-full bg-[var(--color-accent)]" />
          <span>
            Ghost <span className="text-[var(--color-accent-soft)]">Racer</span>
          </span>
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-7 md:flex">
          <Link
            href="#how-it-works"
            className="text-sm text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
          >
            How it works
          </Link>
          <Link
            href="#tech"
            className="text-sm text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
          >
            Tech stack
          </Link>
          <Link
            href="#race"
            className="text-sm text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
          >
            Race
          </Link>
          <Link
            href="/dashboard"
            className="text-sm text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
          >
            Mission control
          </Link>
        </nav>

        <Link href="/dashboard" className="btn btn-primary h-9 px-4 text-sm">
          Open dashboard
        </Link>
      </div>
    </header>
  );
}
