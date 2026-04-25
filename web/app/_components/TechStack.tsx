const hardware = [
  { name: "AWS DeepRacer", icon: "🚗" },
  { name: "AWS DeepLens", icon: "📷" },
  { name: "ESP32", icon: "📡" },
  { name: "Leap Motion", icon: "✋" },
  { name: "Webcam (fallback)", icon: "🎥" },
];

const software = [
  { name: "PyTorch", icon: "🔥" },
  { name: "MediaPipe", icon: "👋" },
  { name: "OpenCV", icon: "👁" },
  { name: "MQTT / Mosquitto", icon: "📨" },
  { name: "Next.js", icon: "⚡" },
  { name: "NumPy", icon: "🔢" },
];

export default function TechStack() {
  return (
    <section id="tech" className="border-t border-zinc-800 bg-black px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <h2 className="mb-10 text-center font-mono text-sm font-bold tracking-widest text-cyan-500">
          TECH STACK
        </h2>

        <div className="grid grid-cols-1 gap-10 rounded-lg border border-zinc-800 bg-zinc-950 p-8 md:grid-cols-2 md:gap-12">
          <div>
            <h3 className="mb-5 font-mono text-xs font-bold tracking-widest text-zinc-400">
              HARDWARE
            </h3>
            <div className="flex flex-wrap gap-3">
              {hardware.map((item) => (
                <span
                  key={item.name}
                  className="flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-cyan-500/50 hover:bg-cyan-500/5 hover:text-cyan-300"
                >
                  <span>{item.icon}</span>
                  {item.name}
                </span>
              ))}
            </div>
          </div>

          <div className="md:border-l md:border-zinc-800 md:pl-12">
            <h3 className="mb-5 font-mono text-xs font-bold tracking-widest text-zinc-400">
              SOFTWARE
            </h3>
            <div className="flex flex-wrap gap-3">
              {software.map((item) => (
                <span
                  key={item.name}
                  className="flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-green-500/50 hover:bg-green-500/5 hover:text-green-300"
                >
                  <span>{item.icon}</span>
                  {item.name}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
