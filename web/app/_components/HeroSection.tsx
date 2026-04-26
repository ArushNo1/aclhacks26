import Link from "next/link";
import { ArrowRightIcon } from "./icons";

export default function HeroSection() {
  return (
    <section className="relative isolate overflow-hidden">
      <div aria-hidden className="hero-glow absolute inset-0 -z-10" />
      <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-6xl flex-col items-start justify-center px-5 py-24">
        <span className="badge badge-accent mb-6">ACL Hacks 26</span>

        <h1 className="text-balance text-4xl font-extrabold leading-[1.05] tracking-tight text-[var(--color-text)] sm:text-5xl md:text-6xl">
          Control the car.{" "}
          <span className="text-[var(--color-accent-soft)]">
            Watch your ghost race.
          </span>
        </h1>

        <p className="mt-6 max-w-[60ch] text-lg leading-relaxed text-[var(--color-text-muted)]">
          Drive a 1/18 scale race car with hand gestures. A neural network
          learns your style. Then your AI ghost takes the wheel and races
          another driver&apos;s ghost on a real track.
        </p>

        <div className="mt-10 flex flex-wrap items-center gap-3">
          <Link href="#how-it-works" className="btn btn-primary">
            See how it works
            <ArrowRightIcon className="h-4 w-4" />
          </Link>
          <Link href="#race" className="btn btn-secondary">
            Watch the race
          </Link>
        </div>

        <div className="mt-16 flex items-center gap-8 text-sm text-[var(--color-text-subtle)]">
          <Stat label="Latency" value="< 50 ms" />
          <span aria-hidden className="h-8 w-px bg-[var(--color-border)]" />
          <Stat label="Track" value="Physical 1/18" />
          <span aria-hidden className="hidden h-8 w-px bg-[var(--color-border)] sm:block" />
          <Stat label="Model" value="Behavioral CNN" className="hidden sm:flex" />
        </div>
      </div>
    </section>
  );
}

function Stat({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={`flex flex-col ${className}`}>
      <span className="text-[0.7rem] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-subtle)]">
        {label}
      </span>
      <span className="font-mono text-sm text-[var(--color-text)]">
        {value}
      </span>
    </div>
  );
}
