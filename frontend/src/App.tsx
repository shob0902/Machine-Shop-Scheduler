import { BrowserRouter, Routes, Route } from "react-router-dom";
import { StrategyProvider } from "./hooks/useStrategy";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Schedule from "./pages/Schedule";
import Orders from "./pages/Orders";
import Machines from "./pages/Machines";
import Disruptions from "./pages/Disruptions";
import StrategyComparison from "./pages/StrategyComparison";
import CostAnalysis from "./pages/CostAnalysis";

export default function App() {
  return (
    <StrategyProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/schedule" element={<Schedule />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/machines" element={<Machines />} />
            <Route path="/disruptions" element={<Disruptions />} />
            <Route path="/strategies" element={<StrategyComparison />} />
            <Route path="/costs" element={<CostAnalysis />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </StrategyProvider>
  );
}
