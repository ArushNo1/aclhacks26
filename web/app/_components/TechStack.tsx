import type { ComponentType, SVGProps } from "react";
import {
  AntennaIcon,
  BoltIcon,
  CameraIcon,
  CarIcon,
  ChipIcon,
  EyeIcon,
  FlameIcon,
  HandIcon,
  HashIcon,
  MailIcon,
} from "./icons";

type Item = {
  name: string;
  desc: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
};

const hardware: Item[] = [
  { name: "AWS DeepRacer", desc: "1/18 scale physical race car", Icon: CarIcon },
  { name: "AWS DeepLens", desc: "Onboard camera + inference", Icon: CameraIcon },
  { name: "ESP32", desc: "Wireless control bridge", Icon: AntennaIcon },
  { name: "Leap Motion", desc: "Hand tracking sensor", Icon: HandIcon },
  { name: "Webcam fallback", desc: "MediaPipe-based hand input", Icon: CameraIcon },
];

const software: Item[] = [
  { name: "PyTorch", desc: "CNN training and inference", Icon: FlameIcon },
  { name: "MediaPipe", desc: "Real-time landmark detection", Icon: HandIcon },
  { name: "OpenCV", desc: "Frame capture and preprocessing", Icon: EyeIcon },
  { name: "MQTT", desc: "Low-latency control transport", Icon: MailIcon },
  { name: "Next.js", desc: "Race dashboard and visuals", Icon: BoltIcon },
  { name: "NumPy", desc: "Data pipeline and telemetry", Icon: HashIcon },
  { name: "ChipKit", desc: "Microcontroller firmware", Icon: ChipIcon },
];

export default function TechStack() {
  return (
    <section
      id="tech"
      className="border-t border-[var(--color-border)] bg-[var(--color-bg)] px-5 py-24"
    >
      <div className="mx-auto max-w-6xl">
        <header className="mb-16 max-w-2xl">
          <span className="label">Tech stack</span>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">
            What&apos;s under the hood
          </h2>
          <p className="mt-4 text-base text-[var(--color-text-muted)]">
            Off-the-shelf hardware, open-source ML. Nothing custom-fabricated —
            the trick is the pipeline.
          </p>
        </header>

        <div className="grid grid-cols-1 gap-x-12 gap-y-10 md:grid-cols-2">
          <Column title="Hardware" items={hardware} />
          <Column title="Software" items={software} />
        </div>
      </div>
    </section>
  );
}

function Column({ title, items }: { title: string; items: Item[] }) {
  return (
    <div>
      <h3 className="label mb-6">{title}</h3>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-1 lg:grid-cols-2">
        {items.map(({ name, desc, Icon }) => (
          <li
            key={name}
            className="card group flex items-start gap-3 p-4 transition-colors hover:border-[var(--color-accent-deep)]"
          >
            <span
              aria-hidden
              className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--color-surface-2)] text-[var(--color-accent-soft)]"
            >
              <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-[var(--color-text)]">
                {name}
              </div>
              <div className="mt-0.5 text-xs leading-relaxed text-[var(--color-text-muted)]">
                {desc}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
