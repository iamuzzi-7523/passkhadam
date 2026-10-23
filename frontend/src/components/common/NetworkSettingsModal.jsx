import React, { useState, useEffect } from 'react';
import { X, Server, Database, Globe, CheckCircle2, Activity, RefreshCw } from 'lucide-react';
import { apiFetch } from '../../utils/api';

export default function NetworkSettingsModal({ isOpen, onClose }) {
  const [config, setConfig] = useState(null);
  const [selectedIpfs, setSelectedIpfs] = useState('local');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      apiFetch('/api/v1/admin/network-config')
        .then(res => res.json())
        .then(data => {
          setConfig(data);
          setSelectedIpfs(data.active_ipfs_provider || 'local');
        })
        .catch(err => console.warn('Failed to load network config:', err));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleTestConnectivity = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiFetch('/api/v1/admin/test-connectivity', { method: 'POST' });
      const data = await res.json();
      setTestResult(data);
    } catch (e) {
      setTestResult({
        blockchain: { status: 'OFFLINE', latency_ms: 0 },
        ipfs: { status: 'OFFLINE', latency_ms: 0 },
        overall_health: 'DEGRADED'
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in">
      <div className="relative w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden text-slate-100">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-white">Network & Storage Architecture</h3>
              <p className="text-xs text-slate-400">EVM Blockchain Nodes & IPFS Decentralized Providers</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5 max-h-[80vh] overflow-y-auto">
          
          {/* IPFS Providers Section */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Database className="w-4 h-4 text-cyan-400" />
                Decentralized IPFS Storage Provider
              </label>
              <span className="text-[10px] text-slate-500 font-mono">Provider Abstraction Active</span>
            </div>

            <div className="space-y-2">
              {config?.supported_ipfs_providers?.map((p) => {
                const isSelected = selectedIpfs === p.id;
                return (
                  <div
                    key={p.id}
                    onClick={() => setSelectedIpfs(p.id)}
                    className={`p-3 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                      isSelected
                        ? 'bg-cyan-950/30 border-cyan-500/50 text-white'
                        : 'bg-slate-950 border-slate-800/80 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-white">{p.name}</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                          p.status === 'OPERATIONAL' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-slate-400'
                        }`}>
                          {p.status}
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500 block mt-0.5">{p.type} • Gateway: {p.gateway_url}</span>
                    </div>
                    {isSelected && <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" />}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Blockchain Networks Section */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Globe className="w-4 h-4 text-purple-400" />
                EVM Blockchain Networks & Testnets
              </label>
              <span className="text-[10px] text-slate-500 font-mono">Chain ID: 1337 Default</span>
            </div>

            <div className="space-y-2">
              {config?.supported_networks?.map((n) => (
                <div key={n.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-xs text-white">{n.name}</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 font-mono">
                        Chain {n.chain_id}
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-500 block mt-0.5">RPC: {n.rpc_url}</span>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                    n.status === 'ONLINE' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'
                  }`}>
                    {n.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Diagnostic Test Connectivity */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-semibold text-white flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  Live Diagnostic Connectivity Check
                </h4>
                <p className="text-[11px] text-slate-400">Ping RPC node and IPFS gateway to evaluate real-time latency</p>
              </div>
              <button
                type="button"
                onClick={handleTestConnectivity}
                disabled={testing}
                className="px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/40 text-emerald-300 rounded-lg text-xs font-medium transition flex items-center gap-1.5"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${testing ? 'animate-spin' : ''}`} />
                {testing ? 'Testing...' : 'Ping Diagnostics'}
              </button>
            </div>

            {testResult && (
              <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-slate-850">
                <div className="p-2 rounded-lg bg-slate-900 border border-slate-800/80">
                  <span className="text-[10px] text-slate-500 block">EVM RPC LATENCY</span>
                  <span className="font-mono text-emerald-400 font-semibold">{testResult.blockchain.latency_ms} ms</span>
                  <span className="text-[10px] text-slate-400 block mt-0.5">{testResult.blockchain.status} ({testResult.blockchain.network})</span>
                </div>
                <div className="p-2 rounded-lg bg-slate-900 border border-slate-800/80">
                  <span className="text-[10px] text-slate-500 block">IPFS STORE LATENCY</span>
                  <span className="font-mono text-cyan-400 font-semibold">{testResult.ipfs.latency_ms} ms</span>
                  <span className="text-[10px] text-slate-400 block mt-0.5">{testResult.ipfs.status} ({testResult.ipfs.provider})</span>
                </div>
              </div>
            )}
          </div>

        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-medium transition"
          >
            Close & Apply
          </button>
        </div>

      </div>
    </div>
  );
}
