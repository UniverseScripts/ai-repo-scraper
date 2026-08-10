"use client";

import { useState } from "react";
import Link from "next/link";

export default function Page() {
  const [copied, setCopied] = useState(false);
  const [flash, setFlash] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(
      `curl -X GET "https://agentrisk-daas.onrender.com/api/v1/analytics/package-risk/npm/react" \\\n-H "X-API-Key: YOUR_API_KEY"`
    );
    setCopied(true);
    setFlash(true);
    setTimeout(() => setFlash(false), 150);
  };

  return (
    <main className="min-h-screen bg-trueblack text-sterilewhite flex flex-col font-sans uppercase tracking-widest text-sm w-full">
      
      {/* 0. TOP NAVIGATION HEADER (FULL-BLEED) */}
      <header className="w-full border-b border-zinc-900 bg-trueblack py-4 px-6 sm:px-10 lg:px-16 xl:px-24">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between font-mono text-xs">
          <Link href="/" className="flex items-center gap-3 font-bold text-crtgreen text-sm tracking-wider">
            <span className="h-2.5 w-2.5 bg-crtgreen rounded-full animate-pulse"></span>
            AGENTRISK // DAAS CORE
          </Link>
          <div className="hidden md:flex items-center gap-8 text-zinc-400">
            <Link href="/docs" className="hover:text-crtgreen transition-colors">DOCS</Link>
            <Link href="/policies" className="hover:text-crtgreen transition-colors">GOVERNANCE</Link>
            <Link href="/terms" className="hover:text-crtgreen transition-colors">TERMS</Link>
            <a 
              href="https://asteriostech07.lemonsqueezy.com/checkout/buy/a3dc2366-b80f-4c18-920b-2f608b7a063e"
              className="border border-crtgreen text-crtgreen px-4 py-2 hover:bg-crtgreen hover:text-black font-bold transition-none"
            >
              PROVISION ACCESS
            </a>
          </div>
        </div>
      </header>

      {/* 1. THE HERO PROTOCOL (FULL-BLEED) */}
      <section className="w-full border-b border-zinc-900 py-12 lg:py-20 px-6 sm:px-10 lg:px-16 xl:px-24 animate-reveal">
        <div className="max-w-[1600px] mx-auto">
          <pre className="text-crtgreen text-xs md:text-sm whitespace-pre border-none font-bold mb-8 font-mono overflow-x-auto">
{`    ___  ___  ___  ___       ___   _____  __ 
   /   |/   |/   |/   |     /   | /  _  \\/ / 
  / /| / /| / /| / /| |    / /| | | | / / /  
 / /_// /_// /_// /_| |   / /_| | | |/ / /___
/_/  /_/  /_/  /_/  |_|  /_/  |_| |___/_____/

STATUS: ACTIVE (REV 3.0 CATALOG-WIDE)
NODE: EDGE INFRASTRUCTURE DAAS
ENCRYPTION: HMAC-SHA256 HMAC VERIFIED`}
          </pre>
          <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-black mb-4 tracking-tight">
            Maintainer &amp; Dormancy Risk Signal DaaS
            <span className="blinking-cursor"></span>
          </h1>
          <p className="text-zinc-400 max-w-3xl leading-relaxed mt-6 lowercase normal-case tracking-normal text-base md:text-lg font-sans">
            On-demand maintainer concentration (MCI), dormancy/reactivation (DRI), anomalous activity (ASI), and typosquatting detection.
            Sourced live from public registry metadata across the AI agent supply chain (MCP, npm, PyPI).
            No CVEs, no static code analysis. Just the raw risk matrix.
          </p>
        </div>
      </section>

      {/* 2. THE INTEGRATION LEDGER (FULL-BLEED) */}
      <section className="w-full border-b border-zinc-900 py-12 lg:py-16 px-6 sm:px-10 lg:px-16 xl:px-24 animate-reveal delay-100 bg-zinc-950/20">
        <div className="max-w-[1600px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
          
          <div className="border border-zinc-900 p-6 md:p-10 relative flex flex-col bg-black">
            <h2 className="text-xl font-bold mb-6 text-crtgreen border-b border-zinc-900 pb-3 font-mono">REQUEST ARBITRAGE</h2>
            <div className={`relative group border border-zinc-900 bg-zinc-950 p-6 flex-1 transition-none ${flash ? 'animate-flash' : ''}`}>
              <button 
                onClick={copyToClipboard}
                aria-label="Copy cURL command to clipboard"
                className="absolute top-3 right-3 bg-zinc-900 border border-zinc-800 px-3 py-1 text-xs text-crtgreen uppercase hover:bg-crtgreen hover:text-black transition-none cursor-pointer font-bold font-mono"
              >
                {copied ? "[COPIED]" : "[COPY]"}
              </button>
              <pre className="text-zinc-300 text-xs md:text-sm overflow-x-auto mt-2 font-mono leading-relaxed">
{`curl -X GET \\
"https://agentrisk-daas.onrender.com/api/v1/analytics/package-risk/npm/@modelcontextprotocol/sdk" \\
-H "X-API-Key: YOUR_API_KEY"`}
              </pre>
            </div>
          </div>

          <div className="border border-zinc-900 p-6 md:p-10 flex flex-col bg-black">
            <h2 className="text-xl font-bold mb-6 text-zinc-500 border-b border-zinc-900 pb-3 font-mono">
              RESPONSE PAYLOAD <span className="text-amber-400 text-xs">[ILLUSTRATIVE]</span>
            </h2>
            <pre className="border border-zinc-900 bg-zinc-950 p-6 text-xs md:text-sm overflow-x-auto text-zinc-400 font-mono flex-1 leading-relaxed">
{`{
  "package_name": "npm/example-mcp-server",
  "timestamp": "2026-07-27T18:50:00Z",
  "maintainer_concentration_index": 10.0,
  "dormancy_reactivation_index": "insufficient data",
  "anomalous_spike_index": 8.0,
  "maintainer_count": 1,
  "single_maintainer_flag": true,
  "days_since_last_publish": 2,
  "publish_cadence_variance": null,
  "fork_spike_ratio": 3.5
}`}
            </pre>
          </div>

        </div>
      </section>

      {/* 3. TIME-SERIES TELEMETRY & TYPOSQUAT LEDGER (FULL-BLEED) */}
      <section className="w-full border-b border-zinc-900 py-12 lg:py-16 px-6 sm:px-10 lg:px-16 xl:px-24 bg-black animate-reveal delay-150">
        <div className="max-w-[1600px] mx-auto">
          <h2 className="text-xl font-bold mb-8 text-crtgreen border-b border-zinc-900 pb-3 font-mono">HISTORICAL TELEMETRY &amp; TYPOSQUAT GUARD</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
            
            <div className="border border-zinc-900 p-6 md:p-8 bg-zinc-950 font-mono text-xs flex flex-col justify-between">
              <div>
                <p className="text-zinc-500 mb-3 tracking-widest">GET /api/v1/package-risk/{`{package_name}`}/history?limit=30</p>
                <p className="text-amber-400 mb-3 tracking-widest text-[11px]">[ EXAMPLE RESPONSE SHAPE — NOT LIVE DATA ]</p>
                <pre className="text-zinc-400 bg-black p-5 border border-zinc-900 overflow-x-auto text-xs leading-relaxed">
{`[
  {
    "package_name": "npm/<name>",
    "timestamp": "<iso-8601>",
    "maintainer_concentration_index": <float | "insufficient data">,
    "dormancy_reactivation_index":    <float | "insufficient data">,
    "anomalous_spike_index":          <float | "insufficient data">,
    "maintainer_count": <int | null>,
    "days_since_last_publish": <int | null>
  }
  // newest first, one snapshot per ingest cycle
]`}
                </pre>
              </div>
              <p className="text-zinc-400 text-xs mt-6 leading-relaxed normal-case font-sans">
                One snapshot is retained per ingest cycle. <code className="text-crtgreen">limit</code> accepts 1&ndash;100 and defaults to 30.
                Any index whose inputs are unavailable returns <code className="text-crtgreen">&quot;insufficient data&quot;</code> rather than a substituted value.
              </p>
            </div>

            <div className="border border-zinc-900 p-6 md:p-8 bg-zinc-950 font-mono text-xs flex flex-col justify-between">
              <div>
                <p className="text-zinc-500 mb-3 tracking-widest">SLOPSQUATTING / TYPOSQUAT DETECTOR</p>
                <pre className="text-amber-400 bg-black p-5 border border-zinc-900 overflow-x-auto text-xs leading-relaxed">
{`{
  "detail": "Package identity 'npm/reaact' does not exist in registry.",
  "status": "not_found",
  "possible_typosquat_of": "npm/react",
  "similarity": 0.91
}`}
                </pre>
              </div>
              <p className="text-zinc-400 text-xs mt-6 leading-relaxed normal-case font-sans">
                Calculates edit distance against known registry targets to flag hallucinated dependencies propagated by LLM agents.
              </p>
            </div>

          </div>
        </div>
      </section>

      {/* 4. THE FINANCIAL GATEWAY (FULL-BLEED) */}
      <section className="w-full py-16 lg:py-24 px-6 sm:px-10 lg:px-16 xl:px-24 animate-reveal delay-200 bg-black">
        <div className="max-w-[1600px] mx-auto">
          <h2 className="text-xl font-bold text-zinc-500 mb-8 border-b border-zinc-900 pb-3 font-mono">SECURE PERIMETER ACCESS</h2>
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center gap-6">
            <div className="border border-zinc-900 p-8 flex-1 bg-zinc-950">
              <p className="text-zinc-500 text-xs mb-2 font-mono tracking-widest">RECURRING SUBSCRIPTION</p>
              <p className="text-3xl sm:text-4xl font-black text-sterilewhite font-mono tracking-tighter">$15.00 / MO</p>
            </div>
            <a
              href="https://asteriostech07.lemonsqueezy.com/checkout/buy/a3dc2366-b80f-4c18-920b-2f608b7a063e"
              className="flex-1 border border-crtgreen bg-transparent text-crtgreen px-8 py-8 text-center text-lg md:text-xl font-black hover:bg-crtgreen hover:text-black uppercase tracking-widest block transition-none font-mono"
            >
              PROVISION API ACCESS
            </a>
          </div>
          <p className="text-xs text-zinc-600 mt-8 max-w-3xl font-mono leading-relaxed">
            WARNING: ALL TRANSACTIONS ARE PROCESSED VIA LEMON SQUEEZY MERCHANT OF RECORD. 
            CRYPTOGRAPHIC TOKENS ARE DISPATCHED VIA EMAIL POST-AUTHENTICATION. CANCEL ANYTIME.
          </p>
        </div>
      </section>

    </main>
  );
}
