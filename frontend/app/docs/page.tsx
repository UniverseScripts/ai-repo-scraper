"use client";

import { useState } from "react";
import Link from "next/link";

export default function DocsPage() {
  const [activeTab, setActiveTab] = useState<"curl" | "python" | "node">("curl");
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const codeSnippets = {
    curl: `curl -X GET \\
  "https://agentrisk-daas.onrender.com/api/v1/analytics/package-risk/npm/@modelcontextprotocol/sdk" \\
  -H "X-API-Key: YOUR_API_KEY"`,
    python: `import httpx

api_key = "YOUR_API_KEY"
package = "npm/@modelcontextprotocol/sdk"

url = f"https://agentrisk-daas.onrender.com/api/v1/analytics/package-risk/{package}"
headers = {"X-API-Key": api_key}

response = httpx.get(url, headers=headers)
data = response.json()

print(f"MCI: {data['maintainer_concentration_index']}")
print(f"ASI: {data['anomalous_spike_index']}")`,
    node: `const axios = require("axios");

const apiKey = "YOUR_API_KEY";
const packagePath = "npm/@modelcontextprotocol/sdk";

axios.get(\`https://agentrisk-daas.onrender.com/api/v1/analytics/package-risk/\${packagePath}\`, {
  headers: { "X-API-Key": apiKey }
})
.then(response => {
  console.log("Risk Telemetry:", response.data);
})
.catch(error => console.error("API Error:", error.response.data));`
  };

  const copyCode = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <main className="min-h-screen bg-trueblack text-sterilewhite flex flex-col font-sans uppercase tracking-widest text-sm w-full">
      
      {/* NAVIGATION HEADER */}
      <div className="w-full border-b border-zinc-900 py-6 px-6 sm:px-10 lg:px-16 xl:px-24">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between font-mono text-xs text-zinc-400">
          <Link href="/" className="hover:text-crtgreen transition-colors flex items-center gap-2 font-bold">
            <span>&lt;</span> RETURN TO TERMINAL
          </Link>
          <span className="text-crtgreen font-bold">[API DOCUMENTATION MANUAL]</span>
        </div>
      </div>

      {/* HERO / THESIS */}
      <section className="w-full border-b border-zinc-900 py-12 lg:py-16 px-6 sm:px-10 lg:px-16 xl:px-24">
        <div className="max-w-[1600px] mx-auto">
          <p className="text-crtgreen text-xs font-mono mb-2">[SYSTEM INTERFACE // V3.0 CATALOG-WIDE]</p>
          <h1 className="text-3xl lg:text-4xl font-black mb-4">API ENDPOINT DIRECTORY &amp; INTEGRATION GUIDE</h1>
          <p className="text-zinc-400 max-w-3xl leading-relaxed mt-4 lowercase normal-case tracking-normal text-base font-sans">
            The AgentRisk Data-as-a-Service API delivers institutional maintainer concentration (MCI), dormancy/reactivation (DRI), anomalous spike activity (ASI), and typosquatting detection across npm and PyPI ecosystems.
          </p>
        </div>
      </section>

      {/* AUTHENTICATION & RATE LIMITS */}
      <section id="authentication" className="w-full border-b border-zinc-900 py-12 px-6 sm:px-10 lg:px-16 xl:px-24">
        <div className="max-w-[1600px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
          <div className="p-8 border border-zinc-900 bg-black">
            <h2 className="text-xl font-bold text-crtgreen mb-4 font-mono">1. AUTHENTICATION</h2>
            <p className="text-zinc-400 text-sm lowercase normal-case tracking-normal leading-relaxed font-sans mb-4">
              All API requests must include your provisioned cryptographic API key passed in the custom HTTP header <code className="text-crtgreen font-mono bg-zinc-950 px-2 py-1 border border-zinc-800">X-API-Key</code>.
            </p>
            <pre className="bg-zinc-950 border border-zinc-900 p-4 text-xs font-mono text-zinc-300">
              X-API-Key: daas_live_a1b2c3d4e5f6...
            </pre>
          </div>

          <div id="rate-limits" className="p-8 border border-zinc-900 bg-zinc-950/40">
            <h2 className="text-xl font-bold text-zinc-400 mb-4 font-mono">2. RATE LIMITING &amp; SLA</h2>
            <p className="text-zinc-400 text-sm lowercase normal-case tracking-normal leading-relaxed font-sans mb-4">
              Production API keys are rate-limited to <strong className="text-sterilewhite">60 requests per minute</strong> per key utilizing an in-memory Upstash Redis Lua sliding-window algorithm.
            </p>
            <div className="border border-zinc-900 bg-black p-4 text-xs font-mono text-zinc-500">
              RATE_LIMIT_WINDOW: 60s | MAX_REQUESTS: 60 | ALGORITHM: LUA SLIDING WINDOW
            </div>
          </div>
        </div>
      </section>

      {/* INTERACTIVE CODE PLAYGROUND */}
      <section className="w-full border-b border-zinc-900 py-12 px-6 sm:px-10 lg:px-16 xl:px-24">
        <div className="max-w-[1600px] mx-auto">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
            <h2 className="text-xl font-bold text-crtgreen font-mono">3. QUICKSTART CODE SNIPPET</h2>
            <div className="flex gap-2 font-mono text-xs">
              {(["curl", "python", "node"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 border transition-none font-bold ${
                    activeTab === tab
                      ? "border-crtgreen bg-crtgreen text-black"
                      : "border-zinc-800 bg-black text-zinc-400 hover:text-sterilewhite"
                  }`}
                >
                  {tab.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="relative border border-zinc-900 bg-black p-6">
            <button
              onClick={() => copyCode(codeSnippets[activeTab], 1)}
              aria-label="Copy code snippet to clipboard"
              className="absolute top-4 right-4 border border-zinc-800 bg-zinc-950 px-3 py-1 text-xs text-crtgreen font-mono hover:bg-crtgreen hover:text-black transition-none cursor-pointer"
            >
              {copiedIndex === 1 ? "[COPIED]" : "[COPY]"}
            </button>
            <pre className="text-xs md:text-sm font-mono text-zinc-300 overflow-x-auto leading-relaxed">
              {codeSnippets[activeTab]}
            </pre>
          </div>
        </div>
      </section>

      {/* ENDPOINT DIRECTORY */}
      <section className="w-full border-b border-zinc-900 py-12 px-6 sm:px-10 lg:px-16 xl:px-24">
        <div className="max-w-[1600px] mx-auto">
          <h2 className="text-xl font-bold text-zinc-400 mb-8 font-mono border-b border-zinc-900 pb-3">
            4. PRODUCTION ENDPOINT SPECIFICATIONS
          </h2>

          <div className="space-y-8">
            <div className="border border-zinc-900 p-6 bg-black">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-zinc-900 pb-4 mb-4 font-mono">
                <div className="flex items-center gap-3">
                  <span className="bg-crtgreen text-black px-2 py-1 text-xs font-black">GET</span>
                  <span className="text-sterilewhite font-bold text-sm md:text-base">/api/v1/package-risk/{`{package_name}`}</span>
                </div>
                <span className="text-zinc-500 text-xs">RAW TELEMETRY METRICS</span>
              </div>
              <p className="text-zinc-400 text-sm lowercase normal-case tracking-normal font-sans mb-4">
                Returns the latest unweighted telemetry row for a target package (e.g. <code className="text-crtgreen font-mono bg-zinc-950 px-2 py-1">npm/react</code> or <code className="text-crtgreen font-mono bg-zinc-950 px-2 py-1">pypi/vllm</code>). Supports scoped npm packages (<code className="text-crtgreen font-mono bg-zinc-950 px-2 py-1">npm/@modelcontextprotocol/sdk</code>).
              </p>
            </div>

            <div className="border border-zinc-900 p-6 bg-black">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-zinc-900 pb-4 mb-4 font-mono">
                <div className="flex items-center gap-3">
                  <span className="bg-crtgreen text-black px-2 py-1 text-xs font-black">GET</span>
                  <span className="text-sterilewhite font-bold text-sm md:text-base">/api/v1/analytics/package-risk/{`{package_name}`}</span>
                </div>
                <span className="text-crtgreen text-xs font-bold">COMPOSITE RISK INDICES</span>
              </div>
              <p className="text-zinc-400 text-sm lowercase normal-case tracking-normal font-sans mb-4">
                Synthesizes raw telemetry into institutional composite risk indices: Maintainer Concentration Index (MCI), Dormancy Reactivation Index (DRI), and Anomalous Spike Index (ASI).
              </p>
            </div>

            <div className="border border-zinc-900 p-6 bg-black">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-zinc-900 pb-4 mb-4 font-mono">
                <div className="flex items-center gap-3">
                  <span className="bg-crtgreen text-black px-2 py-1 text-xs font-black">GET</span>
                  <span className="text-sterilewhite font-bold text-sm md:text-base">/api/v1/package-risk/{`{package_name}`}/history?limit=30</span>
                </div>
                <span className="text-zinc-500 text-xs">TIME-SERIES RETENTION</span>
              </div>
              <p className="text-zinc-400 text-sm lowercase normal-case tracking-normal font-sans mb-4">
                Returns historical telemetry snapshots and computed indices, newest first. <code className="text-crtgreen font-mono bg-zinc-950 px-2 py-1">limit</code> accepts 1&ndash;100 and defaults to 30. One snapshot is retained per ingest cycle.
              </p>
            </div>

            <div className="border border-zinc-900 p-6 bg-black">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-zinc-900 pb-4 mb-4 font-mono">
                <div className="flex items-center gap-3">
                  <span className="bg-amber-400 text-black px-2 py-1 text-xs font-black">POST</span>
                  <span className="text-sterilewhite font-bold text-sm md:text-base">/webhooks/lemon-squeezy</span>
                </div>
                <span className="text-zinc-500 text-xs">CRYPTOGRAPHIC PROVISIONING</span>
              </div>
              <p className="text-zinc-400 text-sm lowercase normal-case tracking-normal font-sans mb-4">
                Receives HMAC-SHA256 signed subscription events from Lemon Squeezy Merchant of Record to instantly provision API keys or deactivate keys on cancellation.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* HTTP STATUS CODES & TYPOSQUATTING SPECIFICATION */}
      <section id="status-codes" className="w-full py-12 px-6 sm:px-10 lg:px-16 xl:px-24">
        <div className="max-w-[1600px] mx-auto">
          <h2 className="text-xl font-bold text-crtgreen mb-6 font-mono">5. HTTP RESPONSE CODES &amp; TYPOSQUATTING MATRIX</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono text-xs">
            <div className="border border-zinc-900 p-6 bg-zinc-950">
              <p className="text-crtgreen font-bold mb-2">HTTP 200 OK</p>
              <p className="text-zinc-400 lowercase normal-case tracking-normal font-sans text-xs mb-3">
                Request resolved successfully. Telemetry or analytics object returned.
              </p>
            </div>

            <div className="border border-zinc-900 p-6 bg-zinc-950">
              <p className="text-amber-400 font-bold mb-2">HTTP 401 UNAUTHORIZED</p>
              <p className="text-zinc-400 lowercase normal-case tracking-normal font-sans text-xs mb-3">
                Missing, unauthenticated, or deactivated API key.
              </p>
            </div>

            <div className="border border-zinc-900 p-6 bg-zinc-950">
              <p className="text-red-400 font-bold mb-2">HTTP 404 NOT FOUND (TYPOSQUATTING)</p>
              <p className="text-zinc-400 lowercase normal-case tracking-normal font-sans text-xs mb-3">
                Queried package identity does not exist in registry. Edit distance matching returns possible typosquatting target.
              </p>
            </div>

            <div className="border border-zinc-900 p-6 bg-zinc-950">
              <p className="text-cyan-400 font-bold mb-2">HTTP 504 GATEWAY TIMEOUT</p>
              <p className="text-zinc-400 lowercase normal-case tracking-normal font-sans text-xs mb-3">
                Synchronous live resolution exceeded 5.0s threshold. Resolution offloaded to background revalidation task.
              </p>
            </div>

            <div className="border border-zinc-900 p-6 bg-zinc-950">
              <p className="text-orange-400 font-bold mb-2">HTTP 503 SERVICE UNAVAILABLE</p>
              <p className="text-zinc-400 lowercase normal-case tracking-normal font-sans text-xs mb-3">
                An upstream telemetry source was unreachable or its request budget was momentarily exhausted. This describes our service, never the queried package &mdash; a package is only reported untrackable when that is actually true.
              </p>
            </div>
          </div>
        </div>
      </section>

    </main>
  );
}
