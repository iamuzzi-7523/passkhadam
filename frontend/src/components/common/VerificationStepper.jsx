import React from 'react';
import {
  CheckCircle2, Clock, ShieldCheck, Database, Key, Lock,
  FileSearch, Sparkles, Hash, UserCheck, ShieldAlert
} from 'lucide-react';

export default function VerificationStepper({ steps = [], isCompleted = false }) {
  const defaultSteps = [
    {
      step: 1,
      name: "Payload Parse & Schema Validation",
      detail: "Envelope JSON parse, expiration & DID schema validation",
      icon: FileSearch
    },
    {
      step: 2,
      name: "Presentation Signature Verification",
      detail: "Ed25519 Authority digital signature check",
      icon: Key
    },
    {
      step: 3,
      name: "Expiration / Timestamp Validation",
      detail: "Checking timestamp freshness (< 300s window)",
      icon: Clock
    },
    {
      step: 4,
      name: "On-Chain DID & Registration Verification",
      detail: "Queries EVM WorkerIdentityRegistry for active & unrevoked status",
      icon: Database
    },
    {
      step: 5,
      name: "IPFS Credential Retrieval",
      detail: "Resolves encrypted payload from IPFS by CID",
      icon: Lock
    },
    {
      step: 6,
      name: "Integrity Hash Verification",
      detail: "Byte-for-byte SHA-256 / Keccak-256 comparison against on-chain anchor",
      icon: Hash
    },
    {
      step: 7,
      name: "Decryption of Verifiable Credential",
      detail: "Decrypts W3C VC subject with AES-256-GCM DEK",
      icon: Lock
    },
    {
      step: 8,
      name: "Issuer Signature Verification",
      detail: "Validates Identity Authority Ed25519 signature on W3C credential",
      icon: ShieldCheck
    },
    {
      step: 9,
      name: "Role-Based Data Redaction",
      detail: "Redacts PII for Employer vs Government view",
      icon: Sparkles
    },
    {
      step: 10,
      name: "Verifier Authorization & Scope Check",
      detail: "Verifies verifier role, active standing, and organization status",
      icon: UserCheck
    },
    {
      step: 11,
      name: "Deferred Atomic Nonce Consumption",
      detail: "Enforces composite replay defense in database transaction",
      icon: CheckCircle2
    }
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center font-bold">
            ✓
          </div>
          <div>
            <h4 className="text-sm font-bold text-white">Cryptographic Verification Pipeline (v0.4)</h4>
            <p className="text-xs text-slate-400">11-stage automated integrity, on-chain hash audit & RBAC sequence</p>
          </div>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
          {steps.length}/11 Stages Verified
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-2.5">
        {defaultSteps.map((s) => {
          const matchingResult = steps.find(st => st.step === s.step);
          const isDone = Boolean(
            (matchingResult && (matchingResult.status === "SUCCESS" || matchingResult.status === "VERIFIED" || matchingResult.status === "COMPLETED")) ||
            (isCompleted && matchingResult)
          );
          const isFailed = Boolean(matchingResult && matchingResult.status === "FAILED");
          const Icon = s.icon;

          return (
            <div
              key={s.step}
              className={`p-3 rounded-xl border text-xs transition-all ${
                isFailed
                  ? 'bg-rose-950/20 border-rose-500/30 text-rose-200'
                  : isDone
                  ? 'bg-emerald-950/20 border-emerald-500/30 text-slate-200'
                  : 'bg-slate-950/40 border-slate-800/80 text-slate-400'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5 font-semibold">
                  <Icon className={`w-3.5 h-3.5 ${isFailed ? 'text-rose-400' : isDone ? 'text-emerald-400' : 'text-slate-500'}`} />
                  <span className={isFailed ? 'text-rose-300' : isDone ? 'text-white' : 'text-slate-400'}>
                    {s.step}. {s.name}
                  </span>
                </div>
                {isFailed ? (
                  <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
                ) : isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : (
                  <span className="w-2 h-2 rounded-full bg-slate-700"></span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                {matchingResult ? matchingResult.detail : s.detail}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
