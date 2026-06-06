import { useState } from "react";
import IconSprite from "./icons/IconSprite";
import Topbar from "./components/Topbar";
import AuthModal from "./components/AuthModal";
import AccountSection from "./components/AccountSection";
import ChatPlanner from "./components/planner/ChatPlanner";
import ItineraryView from "./components/itinerary/ItineraryView";
import InsightsSection from "./components/insights/InsightsSection";

export default function App() {
  const [authOpen, setAuthOpen] = useState(false);
  const openLogin = () => setAuthOpen(true);

  return (
    <>
      <IconSprite />
      <Topbar onOpenLogin={openLogin} />
      <main>
        <ChatPlanner />
        <ItineraryView onOpenLogin={openLogin} />
        <AccountSection onOpenLogin={openLogin} />
        <InsightsSection />
      </main>
      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />
    </>
  );
}
