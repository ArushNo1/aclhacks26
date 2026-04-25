const steps = [
  {
    act: "ACT 01",
    title: "DRIVE",
    icon: "✋",
    description:
      "You control the car with your hand position. X-axis = steering, Y-axis = throttle. Pinch to brake. Every move is recorded.",
  },
  {
    act: "ACT 02",
    title: "CLONE",
    icon: "🧠",
    description:
      "A behavioral cloning neural network (PyTorch CNN) trains on your driving data and learns your exact driving style.",
  },
  {
    act: "ACT 03",
    title: "RACE",
    icon: "🏎",
    description:
      "Your AI ghost drives autonomously. Two ghosts trained by different humans race each other on the physical track.",
  },
];

export default function HowItWorks() {
  return (
    <section className="bg-black px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <h2 className="mb-16 text-center font-mono text-sm font-bold tracking-widest text-cyan-500">
          HOW IT WORKS
        </h2>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {steps.map((step, i) => (
            <div key={step.act} className="relative">
              {i < steps.length - 1 && (
                <div className="absolute right-0 top-1/2 z-10 hidden -translate-y-1/2 translate-x-1/2 font-mono text-2xl text-cyan-800 md:block">
                  →
                </div>
              )}
              <div className="h-full rounded-lg border border-zinc-800 bg-zinc-950 p-8 transition-colors hover:border-cyan-500/30">
                <div className="mb-3 font-mono text-xs font-bold tracking-widest text-cyan-500">
                  {step.act}
                </div>
                <div className="mb-4 text-5xl">{step.icon}</div>
                <h3 className="mb-3 font-mono text-xl font-black text-white">
                  {step.title}
                </h3>
                <p className="text-sm leading-relaxed text-zinc-500">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
