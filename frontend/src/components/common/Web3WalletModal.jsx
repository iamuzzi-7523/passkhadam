import React, { useState } from 'react';
import { X, Wallet, Check, Copy, ExternalLink, RefreshCw, AlertTriangle, ShieldCheck } from 'lucide-react';
import { useWeb3Wallet, SUPPORTED_NETWORKS } from '../../context/Web3Context';

export default function Web3WalletModal({ isOpen, onClose }) {
  const {
    account,
    chainId,
    balance,
    currency,
    isConnected,
    isSimulated,
    isMetaMaskInstalled,
    networkName,
    error,
    connectMetaMask,
    connectSimulated,
    switchNetwork,
    disconnect
  } = useWeb3Wallet();

  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = () => {
    if (account) {
      navigator.clipboard.writeText(account);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden text-slate-100">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30">
              <Wallet className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-white">Web3 & MetaMask Wallet</h3>
              <p className="text-xs text-slate-400">Blockchain Signing & Smart Contract Interface</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {isConnected ? (
            <div className="space-y-4">
              {/* Connected Account Card */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">CONNECTED WALLET</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                    isSimulated ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  }`}>
                    {isSimulated ? '⚡ Hardhat Node Auth' : '🦊 Live MetaMask'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900 border border-slate-800/80">
                  <div className="font-mono text-xs text-slate-200 truncate max-w-[240px]">
                    {account}
                  </div>
                  <button
                    onClick={handleCopy}
                    className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-white transition"
                    title="Copy Address"
                  >
                    {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                  <div>
                    <span className="text-slate-500 text-[11px] block">Network</span>
                    <span className="font-medium text-slate-300">{networkName}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[11px] block">Balance</span>
                    <span className="font-semibold text-amber-400">{balance} {currency}</span>
                  </div>
                </div>
              </div>

              {/* Network Switcher */}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Switch Active EVM Network
                </label>
                <div className="grid grid-cols-1 gap-1.5">
                  {Object.entries(SUPPORTED_NETWORKS).map(([id, net]) => {
                    const netId = parseInt(id, 10);
                    const isActive = chainId === netId;
                    return (
                      <button
                        key={id}
                        onClick={() => switchNetwork(netId)}
                        className={`px-3 py-2 rounded-xl text-left text-xs font-medium flex items-center justify-between transition border ${
                          isActive
                            ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                            : 'bg-slate-950 border-slate-800/80 text-slate-400 hover:text-white hover:border-slate-700'
                        }`}
                      >
                        <div>
                          <span className="text-white block font-medium">{net.name}</span>
                          <span className="text-[10px] text-slate-500">Chain ID: {id} • Currency: {net.currency}</span>
                        </div>
                        {isActive && <Check className="w-4 h-4 text-blue-400" />}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  onClick={disconnect}
                  className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium transition"
                >
                  Disconnect Wallet
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-xs text-slate-400">
                Connect your browser Web3 wallet to sign blockchain identity records, verify smart contracts, and authorize welfare transactions.
              </p>

              {/* Option 1: Live MetaMask */}
              <button
                onClick={connectMetaMask}
                className="w-full p-3 bg-gradient-to-r from-amber-600/30 to-amber-700/20 hover:from-amber-600/40 hover:to-amber-700/30 border border-amber-500/40 rounded-xl text-left flex items-center justify-between transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="text-2xl">🦊</div>
                  <div>
                    <h4 className="text-xs font-semibold text-white group-hover:text-amber-300">
                      Connect Live MetaMask Browser Wallet
                    </h4>
                    <p className="text-[11px] text-slate-400">
                      {isMetaMaskInstalled ? 'MetaMask extension detected' : 'Extension prompt (or install from metamask.io)'}
                    </p>
                  </div>
                </div>
                <ExternalLink className="w-4 h-4 text-amber-400" />
              </button>

              {/* Option 2: Fallback Simulated Local Hardhat Node Wallet */}
              <button
                onClick={() => connectSimulated()}
                className="w-full p-3 bg-slate-950 hover:bg-slate-800/60 border border-slate-800 hover:border-slate-700 rounded-xl text-left flex items-center justify-between transition group"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white group-hover:text-indigo-300">
                      Simulated Local Hardhat Node Wallet (Dev / Demo)
                    </h4>
                    <p className="text-[11px] text-slate-400">
                      Zero-install instant connection with authorized officer address (Chain 1337)
                    </p>
                  </div>
                </div>
              </button>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
