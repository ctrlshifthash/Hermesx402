import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { AuthProvider } from "./lib/auth";
import "./index.css";

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

// Never show a silent blank page again — surface the real error on screen.
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { err: Error | null }
> {
  state = { err: null as Error | null };
  static getDerivedStateFromError(err: Error) {
    return { err };
  }
  componentDidCatch(err: Error, info: unknown) {
    console.error("App crashed:", err, info);
  }
  render() {
    if (this.state.err)
      return (
        <div style={{ padding: 24, fontFamily: "monospace", color: "#1A1712" }}>
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>
            App error (this is the real cause):
          </h1>
          <pre style={{ whiteSpace: "pre-wrap", marginTop: 12 }}>
            {String(this.state.err?.stack || this.state.err)}
          </pre>
          <button
            onClick={() => location.reload()}
            style={{ marginTop: 16, padding: "8px 16px", border: "1px solid #1A1712" }}
          >
            Reload
          </button>
        </div>
      );
    return this.props.children;
  }
}

window.addEventListener("unhandledrejection", (e) =>
  console.error("Unhandled promise rejection:", e.reason)
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={qc}>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
