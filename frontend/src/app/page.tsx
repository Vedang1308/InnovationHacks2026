"use client";

import React, { useState, useEffect } from "react";
import { 
  ShieldCheck, 
  Map as MapIcon, 
  Database, 
  Terminal, 
  AlertTriangle, 
  Activity,
  Satellite
} from "lucide-react";

export default function TraceTrustDashboard() {
  const [logs, setLogs] = useState<string[]>([
    "Initializing TraceTrust Mission Control...",
    "System check: Librarian Agent Online",
    "System check: Geospatial Agent Online",
    "System check: Satellite Auditor Online",
  ]);
  const [auditResult, setAuditResult] = useState<any>(null);

  const addLog = (msg: string) => {
    setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  };

  const handleStartAudit = async () => {
    addLog("Audit sequence started for: Amazon_Sustainability_Report_2024.pdf");
    addLog("Librarian Agent parsing PDF layout...");
    
    // Simulate pipeline
    setTimeout(() => {
      addLog("Librarian discovered 14 facilities in 'Carbon Assets' table.");
      addLog("Geospatial Agent geocoding facilities...");
    }, 1500);

    setTimeout(() => {
      addLog("Satellite Agent querying ASDI S3 for Sentinel-5P (NO2/CH4)...");
      addLog("Climate TRACE API cross-referencing facility CT_12345...");
    }, 3000);

    setTimeout(() => {
      addLog("Auditor Agent calculating Veracity Scores...");
      setAuditResult({
        overall_veracity: 82.5,
        total_audited: 14,
        discrepancies: 3,
        details: [
          { name: "GYR3 Fulfillment Center", reported: 4500, satellite: 5400, score: 80.0, status: "DISCREPANCY" },
          { name: "LGW1 Fulfillment Center", reported: 3200, satellite: 3350, score: 95.5, status: "VERIFIED" },
        ]
      });
      addLog("Audit complete. Reports generated.");
    }, 5000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6">
      {/* Header */}
      <header className="flex justify-between items-center border-b border-slate-800 pb-4 mb-8">
        <div className="flex items-center gap-3">
          <ShieldCheck className="text-emerald-500 w-8 h-8" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">TraceTrust</h1>
            <p className="text-xs text-slate-500 uppercase tracking-widest">Agentic Satellite Auditor</p>
          </div>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={handleStartAudit}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-lg font-medium transition-colors"
          >
            <Activity className="w-4 h-4" /> Start New Audit
          </button>
        </div>
      </header>

      {/* Grid Layout */}
      <div className="grid grid-cols-12 gap-6">
        
        {/* Left Column: Map & Activity */}
        <div className="col-span-8 flex flex-col gap-6">
          {/* Map Area */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl h-96 flex flex-col relative overflow-hidden">
            <div className="absolute top-4 left-4 z-10 bg-slate-950/80 backdrop-blur border border-slate-700 p-2 rounded text-xs uppercase font-semibold text-slate-400">
              Global Facility Map
            </div>
            {/* Placeholder for Interactive Map */}
            <div className="flex-1 flex items-center justify-center bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')] opacity-20">
              <MapIcon className="w-24 h-24 text-slate-700" />
            </div>
            <div className="p-4 border-t border-slate-800 bg-slate-950/50 flex justify-around text-sm">
              <div className="flex items-center gap-2"><span className="w-3 h-3 bg-emerald-500 rounded-full"></span> Verified</div>
              <div className="flex items-center gap-2"><span className="w-3 h-3 bg-red-500 rounded-full"></span> Discrepancy</div>
              <div className="flex items-center gap-2"><span className="w-3 h-3 bg-slate-600 rounded-full"></span> Pending</div>
            </div>
          </div>

          {/* Activity Log */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl flex-1 flex flex-col overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-emerald-500" />
              <h2 className="text-sm font-semibold uppercase tracking-wider">Agent Activity Log</h2>
            </div>
            <div className="p-4 font-mono text-xs text-slate-400 overflow-y-auto max-h-64 flex flex-col gap-2">
              {logs.map((log, i) => (
                <div key={i} className="border-l-2 border-emerald-500/20 pl-3 py-1 bg-emerald-500/5">{log}</div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Evidence & Status */}
        <div className="col-span-4 flex flex-col gap-6">
          {/* Stats Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">Audit Summary</h2>
            {auditResult ? (
              <div className="space-y-6">
                <div className="text-center py-4">
                  <div className="text-5xl font-black text-emerald-500 mb-1">{auditResult.overall_veracity}%</div>
                  <div className="text-xs uppercase text-slate-500">Overall Veracity Score</div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700">
                    <div className="text-xl font-bold">{auditResult.total_audited}</div>
                    <div className="text-[10px] uppercase text-slate-500">Audited</div>
                  </div>
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700">
                    <div className="text-xl font-bold text-red-400">{auditResult.discrepancies}</div>
                    <div className="text-[10px] uppercase text-slate-500">Flagged</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-slate-600 border-2 border-dashed border-slate-800 rounded-lg">
                No active audit. Click "Start" to begin.
              </div>
            )}
          </div>

          {/* Evidence Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex-1">
             <div className="flex items-center gap-2 mb-4">
                <Satellite className="w-4 h-4 text-emerald-500" />
                <h2 className="text-sm font-semibold uppercase tracking-wider">Satellite Evidence</h2>
             </div>
             {auditResult ? (
               <div className="space-y-4">
                  {auditResult.details.map((f: any, i: number) => (
                    <div key={i} className="p-3 bg-slate-950 rounded border border-slate-800 group transition-all hover:border-slate-600">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-xs font-bold truncate pr-2">{f.name}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${f.status === 'VERIFIED' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                          {f.status}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 text-[10px] text-slate-500 gap-2">
                         <div>RPT: {f.reported}t</div>
                         <div className="text-right">SAT: {f.satellite}t</div>
                      </div>
                    </div>
                  ))}
               </div>
             ) : (
               <div className="space-y-4 opacity-50 select-none">
                  {[1,2,3].map(i => (
                    <div key={i} className="h-16 bg-slate-800 rounded animate-pulse"></div>
                  ))}
               </div>
             )}
          </div>
        </div>

      </div>
    </div>
  );
}
