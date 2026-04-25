import Navbar from "./_components/Navbar";
import HeroSection from "./_components/HeroSection";
import HowItWorks from "./_components/HowItWorks";
import TechStack from "./_components/TechStack";
import LiveDashboard from "./_components/LiveDashboard";
import Footer from "./_components/Footer";

export default function Home() {
  return (
    <main className="bg-black text-white">
      <Navbar />
      <HeroSection />
      <HowItWorks />
      <TechStack />
      <LiveDashboard />
      <Footer />
    </main>
  );
}
