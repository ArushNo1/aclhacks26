export default function Footer() {
  return (
    <footer className="border-t border-zinc-800 bg-black px-4 py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
        <span className="font-mono text-xs font-black tracking-widest text-zinc-600">
          GHOST RACER
        </span>
        <span className="font-mono text-xs text-zinc-700">
          ACL HACKS 26 — Behavioral Cloning Demo
        </span>
        <span className="font-mono text-xs text-zinc-700">2026</span>
      </div>
    </footer>
  );
}
