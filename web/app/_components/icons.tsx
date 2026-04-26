import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
  "aria-hidden": true,
};

export function HandIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M9 11V5.5a1.5 1.5 0 1 1 3 0V11" />
      <path d="M12 11V4.5a1.5 1.5 0 1 1 3 0V11" />
      <path d="M15 11V6a1.5 1.5 0 1 1 3 0v8" />
      <path d="M9 11V8a1.5 1.5 0 1 0-3 0v7c0 3.5 2.5 6 6 6h.5c3.5 0 6.5-2.5 6.5-7" />
    </svg>
  );
}

export function NetworkIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="5" cy="6" r="1.6" />
      <circle cx="5" cy="12" r="1.6" />
      <circle cx="5" cy="18" r="1.6" />
      <circle cx="12" cy="9" r="1.6" />
      <circle cx="12" cy="15" r="1.6" />
      <circle cx="19" cy="12" r="1.6" />
      <path d="M6.4 6.5 10.6 8.5M6.4 11.7 10.6 9.4M6.4 12.3 10.6 14.6M6.4 17.5 10.6 15.5" />
      <path d="M13.4 9.4 17.6 11.4M13.4 14.6 17.6 12.6" />
    </svg>
  );
}

export function CarIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M3 14.5h18" />
      <path d="M5 14.5 6.5 9.5a2 2 0 0 1 1.9-1.5h7.2a2 2 0 0 1 1.9 1.5L19 14.5" />
      <path d="M3.5 14.5v3a1 1 0 0 0 1 1h1.5a1 1 0 0 0 1-1v-1.5" />
      <path d="M17 16v1.5a1 1 0 0 0 1 1h1.5a1 1 0 0 0 1-1v-3" />
      <circle cx="7.5" cy="15.5" r="1.6" />
      <circle cx="16.5" cy="15.5" r="1.6" />
    </svg>
  );
}

export function CameraIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="3" y="6.5" width="18" height="12" rx="2" />
      <circle cx="12" cy="12.5" r="3.2" />
      <path d="M8 6.5 9 4.5h6L16 6.5" />
    </svg>
  );
}

export function ChipIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="6" y="6" width="12" height="12" rx="1.5" />
      <rect x="9" y="9" width="6" height="6" rx="0.5" />
      <path d="M9 3v3M12 3v3M15 3v3M9 18v3M12 18v3M15 18v3M3 9h3M3 12h3M3 15h3M18 9h3M18 12h3M18 15h3" />
    </svg>
  );
}

export function AntennaIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M5 6c2 2 2 10 0 12" />
      <path d="M8 8c1 1.2 1 6.8 0 8" />
      <path d="M19 6c-2 2-2 10 0 12" />
      <path d="M16 8c-1 1.2-1 6.8 0 8" />
      <circle cx="12" cy="12" r="1.5" />
      <path d="M12 13.5V21" />
    </svg>
  );
}

export function FlameIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3c2 3 5 5 5 9a5 5 0 0 1-10 0c0-2 1-3 2-4-.2 1.8 1 2.5 1.8 2 .2-3 .8-5 1.2-7Z" />
    </svg>
  );
}

export function EyeIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M2.5 12C4.5 7.5 8 5 12 5s7.5 2.5 9.5 7c-2 4.5-5.5 7-9.5 7s-7.5-2.5-9.5-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export function MailIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="3" y="6" width="18" height="12" rx="2" />
      <path d="M3.5 7.5 12 13l8.5-5.5" />
    </svg>
  );
}

export function BoltIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M13 3 5 13.5h6L10 21l8-10.5h-6L13 3Z" />
    </svg>
  );
}

export function HashIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M5 9h15M4 15h15M10 4 8 20M16 4l-2 16" />
    </svg>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}
