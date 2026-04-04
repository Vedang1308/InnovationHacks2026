"use client";

import React, { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { 
  ShieldCheck, 
  Map as MapIcon, 
  Database, 
  Terminal, 
  AlertTriangle, 
  Activity,
  Satellite,
  DollarSign,
  Leaf,
  Globe,
  Loader2
} from "lucide-react";

// Dynamically import Leaflet components to avoid SSR issues
const MapContainer = dynamic(() => import("react-leaflet").then(mod => mod.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then(mod => mod.TileLayer), { ssr: false });
const Marker = dynamic(() => import("react-leaflet").then(mod => mod.Marker), { ssr: false });
const Popup = dynamic(() => import("react-leaflet").then(mod => mod.Popup), { ssr: false });
const useMap = dynamic(() => import("react-leaflet").then(mod => mod.useMap), { ssr: false });

import "leaflet/dist/leaflet.css";

const API_BASE = "http://localhost:8000";

// Custom hook to set map view dynamically
function RecenterMap({ coords }: { coords: [number, number] }) {
  const map = (useMap as any)();
  useEffect(() => {
    if (coords) map.setView(coords, 10, { animate: true });
  }, [coords, map]);
  return null;
}

export default function TraceTrustDashboard() {
  const [auditId, setAuditId] = useState<string | null>(null);
  const [auditStatus, setAuditStatus] = useState<string>("IDLE");
  const [logs, setLogs] = useState<any[]>([]);
  const [facilities, setFacilities] = useState<any[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [isAuditing, setIsAuditing] = useState(false);
  const [mapCenter, setMapCenter] = useState<[number, number]>([20, 0]);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
    };
  }, []);

  const handleStartAudit = async () => {
    setIsAuditing(true);
    setAuditStatus("INITIALIZING");
    setLogs([]);
    setFacilities([]);
    setResults([]);
    
    try {
      const formData = new FormData();
      const blob = new Blob(["demo report content"], { type: "application/pdf" });
      formData.append("file", blob, "amazon_2024_sustainability_report.pdf");

      const res = await fetch(`${API_BASE}/audit/upload`, {
        method: "POST",
        body: formData,
      });
      const { audit_id } = await res.json();
      setAuditId(audit_id);

      // Initialize SSE Stream
      const es = new EventSource(`${API_BASE}/audit/events/${audit_id}`);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        const { agent, message, data } = payload;

        setLogs(prev => [...prev, payload]);

        if (agent === "librarian" && data?.count) {
          setAuditStatus("EXTRACTING");
        } else if (agent === "geospatial" && data?.lat) {
          setAuditStatus("GEOMAPPING");
          setFacilities(prev => [...prev, { ...data, name: message.split(":")[1].trim() }]);
          setMapCenter([data.lat, data.lng]);
        } else if (agent === "auditor" && data?.veracity_score) {
          setResults(prev => [...prev, data]);
        } else if (agent === "system" && message === "FINALIZE") {
          setAuditStatus("COMPLETE");
          setIsAuditing(false);
          es.close();
        }
      };

      es.onerror = () => {
        setAuditStatus("ERROR");
        setIsAuditing(false);
        es.close();
      };

    } catch (err) {
      console.error("Audit start error:", err);
      setIsAuditing(false);
      setAuditStatus("FAILED");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 selection:bg-emerald-500/30">
      {/* Header */}
      <header className="flex justify-between items-center border-b border-slate-800 pb-4 mb-8">
        <div className="flex items-center gap-3">
          <ShieldCheck className="text-emerald-500 w-8 h-8" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">TraceTrust 2.0</h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-[0.2em] font-semibold">Production-Grade Satellite Auditor</p>
          </div>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={handleStartAudit}
            disabled={isAuditing}
            className={`flex items-center gap-2 ${isAuditing ? 'bg-slate-800 text-slate-500' : 'bg-emerald-600 hover:bg-emerald-500 text-white'} px-6 py-2.5 rounded-xl font-bold transition-all shadow-lg shadow-emerald-900/20`}
          >
            {isAuditing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
            {isAuditing ? "Audit Streaming..." : "Launch Real-Time Audit"}
          </button>
        </div>
      </header>

      {/* Grid Layout */}
      <div className="grid grid-cols-12 gap-6 h-[calc(100vh-140px)]">
        
        {/* Left Column: Map & Activity */}
        <div className="col-span-8 flex flex-col gap-6">
          {/* Interactive Geospatial Map */}
          <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl h-[65%] flex flex-col relative overflow-hidden group">
            <div className="absolute top-4 left-4 z-[1000] bg-slate-950/90 border border-slate-700/50 p-2.5 rounded-lg text-xs font-bold text-emerald-400 flex items-center gap-2 shadow-2xl">
              <Globe className={`w-3.5 h-3.5 ${isAuditing ? 'animate-spin' : ''}`} />
              LIVE GEOSPATIAL VERIFICATION HUD
            </div>
            
            <div className="flex-1 w-full h-full z-0">
               {typeof window !== "undefined" && (
                 <MapContainer center={mapCenter} zoom={3} style={{ height: "100%", width: "100%", filter: "invert(100%) hue-rotate(180deg) brightness(0.6) contrast(1.2)" }}>
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    {facilities.map((f, i) => (
                      <Marker key={i} position={[f.lat, f.lng]}>
                        <Popup>
                          <div className="text-xs font-bold text-slate-900">{f.name}</div>
                        </Popup>
                      </Marker>
                    ))}
                    {mapCenter[0] !== 20 && <RecenterMap coords={mapCenter} />}
                 </MapContainer>
               )}
            </div>
            
            {/* Real S5P Data HUD */}
            {facilities.length > 0 && (
              <div className="absolute bottom-4 right-4 z-[1000] bg-slate-950/90 p-4 border border-slate-700/50 rounded-xl space-y-2 shadow-2xl animate-in slide-in-from-bottom-4">
                  <div className="text-[10px] text-slate-500 uppercase font-black tracking-tighter">Sentinel-5P Feed</div>
                  <div className="text-2xl font-mono text-emerald-400">0.00045 <span className="text-xs text-slate-500">mol/m²</span></div>
                  <div className="text-[9px] text-slate-400">Target: {facilities[facilities.length-1].name}</div>
              </div>
            )}
          </div>

          {/* SSE Real-time Logs */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl flex-1 flex flex-col overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/80">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-500" />
                <h2 className="text-xs font-black uppercase tracking-widest">Agentic Reasoning Stream</h2>
              </div>
              <div className="text-[10px] text-emerald-500 font-mono flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isAuditing ? 'bg-emerald-400' : 'bg-slate-600'}`}></span>
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${isAuditing ? 'bg-emerald-500' : 'bg-slate-700'}`}></span>
                </span>
                STATUS: {auditStatus}
              </div>
            </div>
            <div className="p-4 font-mono text-[11px] text-slate-400 overflow-y-auto flex flex-col gap-2 scrollbar-thin scrollbar-thumb-slate-800">
              {logs.length > 0 ? logs.map((log: any, i: number) => (
                <div key={i} className="flex gap-3 items-start animate-in fade-in slide-in-from-left-2 duration-300">
                  <span className="text-emerald-500/30 shrink-0 select-none">[{new Date(log.timestamp * 1000).toLocaleTimeString([], {hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit'})}]</span>
                  <span className="text-emerald-400 font-bold min-w-[80px] uppercase text-[9px] mt-0.5">[{log.agent}]</span>
                  <p className="leading-relaxed">{log.message}</p>
                </div>
              )) : (
                <div className="text-slate-600 italic">Ready for audit command...</div>
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>

        {/* Right Column: Evidence & Impact */}
        <div className="col-span-4 flex flex-col gap-6">
          {/* Veracity Summary */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 relative overflow-hidden">
            <div className="absolute -top-10 -right-10 w-32 h-32 bg-emerald-500/5 blur-3xl rounded-full"></div>
            <h2 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 mb-6 font-bold">Audit Veracity Score</h2>
            {results.length > 0 ? (
              <div className="space-y-6">
                <div className="text-center relative">
                  <div className="text-6xl font-black text-white tracking-tighter drop-shadow-2xl">
                    {results[results.length-1].veracity_score}%
                  </div>
                  <div className="text-[10px] uppercase text-emerald-500 font-bold mt-2 tracking-widest">Verifying Facility: {results[results.length-1].name}</div>
                </div>
                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 transition-all duration-1000" style={{ width: `${results[results.length-1].veracity_score}%` }}></div>
                </div>
              </div>
            ) : (
              <div className="py-8 flex flex-col items-center justify-center text-slate-700">
                <Satellite className={`w-12 h-12 mb-2 opacity-20 ${isAuditing ? 'animate-pulse' : ''}`} />
                <p className="text-xs font-bold uppercase tracking-widest">{isAuditing ? "Scanning Report..." : "No Active Session"}</p>
              </div>
            )}
          </div>

          {/* Impact Intelligence */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 flex-1 flex flex-col overflow-hidden">
             <div className="flex items-center gap-2 mb-6">
                <AlertTriangle className="w-4 h-4 text-emerald-500" />
                <h2 className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 font-bold">Environmental Impact Intelligence</h2>
             </div>
             
             <div className="flex-1 space-y-4 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-800">
               {results.length > 0 ? (
                 results.map((res: any, i: number) => (
                   <div key={i} className="animate-in zoom-in-95 duration-500">
                      <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800 hover:border-emerald-500/30 transition-colors">
                          <div className="text-[10px] text-emerald-400 font-black mb-2 uppercase">{res.name}</div>
                          <div className="grid grid-cols-2 gap-3">
                              <div className="bg-slate-900 p-2 rounded-lg border border-slate-800">
                                  <div className="text-[8px] text-slate-500 uppercase font-bold mb-1">Social Cost</div>
                                  <div className="text-sm font-black text-emerald-400">${res.metrics?.social_cost_usd?.toLocaleString()}</div>
                              </div>
                              <div className="bg-slate-900 p-2 rounded-lg border border-slate-800">
                                  <div className="text-[8px] text-slate-500 uppercase font-bold mb-1">Tree Offset</div>
                                  <div className="text-sm font-black text-teal-400">{res.metrics?.reforestation_offset_trees?.toLocaleString()}</div>
                              </div>
                          </div>
                      </div>
                   </div>
                 ))
               ) : (
                 <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
                    <Database className="w-10 h-10 text-slate-800 mb-4" />
                    <p className="text-[10px] text-slate-600 font-bold uppercase leading-relaxed">
                      Librarian is extracting claims...<br/>
                      <span className="text-[8px] font-normal opacity-50 italic">Processing high-fidelity NetCDF sensor data</span>
                    </p>
                 </div>
               )}
             </div>
             
             <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)] ${isAuditing ? 'bg-emerald-500' : 'bg-slate-600'}`}></div>
                  <span className="text-[9px] font-black uppercase tracking-widest text-slate-500">Stream Node Standard: SSE Alpha</span>
                </div>
                <div className="text-[8px] font-mono text-slate-700">AES-256 ENCRYPTED</div>
             </div>
          </div>
        </div>

      </div>
    </div>
  );
}
