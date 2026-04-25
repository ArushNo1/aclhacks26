import HeroSection from "./_components/HeroSection";
import HowItWorks from "./_components/HowItWorks";
import TechStack from "./_components/TechStack";
import LiveDashboard from "./_components/LiveDashboard";

export default function Home() {
  return (
    <main className="bg-black text-white">
      <HeroSection />
      <HowItWorks />
      <TechStack />
      <LiveDashboard />
    </main>
  );
}
