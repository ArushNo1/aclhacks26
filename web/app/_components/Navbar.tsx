const links = [
  { label: "How It Works", href: "#how-it-works" },
  { label: "Tech", href: "#tech" },
  { label: "Dashboard", href: "#dashboard" },
];

export default function Navbar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-zinc-800/60 bg-black/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <a href="#home" className="font-mono text-sm font-black tracking-widest text-white hover:text-cyan-400 transition-colors">
          GHOST RACER
        </a>
        <nav className="flex items-center gap-6">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="font-mono text-xs font-bold tracking-widest text-zinc-500 transition-colors hover:text-cyan-400"
            >
              {link.label}
            </a>
          ))}
          <a
            href="/demo"
            className="rounded-full border border-cyan-500/50 bg-cyan-500/10 px-4 py-1 font-mono text-xs font-bold tracking-widest text-cyan-400 transition-colors hover:bg-cyan-500/20"
          >
            ▶ DEMO
          </a>
        </nav>
      </div>
    </header>
  );
}
