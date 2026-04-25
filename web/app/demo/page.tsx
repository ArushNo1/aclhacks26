import type { Metadata } from "next";
import SimDemo from "../_components/SimDemo";

export const metadata: Metadata = {
  title: "Ghost Racer — Live Demo",
  description: "Live simulation stream: hand control vs. behavioral clone.",
};

export default function DemoPage() {
  return (
    <main className="min-h-screen bg-black text-white">
      <SimDemo />
    </main>
  );
}
