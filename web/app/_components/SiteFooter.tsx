export default function SiteFooter() {
  return (
    <footer className="border-t border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 text-sm text-[var(--color-text-subtle)] sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <span aria-hidden className="block h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
          <span className="font-semibold text-[var(--color-text-muted)]">Ghost Racer</span>
          <span aria-hidden>·</span>
          <span>ACL Hacks 2026</span>
        </div>
        <div className="flex items-center gap-5">
          <a
            href="https://github.com"
            className="transition-colors hover:text-[var(--color-text)]"
          >
            GitHub
          </a>
          <a
            href="#how-it-works"
            className="transition-colors hover:text-[var(--color-text)]"
          >
            How it works
          </a>
          <a
            href="#race"
            className="transition-colors hover:text-[var(--color-text)]"
          >
            Race
          </a>
        </div>
      </div>
    </footer>
  );
}
