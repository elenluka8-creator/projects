import Navbar from './components/Navbar'
import HeroSection from './components/HeroSection'
import PainSolutionSection from './components/PainSolutionSection'
import HowItWorksSection from './components/HowItWorksSection'
import FeaturesSection from './components/FeaturesSection'
import AudienceSection from './components/AudienceSection'
import FooterCTASection from './components/FooterCTASection'

export default function App() {
  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white overflow-x-hidden">
      <Navbar />
      <main>
        <HeroSection />
        <PainSolutionSection />
        <HowItWorksSection />
        <FeaturesSection />
        <AudienceSection />
        <FooterCTASection />
      </main>
    </div>
  )
}
