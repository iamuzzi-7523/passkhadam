import React, { useState, useEffect } from 'react';
import { 
  Building2, CheckCircle2, AlertCircle, PlusCircle, UserCheck, 
  Briefcase, FileCheck, RefreshCw, ShieldCheck, Lock, ExternalLink, UserX, Tag, AlertTriangle, Award
} from 'lucide-react';
import QRImageUploader from '../common/QRImageUploader';
import VerificationStepper from '../common/VerificationStepper';
import { useAuth } from '../../context/AuthContext';
import { apiFetch } from '../../utils/api';

export default function EmployerPortal({ currentLang = 'en' }) {
  const { currentUser } = useAuth();
  const [employerInfo, setEmployerInfo] = useState(null);
  const [categoryRequests, setCategoryRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifiedResult, setVerifiedResult] = useState(null);
  const [verificationError, setVerificationError] = useState("");
  const [showOfferModal, setShowOfferModal] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [showCredModal, setShowCredModal] = useState(false);
  const [credTitle, setCredTitle] = useState("Site Trade Competency Certificate");
  const [credType, setCredType] = useState("Experience");
  const [credSkills, setCredSkills] = useState("");
  const [issuingCred, setIssuingCred] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedLevel, setSelectedLevel] = useState("Skilled");
  const [selectedNature, setSelectedNature] = useState("Contract");
  const [jobRole, setJobRole] = useState("Mason Lead");
  const [workLocation, setWorkLocation] = useState("Bengaluru Site A");
  const [catRequest, setCatRequest] = useState("Heavy Machinery Operator");
  const [catReason, setCatReason] = useState("Expanding into excavation work");
  const [actionMsg, setActionMsg] = useState("");

  const fetchEmployerData = async () => {
    try {
      setLoading(true);
      const res = await apiFetch("/api/v1/employer/info");
      if (res.ok) {
        const data = await res.json();
        setEmployerInfo(data);
        if (data.approved_categories?.length > 0) {
          setSelectedCategory(data.approved_categories[0]);
        }
      }
      const catRes = await apiFetch("/api/v1/employer/categories");
      if (catRes.ok) {
        const catData = await catRes.json();
        setCategoryRequests(catData);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmployerData();
  }, [currentUser]);

  const handleVerifyQR = async (file) => {
    setIsVerifying(true);
    setVerificationError("");
    setVerifiedResult(null);
    setActionMsg("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await apiFetch("/api/v1/employer/verify-worker-qr", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Worker QR verification failed");
      }
      setVerifiedResult(data);
    } catch (err) {
      setVerificationError(err.message);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleCreateEmployment = async (e) => {
    e.preventDefault();
    if (!verifiedResult) return;

    try {
      const res = await apiFetch("/api/v1/employer/create-employment", {
        method: "POST",
        body: {
          worker_did: verifiedResult.worker_did,
          category: selectedCategory,
          level: selectedLevel,
          nature_of_employment: selectedNature,
          job_role: jobRole,
          work_location: workLocation
        }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to create employment record");
      }
      setActionMsg(`Employment contract #${data.employment_record.id} successfully created and anchored on blockchain!`);
      setShowOfferModal(false);
      await fetchEmployerData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleIssueCredential = async (e) => {
    e.preventDefault();
    if (!verifiedResult) return;
    setIssuingCred(true);
    setActionMsg("");
    setErrorMsg("");
    try {
      const res = await apiFetch("/api/v1/employer/credentials/issue", {
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
      if (!res.ok) throw new Error(data.detail || "Failed to issue credential");
      setActionMsg(`Verifiable Credential "${data.title}" successfully issued and anchored to worker wallet!`);
      setShowCredModal(false);
    } catch (e) {
      setErrorMsg(e.message || "Failed to issue credential");
    } finally {
      setIssuingCred(false);
    }
  };

  const handleStatusUpdate = async (empId, newStatus) => {
    try {
      const res = await apiFetch("/api/v1/employer/employment-status", {
        method: "PUT",
        body: {
          employment_id: empId,
          new_status: newStatus,
          reason: `Updated to ${newStatus} by employer supervisor`
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      setActionMsg(data.message);
      await fetchEmployerData();
    } catch (e) {
      alert(e.message);
    }
  };

  const handleCategoryRequest = async (e) => {
    e.preventDefault();
    try {
      const res = await apiFetch("/api/v1/employer/request-category", {
        method: "POST",
        body: { category: catRequest, reason: catReason }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      setActionMsg(data.message);
      setShowCategoryModal(false);
      await fetchEmployerData();
    } catch (e) {
      alert(e.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mr-2" />
        <span>Loading Employer Portal...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Employer Organization Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-emerald-600/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center text-2xl font-bold">
              🏢
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">{employerInfo?.name}</h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  {employerInfo?.status}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 font-mono">
                Reg: {employerInfo?.reg_number} • Org Address: {employerInfo?.address}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCategoryModal(true)}
              className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold border border-slate-700 transition-all flex items-center gap-1.5"
            >
              <PlusCircle className="w-3.5 h-3.5 text-blue-400" />
              <span>Request Category</span>
            </button>
          </div>
        </div>

        {/* Approved Categories & Scope Badges */}
        <div className="mt-4 pt-4 border-t border-slate-800 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-400 font-semibold mr-1">Authorized Categories:</span>
          {employerInfo?.approved_categories?.map((cat, idx) => (
            <span
              key={idx}
              className="px-2.5 py-1 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-300 font-medium"
            >
              ✓ {cat}
            </span>
          ))}
          <span className="text-slate-500 mx-2">•</span>
          <span className="text-slate-400 font-semibold mr-1">Levels:</span>
          {employerInfo?.approved_levels?.map((lvl, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-[11px]"
            >
              {lvl}
            </span>
          ))}
        </div>
      </div>

      {/* Category Authorization Scope Directory */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Tag className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-bold text-white">Category Scopes &amp; Authorizations</h3>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            {categoryRequests.length} Scopes Tracked
          </span>
        </div>

        {categoryRequests.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No category scope requests on record.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                <tr>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Skill Level</th>
                  <th className="py-2.5 px-3">Nature of Employment</th>
                  <th className="py-2.5 px-3">Version</th>
                  <th className="py-2.5 px-3">Scope Standing</th>
                  <th className="py-2.5 px-3">Review Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {categoryRequests.map((req) => (
                  <tr key={req.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-2.5 px-3 font-semibold text-white font-sans">{req.category}</td>
                    <td className="py-2.5 px-3 text-slate-300">{req.skill_level || 'Skilled'}</td>
                    <td className="py-2.5 px-3 text-slate-300">{req.nature_of_employment || 'Contract'}</td>
                    <td className="py-2.5 px-3 text-blue-400">v{req.request_version || 1}</td>
                    <td className="py-2.5 px-3">
                      {req.is_active_scope ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                          ACTIVE SCOPE
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">
                          INACTIVE
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        req.status === 'APPROVED' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' :
                        req.status === 'PENDING' ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' :
                        req.status === 'DISCONTINUED' ? 'bg-purple-500/15 text-purple-300 border border-purple-500/30' :
                        'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                      }`}>
                        {req.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {actionMsg && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs font-medium">
          {actionMsg}
        </div>
      )}

      {/* Verification Zone: QR Upload and Live Stepper */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <QRImageUploader
            onVerify={handleVerifyQR}
            isVerifying={isVerifying}
            roleTitle="Employer Verification"
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
              This specific QR presentation image was already verified by your organization. Verifiable Presentations use single-use cryptographic nonces to protect workers against replay attacks.
            </p>
            <div className="p-2.5 rounded-xl bg-slate-950/80 border border-amber-500/20 text-amber-200 font-medium">
              💡 <strong>How to re-verify or create a new contract:</strong> Ask the worker to tap <strong>"Refresh"</strong> in their Worker Portal to generate a fresh QR presentation, then upload the new image.
            </div>
          </div>
        ) : (
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{verificationError}</span>
          </div>
        )
      )}

      {/* Verified Worker Card (RBAC Permitted View) */}
      {verifiedResult && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <UserCheck className="w-5 h-5 text-emerald-400" />
              <h3 className="font-bold text-white text-base">Verified Worker Details</h3>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Identity & BOCW Cryptographically Verified</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Worker Full Name:</span>
              <span className="font-bold text-white text-sm block mt-0.5">
                {verifiedResult.data?.full_name}
              </span>
              <span className="text-slate-500 text-[10px] block mt-1">
                Aadhaar: Protected (Zero PII leak)
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Worker DID:</span>
              <span className="font-mono text-blue-400 font-semibold block mt-0.5 truncate">
                {verifiedResult.worker_did}
              </span>
              <span className="text-emerald-400 text-[10px] block mt-1">
                ✓ Anchored on WorkerIdentityRegistry
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
              <span className="text-slate-400 block text-[11px]">Current Work Status:</span>
              <span className="font-semibold text-emerald-400 block mt-0.5">
                {verifiedResult.data?.current_employment_status}
              </span>
              <span className="text-slate-400 text-[10px] block mt-1">
                Prior Records: {verifiedResult.data?.employment_history_count}
              </span>
            </div>
          </div>

          {/* Verified Skills & Certifications */}
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
            <span className="text-xs font-semibold text-slate-300 block">Verified Trade Skills & Safety Induction:</span>
            <div className="flex flex-wrap gap-2">
              {verifiedResult.data?.skills?.map((skill, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-blue-600/15 border border-blue-500/30 text-blue-300 text-xs font-semibold"
                >
                  ✓ {skill}
                </span>
              ))}
              <span className="px-2.5 py-1 rounded-lg bg-emerald-600/15 border border-emerald-500/30 text-emerald-300 text-xs font-semibold">
                ✓ BOCW Safety Certified
              </span>
            </div>
          </div>

          {/* Action CTAs */}
          <div className="pt-2 flex justify-end gap-3 flex-wrap">
            <button
              onClick={() => setShowCredModal(true)}
              className="py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold text-xs shadow-lg transition-all flex items-center gap-2"
            >
              <Award className="w-4 h-4" />
              <span>Issue Trade / Experience Credential</span>
            </button>
            <button
              onClick={() => setShowOfferModal(true)}
              className="py-2.5 px-6 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold text-xs shadow-lg shadow-emerald-600/30 transition-all flex items-center gap-2"
            >
              <Briefcase className="w-4 h-4" />
              <span>Offer On-Chain Employment Contract</span>
            </button>
          </div>
        </div>
      )}

      {/* Workforce Management Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-blue-400" />
            <h3 className="font-bold text-white text-base">Company Workforce & Stint History</h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            Active: {employerInfo?.active_workers} • Total: {employerInfo?.employments?.length}
          </span>
        </div>

        {employerInfo?.employments && employerInfo.employments.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 uppercase font-semibold text-[10px]">
                <tr>
                  <th className="p-3">ID</th>
                  <th className="p-3">Worker DID</th>
                  <th className="p-3">Category</th>
                  <th className="p-3">Level / Nature</th>
                  <th className="p-3">Job Role</th>
                  <th className="p-3">Work Location</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {employerInfo.employments.map((emp) => (
                  <tr key={emp.id} className="hover:bg-slate-800/30">
                    <td className="p-3 font-mono font-bold text-slate-300">#{emp.id}</td>
                    <td className="p-3 font-mono text-blue-400 truncate max-w-[140px]">{emp.worker_did}</td>
                    <td className="p-3 font-medium text-slate-200">{emp.category}</td>
                    <td className="p-3 text-slate-300">{emp.level || "Skilled"} • {emp.nature_of_employment || "Contract"}</td>
                    <td className="p-3 text-slate-300">{emp.job_role}</td>
                    <td className="p-3 text-slate-400">{emp.location}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        emp.status === 'ACTIVE'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : emp.status === 'DISMISSED'
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                          : 'bg-slate-800 text-slate-400'
                      }`}>
                        {emp.status}
                      </span>
                    </td>
                    <td className="p-3 text-right space-x-1">
                      {emp.status === 'ACTIVE' && (
                        <>
                          <button
                            onClick={() => handleStatusUpdate(emp.id, 'COMPLETED')}
                            className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded font-semibold text-[10px] border border-slate-700"
                          >
                            Complete
                          </button>
                          <button
                            onClick={() => handleStatusUpdate(emp.id, 'DISMISSED')}
                            className="px-2 py-1 bg-rose-900/40 hover:bg-rose-900 text-rose-300 rounded font-semibold text-[10px] border border-rose-800"
                          >
                            Dismiss
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-6 text-slate-500 text-xs">
            No employment contracts created yet. Verify a worker QR code to offer employment.
          </div>
        )}
      </div>

      {/* Offer Employment Modal */}
      {showOfferModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Offer Employment Contract</h3>
              <button onClick={() => setShowOfferModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateEmployment} className="space-y-3">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">
                  Authorized Job Category
                </label>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                >
                  {employerInfo?.approved_categories?.map((cat, idx) => (
                    <option key={idx} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Employment Level</label>
                  <select
                    value={selectedLevel}
                    onChange={(e) => setSelectedLevel(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  >
                    <option value="Skilled">Skilled</option>
                    <option value="Semi-Skilled">Semi-Skilled</option>
                    <option value="Unskilled">Unskilled</option>
                    <option value="Supervisory">Supervisory</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Nature of Employment</label>
                  <select
                    value={selectedNature}
                    onChange={(e) => setSelectedNature(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  >
                    <option value="Contract">Contract</option>
                    <option value="Permanent">Permanent</option>
                    <option value="Project-Based">Project-Based</option>
                    <option value="Seasonal">Seasonal</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Job Role Title</label>
                <input
                  type="text"
                  value={jobRole}
                  onChange={(e) => setJobRole(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Work Location</label>
                <input
                  type="text"
                  value={workLocation}
                  onChange={(e) => setWorkLocation(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowOfferModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold shadow-md shadow-emerald-600/30"
                >
                  Anchor Employment on Blockchain
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Issue Verifiable Credential Modal */}
      {showCredModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-white text-base">Issue Trade / Experience Credential</h3>
              </div>
              <button onClick={() => setShowCredModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleIssueCredential} className="space-y-3">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">Credential Title</label>
                <input
                  type="text"
                  value={credTitle}
                  onChange={(e) => setCredTitle(e.target.value)}
                  placeholder="e.g. Senior Electrician Experience Certificate"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Credential Type</label>
                <select
                  value={credType}
                  onChange={(e) => setCredType(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                >
                  <option value="Experience">Trade Experience Certificate</option>
                  <option value="Skill">Verified Trade Skill / Competency</option>
                  <option value="Safety">Site Safety Induction & Clearance</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Competencies / Skills (Comma Separated)</label>
                <input
                  type="text"
                  value={credSkills}
                  onChange={(e) => setCredSkills(e.target.value)}
                  placeholder="e.g. Electrical Conduit, Cable Pulling, Panel Wiring"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCredModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={issuingCred}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold flex items-center gap-1.5"
                >
                  {issuingCred ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Award className="w-4 h-4" />}
                  <span>Issue to Worker Wallet</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Category Request Modal */}
      {showCategoryModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Request Additional Category</h3>
              <button onClick={() => setShowCategoryModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCategoryRequest} className="space-y-3">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">Category Name</label>
                <input
                  type="text"
                  value={catRequest}
                  onChange={(e) => setCatRequest(e.target.value)}
                  placeholder="e.g. Heavy Machinery Operator"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Business Rationale</label>
                <textarea
                  value={catReason}
                  onChange={(e) => setCatReason(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCategoryModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold"
                >
                  Submit Request to Admin
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
