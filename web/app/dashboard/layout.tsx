import type { Metadata } from "next";
import { Orbitron, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import "./styles.css";

const orbitron = Orbitron({
  weight: ["400", "600", "700", "900"],
  subsets: ["latin"],
  variable: "--font-orbitron",
});

const jetbrainsMono = JetBrains_Mono({
  weight: ["400", "500"],
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
});

const spaceGrotesk = Space_Grotesk({
  weight: ["300", "400", "500", "600"],
  subsets: ["latin"],
  variable: "--font-space-grotesk",
});

export const metadata: Metadata = {
  title: "Mission Control — Ghost Racer",
  description: "Ghost Racer Mission Control Dashboard",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={`${orbitron.variable} ${jetbrainsMono.variable} ${spaceGrotesk.variable}`}
      style={{ position: "fixed", inset: 0, overflow: "hidden" }}
    >
      {children}
    </div>
  );
}
