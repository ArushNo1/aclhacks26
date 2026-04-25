export default function HeroSection() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-black px-4 text-center">
      <div className="hero-grid absolute inset-0" />
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black" />

      <div className="relative z-10 flex flex-col items-center gap-8">
        <div className="flex flex-wrap justify-center gap-3">
          <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-4 py-1 font-mono text-xs font-bold tracking-widest text-cyan-400">
            ACL HACKS 26
          </span>
          <span className="rounded-full border border-green-500/40 bg-green-500/10 px-4 py-1 font-mono text-xs font-bold tracking-widest text-green-400">
            BEHAVIORAL CLONING
          </span>
        </div>

        <h1 className="glow-title font-mono text-7xl font-black tracking-tighter text-white sm:text-8xl md:text-9xl">
          GHOST
          <br />
          RACER
        </h1>

        <p className="max-w-xl text-lg leading-relaxed text-zinc-400">
          Control a real car with your hands.
          <br />
          Your ghost races on.
        </p>

        <div className="flex flex-wrap justify-center gap-6 font-mono text-xs text-zinc-600">
          <span>✋ HAND TRACKING</span>
          <span>→</span>
          <span>🧠 BEHAVIORAL CLONE</span>
          <span>→</span>
          <span>🏎 AUTONOMOUS RACE</span>
        </div>
      </div>

      <div className="bounce-arrow absolute bottom-8 left-1/2 font-mono text-2xl text-cyan-500">
        ↓
      </div>
    </section>
  );
}
