import React, { useState, useEffect } from 'react';
import { 
  Landmark, ShieldCheck, AlertTriangle, CheckCircle, FileText, 
  MapPin, Coins, RefreshCw, Send, CheckCircle2, History, BadgeCheck, User, Award
} from 'lucide-react';
import QRImageUploader from '../common/QRImageUploader';
import VerificationStepper from '../common/VerificationStepper';
import { useAuth } from '../../context/AuthContext';
import { apiFetch } from '../../utils/api';

export default function GovernmentPortal({ currentLang = 'en' }) {
  const { currentUser } = useAuth();
  const [govInfo, setGovInfo] = useState(null);
  const [officerProfile, setOfficerProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifiedResult, setVerifiedResult] = useState(null);
  const [verificationError, setVerificationError] = useState("");
  const [selectedScheme, setSelectedScheme] = useState(1);
  const [disbursing, setDisbursing] = useState(false);
  const [actionMsg, setActionMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [credTitle, setCredTitle] = useState("BOCW Social Security Welfare Card");
  const [credType, setCredType] = useState("Welfare");
  const [credSkills, setCredSkills] = useState("");
  const [issuingCred, setIssuingCred] = useState(false);

  const fetchGovData = async () => {
    try {
      setLoading(true);
      const res = await apiFetch("/api/v1/government/info");
      if (res.ok) {
        const data = await res.json();
        setGovInfo(data);
      }
      const profRes = await apiFetch("/api/v1/government/profile/me");
      if (profRes.ok) {
        const profData = await profRes.json();
        setOfficerProfile(profData);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGovData();
  }, [currentUser]);

  const handleVerifyQR = async (file) => {
    setIsVerifying(true);
    setVerificationError("");
    setVerifiedResult(null);
    setActionMsg("");
    setErrorMsg("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await apiFetch("/api/v1/government/verify-worker-qr", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Government QR verification failed");
      }
      setVerifiedResult(data);
    } catch (err) {
      setVerificationError(err.message);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleDisburseClaim = async () => {
    if (!verifiedResult) return;
    setDisbursing(true);
    setActionMsg("");
    setErrorMsg("");

    try {
      const officerState = officerProfile?.state || govInfo?.state || "Maharashtra";
      const officerWallet = officerProfile?.wallet_address || govInfo?.address;
      const res = await apiFetch("/api/v1/government/disburse-claim", {
        method: "POST",
        body: {
          scheme_id: Number(selectedScheme),
          worker_did: verifiedResult.worker_did,
          officer_state: officerState,
          officer_wallet: officerWallet,
          gov_officer_wallet: officerWallet
        }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Claim disbursement failed");
      }
      setActionMsg(`Welfare claim #${data.claim_record.claim_id} disbursed successfully: ₹${data.claim_record.amount} anchored on blockchain!`);
      await fetchGovData();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setDisbursing(false);
    }
  };

  const handleIssueGovernmentCredential = async (e) => {
    e.preventDefault();
    if (!verifiedResult) return;
    setIssuingCred(true);
    setActionMsg("");
    setErrorMsg("");

    try {
      const res = await apiFetch("/api/v1/government/credentials/issue", {
        method: "POST",
        body: {
          worker_did: verifiedResult.worker_did,
          title: credTitle,
          credential_type: credType,
          skills: credSkills ? credSkills.split(',').map(s => s.trim()).filter(Boolean) : [credTitle],
          valid_days: 365
        }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to issue credential");
      }
      setActionMsg(`Official Verifiable Credential "${data.title}" successfully issued and anchored to worker DID!`);
    } catch (err) {
      setErrorMsg(err.message || "Failed to issue credential");
    } finally {
      setIssuingCred(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mr-2" />
        <span>Loading Government Portal...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Department Authority Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-purple-600/15 border border-purple-500/30 text-purple-400 flex items-center justify-center text-2xl font-bold">
              🏛️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">
                  {officerProfile?.department || govInfo?.department_name || 'Department of Labour'}
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/30">
                  {officerProfile?.authority_level ? `${officerProfile.authority_level} JURISDICTION` : `State Jurisdiction: ${govInfo?.state}`}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 font-mono">
                Officer Address: {officerProfile?.wallet_address || govInfo?.address} • Cross-State Verification Active
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="px-3.5 py-2 rounded-xl bg-slate-950/80 border border-slate-800 text-right">
              <span className="text-[10px] text-slate-400 block uppercase font-semibold">Total Disbursed</span>
              <span className="text-base font-bold text-emerald-400 font-mono">
                ₹{govInfo?.total_disbursed_inr?.toLocaleString() || 0}
              </span>
            </div>
            <div className="px-3.5 py-2 rounded-xl bg-slate-950/80 border border-slate-800 text-right">
              <span className="text-[10px] text-slate-400 block uppercase font-semibold">Claims Anchored</span>
              <span className="text-base font-bold text-blue-400 font-mono">
                {govInfo?.total_claims_recorded || 0}
              </span>
            </div>
          </div>
        </div>

        {/* Officer Credentials & Geographic Jurisdiction Bar */}
        <div className="pt-3 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-300">
              <User className="w-3.5 h-3.5 text-purple-400" />
              <strong className="text-white">{officerProfile?.officer_name || officerProfile?.full_name || currentUser?.full_name}</strong>
              <span className="text-slate-500 font-mono">({officerProfile?.officer_reference_id || 'GOV-REF'})</span>
            </span>
            <span className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-slate-300">
              <span className="text-slate-500">Designation: </span>
              <strong className="text-slate-200">{officerProfile?.designation || 'Labour Welfare Officer'}</strong>
            </span>
          </div>

          <div className="flex items-center gap-2 text-[11px] font-mono">
            <span className="flex items-center gap-1 text-slate-400">
              <MapPin className="w-3.5 h-3.5 text-blue-400" />
              <span>State: <strong className="text-slate-200">{officerProfile?.state || govInfo?.state || 'Maharashtra'}</strong></span>
              {officerProfile?.district && (
                <span>• District: <strong className="text-slate-200">{officerProfile.district}</strong></span>
              )}
              {officerProfile?.block && (
                <span>• Block: <strong className="text-slate-200">{officerProfile.block}</strong></span>
              )}
            </span>
          </div>
        </div>
      </div>

      {actionMsg && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs font-medium">
          {actionMsg}
        </div>
      )}

      {errorMsg && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs font-medium">
          {errorMsg}
        </div>
      )}

      {/* Verification Zone: QR Upload and Live Stepper */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <QRImageUploader
            onVerify={handleVerifyQR}
            isVerifying={isVerifying}
            roleTitle="Government Authority Verification"
          />
        </div>

        <div>
          <VerificationStepper
            steps={verifiedResult?.audit_steps || []}
            isCompleted={Boolean(verifiedResult)}
          />
        </div>
      </div>

      {/* Verification Error Notice */}
      {verificationError && (
        verificationError.includes('REPLAY_ATTACK_DETECTED') ? (
          <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl text-xs space-y-2">
            <div className="flex items-center gap-2 font-bold text-amber-300 text-sm">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>QR Presentation Already Verified (Single-Use Token)</span>
            </div>
            <p className="text-slate-300 leading-relaxed">
              This specific QR presentation image was already verified by your officer account. Verifiable Presentations use single-use cryptographic nonces to protect workers against presentation replay attacks.
            </p>
            <div className="p-2.5 rounded-xl bg-slate-950/80 border border-amber-500/20 text-amber-200 font-medium">
              💡 <strong>How to re-verify this worker:</strong> Ask the worker to tap <strong>"Refresh"</strong> in their Worker Portal to generate a fresh QR presentation, then upload the new image.
            </div>
          </div>
        ) : (verificationError.includes('does not cover worker location') || verificationError.includes('JURISDICTION_MISMATCH')) ? (
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-xs space-y-2">
            <div className="flex items-center gap-2 font-bold text-rose-300 text-sm">
              <MapPin className="w-4 h-4 text-rose-400 shrink-0" />
              <span>Officer Jurisdiction Mismatch</span>
            </div>
            <p className="text-slate-300 leading-relaxed">
              Your officer jurisdiction does not currently cover this worker's recorded state location.
            </p>
            <div className="p-2.5 rounded-xl bg-slate-950/80 border border-rose-500/20 text-rose-200 space-y-1.5">
              <div>• <strong>Worker Location Update:</strong> The worker can open their Worker Portal and click <strong className="text-white">"Change Location"</strong> to set their current migration destination state to your state.</div>
              <div>• <strong>Cross-State Authority:</strong> A platform administrator can enable <strong className="text-white">Cross-State Verification</strong> for your officer account in the Admin Portal to allow cross-state migrant verifications.</div>
            </div>
          </div>
        ) : (
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-rose-400 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{verificationError}</span>
          </div>
        )
      )}

      {/* Verified Worker Government View */}
      {verifiedResult && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-purple-400" />
              <h3 className="font-bold text-white text-base">Government Worker Audit</h3>
            </div>

            {/* Cross-state badge */}
            {verifiedResult.data?.is_interstate_worker ? (
              <span className="px-3 py-1 rounded-full bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-xs font-bold flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5" />
                <span>Interstate Migrant Worker (Cross-State Portability Valid)</span>
              </span>
            ) : (
              <span className="px-3 py-1 rounded-full bg-slate-800 text-slate-300 text-xs font-semibold">
                Intra-State Worker
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Worker Full Name:</span>
              <span className="font-bold text-white text-sm block mt-0.5">
                {verifiedResult.data?.full_name}
              </span>
              <span className="text-emerald-400 text-[10px] block mt-1">
                Aadhaar: {verifiedResult.data?.masked_aadhaar}
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Origin State:</span>
              <span className="font-semibold text-white block mt-0.5">
                {verifiedResult.data?.origin_state}
              </span>
              <span className="text-slate-500 text-[10px] block mt-1">Home Jurisdiction</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Current Location:</span>
              <span className="font-semibold text-purple-400 block mt-0.5">
                {govInfo?.state}
              </span>
              <span className="text-slate-500 text-[10px] block mt-1">Receiving Jurisdiction</span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Prior Claims on File:</span>
              <span className="font-bold text-blue-400 font-mono text-sm block mt-0.5">
                {verifiedResult.data?.benefit_claims_count} Claim(s)
              </span>
              <span className="text-slate-500 text-[10px] block mt-1">On-Chain Ledger</span>
            </div>
          </div>

          {/* Scheme Selection & Disbursement Action */}
          <div className="p-5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-white flex items-center gap-2">
                  <Coins className="w-4 h-4 text-emerald-400" />
                  Evaluate Applicable Welfare Schemes
                </h4>
                <p className="text-xs text-slate-400 mt-0.5">
                  Automated duplicate-claim and cooldown interval enforcement via WelfareSchemeRegistry.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {govInfo?.schemes?.map((s) => (
                <div
                  key={s.id}
                  onClick={() => setSelectedScheme(s.id)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                    selectedScheme === s.id
                      ? 'bg-purple-950/30 border-purple-500 shadow-md'
                      : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-white">{s.name}</span>
                    <span className="font-mono font-bold text-emerald-400">₹{s.amount}</span>
                  </div>
                  <p className="text-slate-400 text-[11px] leading-tight mb-2">{s.description}</p>
                  <div className="flex items-center justify-between text-[10px] text-slate-500 pt-2 border-t border-slate-800">
                    <span>Cooldown: {Math.floor(s.cooldown_seconds / 86400)} Days</span>
                    <span className="text-purple-400 font-semibold">Cross-State Valid ✓</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={handleDisburseClaim}
                disabled={disbursing}
                className="py-2.5 px-6 bg-purple-600 hover:bg-purple-500 text-white rounded-xl font-bold text-xs shadow-lg shadow-purple-600/30 transition-all flex items-center gap-2 disabled:opacity-50"
              >
                {disbursing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Anchoring Claim on Blockchain...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>Disburse Benefit Claim on Blockchain</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Issue Verifiable Credential Panel */}
          <div className="bg-slate-950/90 border border-slate-800 rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-amber-400" />
                <h4 className="font-bold text-white text-sm">Issue Verifiable Credential to Worker Wallet</h4>
              </div>
              <span className="text-[11px] text-slate-400">Signed Official Credential</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Credential Title</label>
                <input
                  type="text"
                  value={credTitle}
                  onChange={(e) => setCredTitle(e.target.value)}
                  placeholder="e.g. BOCW Social Security Card"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Credential Type</label>
                <select
                  value={credType}
                  onChange={(e) => setCredType(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200"
                >
                  <option value="Welfare">Welfare Registration (BOCW)</option>
                  <option value="Skill">Trade Skill Certification (NSDC)</option>
                  <option value="Safety">Workplace Safety Induction</option>
                  <option value="Permit">Inter-State Migrant Work Permit</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Certified Skills / Attributes</label>
                <input
                  type="text"
                  value={credSkills}
                  onChange={(e) => setCredSkills(e.target.value)}
                  placeholder="e.g. Masonry, Scaffolding, Bricklaying"
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200"
                />
              </div>
            </div>

            <div className="flex justify-end pt-1">
              <button
                onClick={handleIssueGovernmentCredential}
                disabled={issuingCred}
                className="py-2.5 px-5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl font-bold text-xs shadow-md transition-all flex items-center gap-2 disabled:opacity-50"
              >
                {issuingCred ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Award className="w-4 h-4" />}
                <span>Issue & Anchor Credential on Blockchain</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Government Claims Ledger */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <History className="w-5 h-5 text-purple-400" />
            <h3 className="font-bold text-white text-base">State Benefit Disbursement Ledger</h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {govInfo?.total_claims_recorded} Disbursed Claims
          </span>
        </div>

        {govInfo?.all_claims && govInfo.all_claims.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 uppercase font-semibold text-[10px]">
                <tr>
                  <th className="p-3">Claim ID</th>
                  <th className="p-3">Worker DID</th>
                  <th className="p-3">Scheme Name</th>
                  <th className="p-3">Amount</th>
                  <th className="p-3">Disbursed State</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {govInfo.all_claims.map((c) => (
                  <tr key={c.claim_id} className="hover:bg-slate-800/30">
                    <td className="p-3 font-mono font-bold text-slate-300">#{c.claim_id}</td>
                    <td className="p-3 font-mono text-blue-400 truncate max-w-[160px]">{c.worker_did}</td>
                    <td className="p-3 font-medium text-slate-200">{c.scheme_name}</td>
                    <td className="p-3 font-mono font-bold text-emerald-400">₹{c.amount}</td>
                    <td className="p-3 text-slate-300">{c.officer_state}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                        DISBURSED ✓
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-6 text-slate-500 text-xs">
            No welfare disbursements anchored yet. Upload a worker QR image to evaluate and disburse benefits.
          </div>
        )}
      </div>

    </div>
  );
}
