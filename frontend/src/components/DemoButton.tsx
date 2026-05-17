import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Play } from "lucide-react";
import { useAuth } from "@/lib/auth";

export default function DemoButton({
  className = "btn-primary",
  label = "Launch a live agent",
}: {
  className?: string;
  label?: string;
}) {
  const { authenticated, connect } = useAuth();
  const nav = useNavigate();
  const [clicked, setClicked] = useState(false);

  // Navigate ONLY after an explicit click (covers the post-Privy-connect
  // case too). Never auto-bounce off the landing page — a guest is always
  // "authenticated", which previously force-redirected Home → /dashboard.
  useEffect(() => {
    if (clicked && authenticated) nav("/dashboard");
  }, [clicked, authenticated, nav]);

  return (
    <button
      className={className}
      onClick={() => {
        setClicked(true);
        if (!authenticated) connect();
      }}
    >
      <Play className="h-4 w-4" />
      {label}
    </button>
  );
}
