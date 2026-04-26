import { CarIcon, HandIcon, NetworkIcon } from "./icons";
import type { ReactNode } from "react";

const steps = [
  {
    n: "01",
    title: "Drive",
    body: "Hand position controls steering and throttle. Pinch to brake. The system records every input alongside synced video frames.",
    visual: <DriveVisual />,
  },
  {
    n: "02",
    title: "Clone",
    body: "A behavioral cloning CNN trains on your session. It learns the way you take corners, where you brake, how aggressively you hold the line.",
    visual: <CloneVisual />,
  },
  {
    n: "03",
    title: "Race",
    body: "Your trained model drives the car autonomously. Two ghosts — trained by different humans — face off lap-for-lap on the same track.",
    visual: <RaceVisual />,
  },
];

export default function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="border-t border-[var(--color-border)] bg-[var(--color-bg)] px-5 py-24"
    >
      <div className="mx-auto max-w-6xl">
        <header className="mb-20 max-w-2xl">
          <span className="label">How it works</span>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">
            From hand gesture to autonomous lap
          </h2>
          <p className="mt-4 text-base text-[var(--color-text-muted)]">
            A short pipeline: capture human driving, train a model, hand the
            car back to the model. Three stages, one car.
          </p>
        </header>

        <div className="space-y-20 md:space-y-28">
          {steps.map((step, i) => (
            <Step key={step.n} step={step} reverse={i % 2 === 1} />
          ))}
        </div>
      </div>
    </section>
  );
}

function Step({
  step,
  reverse,
}: {
  step: { n: string; title: string; body: string; visual: ReactNode };
  reverse: boolean;
}) {
  return (
    <article className="grid grid-cols-1 items-center gap-10 md:grid-cols-2 md:gap-16">
      <div className={reverse ? "md:order-2" : "md:order-1"}>
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-sm text-[var(--color-accent-soft)]">
            {step.n}
          </span>
          <span aria-hidden className="h-px flex-1 bg-[var(--color-border)]" />
        </div>
        <h3 className="mt-4 text-2xl font-semibold tracking-tight text-[var(--color-text)] sm:text-3xl">
          {step.title}
        </h3>
        <p className="mt-4 text-base text-[var(--color-text-muted)]">
          {step.body}
        </p>
      </div>
      <div className={reverse ? "md:order-1" : "md:order-2"}>
        <div className="card relative aspect-[4/3] overflow-hidden p-6">
          {step.visual}
        </div>
      </div>
    </article>
  );
}

function DriveVisual() {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <div className="relative">
        <div
          aria-hidden
          className="absolute inset-0 -m-6 rounded-full bg-[var(--color-accent)]/8 blur-2xl"
        />
        <HandIcon className="relative h-32 w-32 text-[var(--color-accent-soft)]" />
        <div className="mt-6 grid grid-cols-2 gap-3 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-subtle)]">
          <div>X · steering</div>
          <div>Y · throttle</div>
          <div>Pinch · brake</div>
          <div>Z · gear</div>
        </div>
      </div>
    </div>
  );
}

function CloneVisual() {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <div className="relative">
        <div
          aria-hidden
          className="absolute inset-0 -m-6 rounded-full bg-[var(--color-accent)]/8 blur-2xl"
        />
        <NetworkIcon className="relative h-32 w-32 text-[var(--color-accent-soft)]" />
        <div className="mt-6 flex items-center justify-center gap-2 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-subtle)]">
          <span>frames</span>
          <span aria-hidden>→</span>
          <span>cnn</span>
          <span aria-hidden>→</span>
          <span className="text-[var(--color-accent-soft)]">controls</span>
        </div>
      </div>
    </div>
  );
}

function RaceVisual() {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center">
      <CarIcon className="h-32 w-32 text-[var(--color-accent-soft)]" />
      <svg
        aria-hidden
        viewBox="0 0 200 60"
        className="mt-6 w-full max-w-xs text-[var(--color-border-strong)]"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <path d="M10 30 Q 50 5 100 30 T 190 30" strokeDasharray="4 4" />
        <circle cx="40" cy="22" r="3" fill="var(--color-accent)" stroke="none" />
        <circle cx="120" cy="34" r="3" fill="var(--color-text-subtle)" stroke="none" />
      </svg>
    </div>
  );
}
