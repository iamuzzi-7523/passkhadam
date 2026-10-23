import React, { useState, useEffect } from 'react';
import { 
  Building2, CheckCircle2, AlertCircle, PlusCircle, UserCheck, 
  Briefcase, FileCheck, RefreshCw, ShieldCheck, Lock, ExternalLink, UserX, Tag, AlertTriangle, Award,
  Search, Filter, X, RotateCcw, Clock, Shield, Users
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

  // Milestone 4 / Feature 14: Dismissal & Conclusion Modal State
  const [showDismissConfirmModal, setShowDismissConfirmModal] = useState(false);
  const [selectedStintForDismiss, setSelectedStintForDismiss] = useState(null);
  const [dismissReasonPreset, setDismissReasonPreset] = useState("PROJECT_COMPLETED");
  const [dismissStatus, setDismissStatus] = useState("COMPLETED");
  const [dismissNotes, setDismissNotes] = useState("");
  const [isSubmittingDismiss, setIsSubmittingDismiss] = useState(false);
  const [dismissError, setDismissError] = useState("");

  const CONCLUSION_PRESETS = [
    {
      id: "PROJECT_COMPLETED",
      label: "Project Completed / Work Concluded",
      status: "COMPLETED",
      defaultReason: "Project phase concluded successfully on site; deliverables met."
    },
    {
      id: "MUTUAL_AGREEMENT",
      label: "Mutual Agreement / Contract Concluded",
      status: "COMPLETED",
      defaultReason: "Mutual agreement between employer and worker upon scheduled contract term end."
    },
    {
      id: "DISCONTINUED_BY_EMPLOYER",
      label: "Discontinued by Employer",
      status: "DISCONTINUED",
      defaultReason: "Discontinued by employer due to operational site scope changes."
    },
    {
      id: "WORKER_RESIGNED",
      label: "Worker Resigned",
      status: "RESIGNED",
      defaultReason: "Worker voluntarily resigned due to personal relocation / circumstances."
    },
    {
      id: "OTHER",
      label: "Other (specify below)",
      status: "DISCONTINUED",
      defaultReason: "Employment stint concluded."
    }
  ];

  const formatStintDate = (ts) => {
    if (!ts) return "N/A";
    const date = new Date(ts > 1e11 ? ts : ts * 1000);
    return date.toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
  };

  // Feature 15: Workforce Search & Filtering State
  const [searchQuery, setSearchQuery] = useState("");
  const [tradeFilter, setTradeFilter] = useState("ALL");
  const [statusTab, setStatusTab] = useState("ALL"); // 'ALL' | 'ACTIVE' | 'CONCLUDED'

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

  const handleOpenDismissModal = (stint, defaultStatus = 'COMPLETED') => {
    setSelectedStintForDismiss(stint);
    const matched = CONCLUSION_PRESETS.find(p => p.status === defaultStatus) || CONCLUSION_PRESETS[0];
    setDismissReasonPreset(matched.id);
    setDismissStatus(matched.status);
    setDismissNotes(matched.defaultReason);
    setDismissError("");
    setShowDismissConfirmModal(true);
  };

  const handlePresetChange = (presetId) => {
    setDismissReasonPreset(presetId);
    const preset = CONCLUSION_PRESETS.find(p => p.id === presetId);
    if (preset) {
      setDismissStatus(preset.status);
      setDismissNotes(preset.defaultReason);
    }
  };

  const handleConfirmDismiss = async (e) => {
    e.preventDefault();
    if (!selectedStintForDismiss) return;
    setIsSubmittingDismiss(true);
    setDismissError("");
    try {
      const finalReason = dismissNotes.trim() || 
        CONCLUSION_PRESETS.find(p => p.id === dismissReasonPreset)?.defaultReason || 
        `Employment stint #${selectedStintForDismiss.id} concluded as ${dismissStatus}`;

      const res = await apiFetch("/api/v1/employer/employment-status", {
        method: "PUT",
        body: {
          employment_id: selectedStintForDismiss.id,
          new_status: dismissStatus,
          reason: finalReason
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to conclude employment stint");

      setActionMsg(data.message || `Employment #${selectedStintForDismiss.id} successfully updated to ${dismissStatus}. Record preserved.`);
      setShowDismissConfirmModal(false);
      setSelectedStintForDismiss(null);
      setDismissNotes("");
      await fetchEmployerData();
    } catch (err) {
      setDismissError(err.message || "Failed to update employment status");
    } finally {
      setIsSubmittingDismiss(false);
    }
  };

  const handleStatusUpdate = async (empId, newStatus) => {
    const stint = employerInfo?.employments?.find(e => e.id === empId);
    if (stint) {
      handleOpenDismissModal(stint, newStatus);
    } else {
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

  // Feature 15 & 16: Derived Workforce Data and Status Formatting
  const allEmployments = employerInfo?.employments || [];
  const activeCount = allEmployments.filter(e => (e.status || '').toUpperCase() === 'ACTIVE').length;
  const concludedCount = allEmployments.filter(e => (e.status || '').toUpperCase() !== 'ACTIVE').length;

  const availableTrades = Array.from(new Set([
    ...(employerInfo?.approved_categories || []),
    ...allEmployments.map(e => e.category)
  ])).filter(Boolean);

  const filteredEmployments = allEmployments.filter(emp => {
    const statusUpper = (emp.status || '').toUpperCase();
    if (statusTab === 'ACTIVE' && statusUpper !== 'ACTIVE') return false;
    if (statusTab === 'CONCLUDED' && statusUpper === 'ACTIVE') return false;
    if (tradeFilter !== 'ALL' && emp.category !== tradeFilter) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      const matchId = String(emp.id).toLowerCase().includes(q) || `#${emp.id}`.toLowerCase().includes(q);
      const matchDid = (emp.worker_did || '').toLowerCase().includes(q);
      const matchCategory = (emp.category || '').toLowerCase().includes(q);
      const matchRole = (emp.job_role || '').toLowerCase().includes(q);
      const matchLoc = (emp.location || '').toLowerCase().includes(q);
      const matchName = (emp.worker_name || emp.name || '').toLowerCase().includes(q);
      if (!matchId && !matchDid && !matchCategory && !matchRole && !matchLoc && !matchName) {
        return false;
      }
    }
    return true;
  });

  const renderStintStatusBadge = (status) => {
    const norm = (status || '').toUpperCase();
    switch (norm) {
      case 'ACTIVE':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5 w-fit">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            ACTIVE
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30 flex items-center gap-1 w-fit">
            ✓ COMPLETED
          </span>
        );
      case 'DISCONTINUED':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1 w-fit">
            ⚠️ DISCONTINUED
          </span>
        );
      case 'DISMISSED':
      case 'TERMINATED':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center gap-1 w-fit">
            ✕ {norm}
          </span>
        );
      case 'RESIGNED':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center gap-1 w-fit">
            RESIGNED
          </span>
        );
      case 'SUSPENDED':
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 w-fit">
            SUSPENDED
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700 w-fit">
            {norm || 'RECORDED'}
          </span>
        );
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

      {/* Feature 16: Organization PENDING_REVIEW Actionable Banner */}
      {(employerInfo?.status === 'PENDING_REVIEW' || employerInfo?.status === 'PENDING') && (
        <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 space-y-2">
          <div className="flex items-center gap-2 font-bold text-sm text-amber-200">
            <Clock className="w-4 h-4 text-amber-400 shrink-0" />
            <span>Organization Registration Under Platform Review (PENDING_REVIEW)</span>
          </div>
          <p className="text-slate-300 leading-relaxed text-[11px]">
            Your employer organization registration for <strong className="text-white">{employerInfo?.name}</strong> has been received and is currently undergoing administrative review. Category approvals and on-chain contract creation will be enabled upon Admin activation token confirmation.
          </p>
        </div>
      )}

      {/* Feature 16: Web-First Verification & Stint Permanence Guidance Notice */}
      <div className="p-4 rounded-2xl bg-slate-900 border border-blue-500/20 text-xs text-slate-300 space-y-2 shadow-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-bold text-white text-sm">
            <ShieldCheck className="w-4 h-4 text-blue-400 shrink-0" />
            <span>Web-First Verification &amp; Stint Permanence Guidance</span>
          </div>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/30">
            Zero-Camera Engine
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1 text-[11px]">
          <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
            <span className="font-semibold text-blue-300 block">1. No Camera Hardware Required</span>
            <p className="text-slate-400 leading-relaxed">
              Upload worker QR images (PNG) or use the 1-click simulation button below to verify credentials without physical webcams.
            </p>
          </div>
          <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
            <span className="font-semibold text-amber-300 block">2. Single-Use Replay Protection</span>
            <p className="text-slate-400 leading-relaxed">
              Presentations expire after 5 minutes or 1 verification. Workers can generate a fresh QR in 1 second by tapping "Refresh".
            </p>
          </div>
          <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
            <span className="font-semibold text-emerald-300 block">3. Immutable Historical Provenance</span>
            <p className="text-slate-400 leading-relaxed">
              Completed or dismissed stints remain anchored in the worker's portable wallet as verified proof of employment tenure.
            </p>
          </div>
        </div>
      </div>

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

      {/* Feature 15: Workforce Management with Real-Time Search, Filter & Status Tabs */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-blue-400" />
            <div>
              <h3 className="font-bold text-white text-base">Company Workforce & Stint History</h3>
              <p className="text-[11px] text-slate-400">Search and filter active contracts and immutable past employment stints</p>
            </div>
          </div>
          <span className="text-xs text-slate-400 font-mono bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800">
            Active: <strong className="text-emerald-400">{activeCount}</strong> • Total: <strong className="text-white">{allEmployments.length}</strong>
          </span>
        </div>

        {/* Search, Trade Filter & Status Tabs Controls */}
        <div className="space-y-3 pt-1">
          {/* Top Row: Search Input & Trade Dropdown */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-2 relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by worker DID, stint #, job role, trade, or location..."
                className="w-full pl-9 pr-8 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 outline-none focus:border-blue-500 transition-all font-sans"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs p-0.5"
                  title="Clear search"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <div className="relative">
              <Filter className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <select
                value={tradeFilter}
                onChange={(e) => setTradeFilter(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 outline-none focus:border-blue-500 transition-all appearance-none cursor-pointer"
              >
                <option value="ALL">All Trades ({availableTrades.length > 0 ? `${availableTrades.length} categories` : 'All'})</option>
                {availableTrades.map((trade, idx) => (
                  <option key={idx} value={trade}>{trade}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Bottom Row: Status Tabs & Counts */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
              <button
                type="button"
                onClick={() => setStatusTab('ALL')}
                className={`px-3 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
                  statusTab === 'ALL'
                    ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>All Stints</span>
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-800 text-slate-300 font-mono">
                  {allEmployments.length}
                </span>
              </button>
              <button
                type="button"
                onClick={() => setStatusTab('ACTIVE')}
                className={`px-3 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
                  statusTab === 'ACTIVE'
                    ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>Active Only</span>
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-emerald-950 border border-emerald-500/40 text-emerald-300 font-mono">
                  {activeCount}
                </span>
              </button>
              <button
                type="button"
                onClick={() => setStatusTab('CONCLUDED')}
                className={`px-3 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
                  statusTab === 'CONCLUDED'
                    ? 'bg-purple-600/30 text-purple-300 border border-purple-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>Concluded / Past</span>
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-purple-950 border border-purple-500/40 text-purple-300 font-mono">
                  {concludedCount}
                </span>
              </button>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-400 font-mono text-[11px]">
                Showing <strong className="text-white">{filteredEmployments.length}</strong> of{' '}
                <strong className="text-white">{allEmployments.length}</strong> stints
              </span>
              {(searchQuery || tradeFilter !== 'ALL' || statusTab !== 'ALL') && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery('');
                    setTradeFilter('ALL');
                    setStatusTab('ALL');
                  }}
                  className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-[11px] font-medium transition flex items-center gap-1"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Reset Filters</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Results Table & Fallbacks */}
        {allEmployments.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-xs space-y-2">
            <Briefcase className="w-8 h-8 mx-auto text-slate-600" />
            <p className="font-medium text-slate-400">No employment contracts created yet.</p>
            <p className="text-[11px] text-slate-600">Verify a worker QR code above using zero-camera simulation to offer on-chain employment.</p>
          </div>
        ) : filteredEmployments.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-xs space-y-2.5 bg-slate-950/40 rounded-xl border border-slate-800">
            <Search className="w-8 h-8 mx-auto text-slate-600" />
            <p className="font-semibold text-slate-300">No workforce stints match filter criteria</p>
            <p className="text-[11px] text-slate-500 max-w-md mx-auto">
              No stints found matching query {searchQuery && <span className="text-blue-300 font-mono">"{searchQuery}"</span>} with trade <span className="text-blue-300 font-mono">"{tradeFilter}"</span> and status <span className="text-blue-300 font-mono">"{statusTab}"</span>.
            </p>
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                setTradeFilter('ALL');
                setStatusTab('ALL');
              }}
              className="px-3.5 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 rounded-lg text-xs font-medium transition inline-flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset All Filters</span>
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 uppercase font-semibold text-[10px]">
                <tr>
                  <th className="p-3">ID</th>
                  <th className="p-3">Worker Identity</th>
                  <th className="p-3">Category</th>
                  <th className="p-3">Level / Nature</th>
                  <th className="p-3">Job Role</th>
                  <th className="p-3">Work Location</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {filteredEmployments.map((emp) => (
                  <tr key={emp.id} className="hover:bg-slate-800/30">
                    <td className="p-3 font-mono font-bold text-slate-300">#{emp.id}</td>
                    <td className="p-3 max-w-[180px]">
                      <span className="font-semibold text-white block truncate">
                        {emp.worker_name || "Registered Worker"}
                      </span>
                      <span className="font-mono text-blue-400 truncate block text-[11px]" title={emp.worker_did}>
                        {emp.worker_did}
                      </span>
                    </td>
                    <td className="p-3 font-medium text-slate-200">{emp.category}</td>
                    <td className="p-3 text-slate-300">{emp.level || "Skilled"} • {emp.nature_of_employment || "Contract"}</td>
                    <td className="p-3 text-slate-300">{emp.job_role}</td>
                    <td className="p-3 text-slate-400">{emp.location}</td>
                    <td className="p-3">
                      {renderStintStatusBadge(emp.status)}
                    </td>
                    <td className="p-3 text-right space-x-1.5">
                      {emp.status === 'ACTIVE' && (
                        <>
                          <button
                            type="button"
                            onClick={() => handleOpenDismissModal(emp, 'COMPLETED')}
                            className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg font-semibold text-[11px] border border-slate-700 hover:border-slate-600 transition shadow-sm"
                            title="Conclude stint (Project completed or mutual agreement)"
                          >
                            Complete
                          </button>
                          <button
                            type="button"
                            onClick={() => handleOpenDismissModal(emp, 'DISCONTINUED')}
                            className="px-2.5 py-1 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 hover:text-rose-200 rounded-lg font-semibold text-[11px] border border-rose-800/50 hover:border-rose-700 transition shadow-sm"
                            title="Discontinue stint (Early conclusion or operational change)"
                          >
                            Discontinue
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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

      {/* Feature 14: Conclude / Dismiss Employment Stint Confirmation Modal */}
      {showDismissConfirmModal && selectedStintForDismiss && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 text-xs animate-in fade-in zoom-in-95 duration-150">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-white text-base">Conclude Employment Stint</h3>
                  <p className="text-[11px] text-slate-400">Confirm conclusion or discontinuation on permanent ledger</p>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => {
                  setShowDismissConfirmModal(false);
                  setSelectedStintForDismiss(null);
                }} 
                className="text-slate-400 hover:text-white transition p-1"
              >
                ✕
              </button>
            </div>

            {/* Invariant Guidance Notice */}
            <div className="p-3 bg-amber-500/10 border border-amber-500/25 rounded-xl text-amber-200/90 text-xs flex items-start gap-2.5 leading-relaxed">
              <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-amber-300">Permanent Record Notice:</span> Concluding this stint will mark it finished on the blockchain and SQLite ledger. Under PassKhadam permanence invariants, this historical record remains permanently attached to the worker's portable employment history.
              </div>
            </div>

            {/* Worker & Stint Summary Card */}
            <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-4 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Worker Details</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30">
                  Stint #{selectedStintForDismiss.id}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs pt-1">
                <div>
                  <span className="text-slate-400 block text-[11px]">Worker Name / Identity:</span>
                  <span className="font-bold text-white block mt-0.5">
                    {selectedStintForDismiss.worker_name || "Registered Worker"}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500 truncate block mt-0.5" title={selectedStintForDismiss.worker_did}>
                    {selectedStintForDismiss.worker_did}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Trade & Job Role:</span>
                  <span className="font-semibold text-slate-200 block mt-0.5">
                    {selectedStintForDismiss.category} • {selectedStintForDismiss.job_role}
                  </span>
                  <span className="text-[10px] text-slate-400 block mt-0.5">
                    {selectedStintForDismiss.level || "Skilled"} ({selectedStintForDismiss.nature_of_employment || "Contract"})
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Site Location:</span>
                  <span className="font-medium text-slate-300 block mt-0.5">
                    {selectedStintForDismiss.location || "N/A"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Stint Start Date:</span>
                  <span className="font-medium text-slate-300 block mt-0.5">
                    {formatStintDate(selectedStintForDismiss.start_date)}
                  </span>
                </div>
              </div>
            </div>

            {/* Conclusion Form */}
            <form onSubmit={handleConfirmDismiss} className="space-y-4">
              <div>
                <label className="block text-slate-300 font-semibold mb-1.5">
                  Conclusion Reason & Target Status
                </label>
                <select
                  value={dismissReasonPreset}
                  onChange={(e) => handlePresetChange(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white outline-none focus:border-blue-500 transition"
                >
                  {CONCLUSION_PRESETS.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.label} [{preset.status}]
                    </option>
                  ))}
                </select>
                <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                  <span>Ledger status transition: <strong className="text-blue-400">{selectedStintForDismiss.status}</strong> → <strong className="text-emerald-400">{dismissStatus}</strong></span>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1.5">
                  Conclusion Notes & Description (Saved to permanent history)
                </label>
                <textarea
                  value={dismissNotes}
                  onChange={(e) => setDismissNotes(e.target.value)}
                  rows={3}
                  placeholder="Provide context or certificate notes regarding this stint conclusion..."
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-xl text-white outline-none focus:border-blue-500 transition resize-none text-xs"
                  required
                />
                <p className="text-[10px] text-slate-400 mt-1">
                  This note will be recorded in the on-chain event ledger and visible on the worker's verified employment certificate.
                </p>
              </div>

              {dismissError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{dismissError}</span>
                </div>
              )}

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-800">
                <button
                  type="button"
                  disabled={isSubmittingDismiss}
                  onClick={() => {
                    setShowDismissConfirmModal(false);
                    setSelectedStintForDismiss(null);
                  }}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl font-medium transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingDismiss}
                  className={`px-5 py-2 rounded-xl font-bold text-white transition flex items-center gap-2 shadow-lg ${
                    dismissStatus === 'DISCONTINUED'
                      ? 'bg-rose-700 hover:bg-rose-600 shadow-rose-900/30'
                      : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-900/30'
                  }`}
                >
                  {isSubmittingDismiss ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Updating Ledger...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Confirm & Conclude Stint</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
