import { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui";
import { getSolanaErr } from "@/lib/auth";

function SolanaDiag() {
  const [err, setErr] = useState("");
  useEffect(() => {
    const t = setInterval(() => setErr(getSolanaErr()), 1500);
    return () => clearInterval(t);
  }, []);
  if (!err) return null;
  return (
    <div
      style={{
        position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 9999,
        background: "#B3261E", color: "#fff", fontFamily: "monospace",
        fontSize: 12, padding: "8px 14px", maxHeight: 160, overflow: "auto",
      }}
    >
      <b>SOLANA CONNECTOR FAILED (this is why Phantom → download):</b>
      <br />
      {err}
    </div>
  );
}
import Shell from "@/components/Shell";
import RequireWallet from "@/components/RequireWallet";
import Landing from "@/pages/Landing";
import Dashboard from "@/pages/Dashboard";
import Agents from "@/pages/Agents";
import Runs from "@/pages/Runs";
import RunDetail from "@/pages/RunDetail";
import Schedules from "@/pages/Schedules";
import Payments from "@/pages/Payments";
import Calls from "@/pages/Calls";
import Settings from "@/pages/Settings";

const gated = (el: JSX.Element) => <RequireWallet>{el}</RequireWallet>;

export default function App() {
  return (
    <>
      <Toaster />
      <SolanaDiag />
      <Routes>
        {/* Home stays the landing page (its own marketing nav). */}
        <Route path="/" element={<Landing />} />

        {/* The app: shared shell with the tab nav + wallet control. */}
        <Route element={<Shell />}>
          <Route path="/dashboard" element={gated(<Dashboard />)} />
          <Route path="/agents" element={gated(<Agents />)} />
          <Route path="/runs" element={gated(<Runs />)} />
          <Route path="/runs/:id" element={gated(<RunDetail />)} />
          <Route path="/schedules" element={gated(<Schedules />)} />
          <Route path="/payments" element={gated(<Payments />)} />
          <Route path="/calls" element={gated(<Calls />)} />
          <Route path="/budgets" element={gated(<Settings />)} />
        </Route>

        {/* legacy paths */}
        <Route path="/app" element={<Navigate to="/dashboard" replace />} />
        <Route path="/app/*" element={<Navigate to="/dashboard" replace />} />
        <Route path="/auth" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
