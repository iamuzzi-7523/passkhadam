import React, { useState, useEffect } from 'react';
import { 
  User, CheckCircle, AlertTriangle, QrCode, Shield, Briefcase, 
  Download, RefreshCw, Key, Award, FileText, ChevronRight, MapPin, Sparkles, Volume2, Navigation
} from 'lucide-react';
import VoiceNarrator from '../common/VoiceNarrator';
import { getTranslation } from '../../i18n/translations';
import { useAuth } from '../../context/AuthContext';
import { apiFetch } from '../../utils/api';

const INDIAN_STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
  'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand',
  'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
  'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
  'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
  'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Delhi', 'Jammu & Kashmir', 'Ladakh', 'Puducherry'
];

export default function WorkerPortal({ currentLang = 'en' }) {
  const { currentUser } = useAuth();
  const [profile, setProfile] = useState(null);
  const [wallet, setWallet] = useState(null);
  const [qrData, setQrData] = useState(null);
  const [timerSeconds, setTimerSeconds] = useState(300);
  const [loading, setLoading] = useState(true);
  const [verifyingAadhaar, setVerifyingAadhaar] = useState(false);
  const [showAadhaarModal, setShowAadhaarModal] = useState(false);
  const [showLocationModal, setShowLocationModal] = useState(false);
  const [targetCurrentState, setTargetCurrentState] = useState('Goa');
  const [targetAddress, setTargetAddress] = useState('');
  const [updatingLocation, setUpdatingLocation] = useState(false);
  const [aadhaarInput, setAadhaarInput] = useState("");
  const [nameInput, setNameInput] = useState(currentUser?.full_name || "");
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  useEffect(() => {
    if (currentUser?.full_name && !nameInput) {
      setNameInput(currentUser.full_name);
    }
  }, [currentUser]);

  const fetchWorkerData = async () => {
    try {
      setLoading(true);
      setErrorMsg("");
      const profRes = await apiFetch('/api/v1/worker/profile/me');
      if (profRes.ok) {
        const p = await profRes.json();
        setProfile(p);
        if (p.is_credential_anchored) {
          const wRes = await apiFetch('/api/v1/worker/wallet/me');
          if (wRes.ok) setWallet(await wRes.json());

          // Revalidate dynamic source status before fetching QR presentation
          if (p.aadhaar_status === 'ACTIVE') {
            const qrRes = await apiFetch('/api/v1/worker/presentation/qr-card/me');
            if (qrRes.ok) {
              const q = await qrRes.json();
              setQrData(q);
              setTimerSeconds(q.expires_in_seconds || 300);
            } else {
              setQrData(null);
            }
          } else {
            setQrData(null);
          }
        } else {
          setQrData(null);
          setWallet(null);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkerData();
  }, [currentUser]);

  // Expiration countdown
  useEffect(() => {
    if (!qrData || timerSeconds <= 0) return;
    const interval = setInterval(() => {
      setTimerSeconds(prev => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [qrData, timerSeconds]);

  const handleVerifyAadhaar = async (e) => {
    e.preventDefault();
    setVerifyingAadhaar(true);
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const res = await apiFetch('/api/v1/worker/verify-aadhaar/me', {
        method: "POST",
        body: { aadhaar_number: aadhaarInput, full_name: nameInput }
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Aadhaar verification failed");
      }
      setSuccessMsg("Government Identity Successfully Verified & DID Anchored on Blockchain!");
      setShowAadhaarModal(false);
      await fetchWorkerData();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setVerifyingAadhaar(false);
    }
  };

  const handleRefreshQr = async () => {
    try {
      // Re-fetch entire worker profile to get authoritative live status
      const profRes = await apiFetch('/api/v1/worker/profile/me');
      if (profRes.ok) {
        const p = await profRes.json();
        setProfile(p);
        if (p.aadhaar_status !== 'ACTIVE') {
          setQrData(null);
          setErrorMsg(`QR Presentation locked: Source Aadhaar record status is currently ${p.aadhaar_status}.`);
          return;
        }
      }

      const res = await apiFetch('/api/v1/worker/presentation/qr-card/me');
      if (res.ok) {
        const q = await res.json();
        setQrData(q);
        setTimerSeconds(q.expires_in_seconds || 300);
        setErrorMsg("");
      } else {
        setQrData(null);
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Unable to generate QR presentation.");
      }
    } catch (e) {
      setQrData(null);
      console.error(e);
      setErrorMsg("Network error generating fresh QR presentation.");
    }
  };

  const handleDownloadQr = async () => {
    if (profile?.aadhaar_status !== 'ACTIVE') {
      setErrorMsg(`Cannot download QR card: Citizen Aadhaar record status is ${profile?.aadhaar_status || 'NOT ACTIVE'}.`);
      return;
    }
    try {
      const res = await apiFetch('/api/v1/worker/presentation/download-qr/me');
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `passkhadam_${profile?.did?.slice(-8) || 'worker'}_qr.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Unable to download QR presentation. Live check failed or status is not active.");
      }
    } catch (e) {
      setErrorMsg("Network error while downloading QR presentation.");
    }
  };

  const handleOpenLocationModal = () => {
    setTargetCurrentState(profile?.current_state || 'Goa');
    setTargetAddress(profile?.address || '');
    setErrorMsg("");
    setShowLocationModal(true);
  };

  const handleUpdateLocation = async (e) => {
    e.preventDefault();
    if (!targetCurrentState) {
      alert("Please select a target state.");
      return;
    }
    try {
      setUpdatingLocation(true);
      setErrorMsg("");
      const res = await apiFetch('/api/v1/worker/profile/me', {
        method: 'PUT',
        body: {
          current_state: targetCurrentState,
          address: targetAddress || undefined
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to update location');
      setSuccessMsg(`✓ Current migration state updated to ${targetCurrentState}! Fresh presentations will now reflect this state.`);
      setShowLocationModal(false);
      await fetchWorkerData();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setUpdatingLocation(false);
    }
  };

  const renderAadhaarStatusBadge = (status) => {
    switch (status) {
      case 'ACTIVE':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center gap-1">
            <span>✓</span> VERIFIED & VALID
          </span>
        );
      case 'INACTIVE':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 flex items-center gap-1">
            <span>⚠️</span> IDENTITY RECORD INACTIVE
          </span>
        );
      case 'SUSPENDED':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40 flex items-center gap-1">
            <span>🚫</span> IDENTITY RECORD SUSPENDED
          </span>
        );
      case 'UNAVAILABLE':
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-yellow-500/20 text-yellow-300 border border-yellow-500/40 flex items-center gap-1">
            <span>⚠️</span> STATUS CHECK UNAVAILABLE
          </span>
        );
      case 'UNVERIFIED':
      default:
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-slate-700/40 text-slate-300 border border-slate-600/40 flex items-center gap-1">
            VERIFICATION REQUIRED
          </span>
        );
    }
  };

  const getDocumentCardClasses = (status) => {
    switch (status) {
      case 'ACTIVE':
        return 'bg-gradient-to-r from-amber-500/10 via-slate-900 to-emerald-500/10 border-slate-700/80';
      case 'INACTIVE':
        return 'bg-gradient-to-r from-amber-500/15 via-slate-900 to-amber-900/20 border-amber-500/40';
      case 'SUSPENDED':
        return 'bg-gradient-to-r from-rose-500/15 via-slate-900 to-rose-900/20 border-rose-500/40';
      case 'UNAVAILABLE':
        return 'bg-gradient-to-r from-yellow-500/15 via-slate-900 to-yellow-900/20 border-yellow-500/40';
      default:
        return 'bg-slate-900 border-slate-800';
    }
  };

  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mr-2" />
        <span>Loading Worker Portal...</span>
      </div>
    );
  }

  const voiceScripts = {
    en: `Welcome ${profile?.full_name || 'Worker'}. Your digital identity is verified on the PassKhadam blockchain platform. Your trade is ${profile?.worker_category || 'Mason'}. You can download your tamper-proof QR code to share your verified credentials with employers and state welfare officers. Your raw Aadhaar number is never exposed.`,
    hi: `पासकदम में आपका स्वागत है ${profile?.full_name || 'श्रमिक जी'}। आपकी पहचान ब्लॉकचेन पर सत्यापित है। आपका कार्य ${profile?.worker_category || 'कारीगर'} है। आप अपना सुरक्षित क्यूआर कोड डाउनलोड करके नियोक्ताओं या सरकारी अधिकारियों को दिखा सकते हैं। आपका असली आधार नंबर हमेशा सुरक्षित और गोपनीय रहता है।`,
    kn: `ಪಾಸ್‌ಕದಮ್‌ಗೆ ಸುಸ್ವಾಗತ ${profile?.full_name || 'ಕಾರ್ಮಿಕರೇ'}. ನಿಮ್ಮ ಡಿಜಿಟಲ್ ಗುರುತನ್ನು ಬ್ಲಾಕ್‌ಚೈನ್‌ನಲ್ಲಿ ಪರಿಶೀಲಿಸಲಾಗಿದೆ. ನಿಮ್ಮ QR ಕೋಡ್ ಅನ್ನು ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ ಮಾಲೀಕರಿಗೆ ತೋರಿಸಬಹುದು. ನಿಮ್ಮ ಮೂಲ ಆಧಾರ್ ಸಂಖ್ಯೆ ರಕ್ಷಿತವಾಗಿದೆ.`,
    bn: `পাসখদমে স্বাগতম ${profile?.full_name || 'কর্মী'}। আপনার পরিচয় ব্লকচেইনে সুরক্ষিত ও যাচাইকৃত। আপনার মূল আধার নম্বর গোপন রেখে এই QR কোডটি ব্যবহার করুন।`,
    mr: `पासकदम मध्ये स्वागत आहे ${profile?.full_name || 'कामगार बंधू'}। तुमची डिजिटल ओळख ब्लॉकचेनवर सुरक्षित आहे. मूळ आधार नंबर न दाखवता हा QR कोड दाखवून तुम्ही पडताळणी करू शकता.`,
    te: `పాస్‌కదమ్‌కి స్వాగతం ${profile?.full_name || 'కార్మికులు'}। మీ డిజిటల్ గుర్తింపు బ్లాక్‌చెయిన్‌లో ధృవీకరించబడింది. మీ అసలు ఆధార్ నంబర్‌ను దాచిపెట్టి ఈ QR కోడ్‌ను చూపించవచ్చు.`
  };
  const voiceText = voiceScripts[currentLang] || voiceScripts.en;

  return (
    <div className="space-y-6">
      {/* Welcome & Verification Status Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-blue-600/15 border border-blue-500/30 text-blue-400 flex items-center justify-center text-2xl font-bold">
              👷
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">{profile?.full_name}</h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                  {profile?.worker_category} ({profile?.employment_level || "Skilled"})
                </span>
                <VoiceNarrator textToRead={voiceText} currentLang={currentLang} />
              </div>
              <p className="text-xs text-slate-400 flex flex-wrap items-center gap-2 mt-1">
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-500" />
                  Origin: <strong>{profile?.origin_state}</strong>
                </span>
                <span>•</span>
                <span className="flex items-center gap-1.5">
                  <span>Current State: <strong className="text-blue-300">{profile?.current_state}</strong></span>
                  <button
                    type="button"
                    onClick={handleOpenLocationModal}
                    className="px-2 py-0.5 rounded-md bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 border border-blue-500/30 text-[10px] font-semibold transition flex items-center gap-1 shadow-sm"
                    title="Change your current work location state (e.g. Goa, Maharashtra)"
                  >
                    <Navigation className="w-2.5 h-2.5 text-blue-400" />
                    <span>Change Location</span>
                  </button>
                </span>
                <span>•</span>
                <span className="text-emerald-400 font-mono">BOCW Registered ✓</span>
              </p>
            </div>
          </div>

          {/* Verification Chips */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-medium flex items-center gap-1">
              ✓ Email Verified
            </span>
            <span className="px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-medium flex items-center gap-1">
              ✓ Phone OTP Verified
            </span>
            {profile?.is_credential_anchored ? (
              <span className={`px-2.5 py-1 rounded-lg border font-bold flex items-center gap-1 ${
                profile?.aadhaar_status === 'ACTIVE' ? 'bg-blue-500/15 border-blue-500/30 text-blue-300' :
                profile?.aadhaar_status === 'INACTIVE' ? 'bg-amber-500/15 border-amber-500/30 text-amber-300' :
                profile?.aadhaar_status === 'SUSPENDED' ? 'bg-rose-500/15 border-rose-500/30 text-rose-300' :
                profile?.aadhaar_status === 'UNAVAILABLE' ? 'bg-yellow-500/15 border-yellow-500/30 text-yellow-300' :
                'bg-slate-700/30 border-slate-600/30 text-slate-300'
              }`}>
                ✓ Identity Anchored (DID) • {profile?.aadhaar_status || 'ACTIVE'}
              </span>
            ) : (
              <button
                onClick={() => setShowAadhaarModal(true)}
                className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold transition-all shadow-md shadow-rose-600/20 flex items-center gap-1.5"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Verify Government Identity</span>
              </button>
            )}
          </div>
        </div>

        {/* Masked Aadhaar / DID Alert */}
        {profile?.is_credential_anchored && (
          <div className="mt-4 pt-4 border-t border-slate-800 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <span className="text-slate-400 block text-[11px]">Decentralized Identifier (DID):</span>
              <span className="font-mono text-blue-400 font-semibold truncate block mt-0.5">
                {profile?.did}
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <span className="text-slate-400 block text-[11px]">Government Identity:</span>
              <span className={`font-mono font-semibold block mt-0.5 ${
                profile?.aadhaar_status === 'ACTIVE' ? 'text-emerald-400' :
                profile?.aadhaar_status === 'INACTIVE' ? 'text-amber-400' :
                profile?.aadhaar_status === 'SUSPENDED' ? 'text-rose-400' :
                profile?.aadhaar_status === 'UNAVAILABLE' ? 'text-yellow-400' : 'text-slate-400'
              }`}>
                {profile?.masked_aadhaar} ({profile?.aadhaar_status || 'Verified'})
              </span>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <span className="text-slate-400 block text-[11px]">IPFS Credential CID:</span>
              <span className="font-mono text-cyan-400 font-semibold truncate block mt-0.5">
                {profile?.ipfs_cid}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* VERIFIED GOVERNMENT DOCUMENT VISUAL (P1 Missing Requirement) */}
      {profile?.is_credential_anchored && (
        <div className={`border rounded-2xl p-6 shadow-2xl relative overflow-hidden ${getDocumentCardClasses(profile?.aadhaar_status)}`}>
          <div className="flex flex-col sm:flex-row justify-between items-start gap-3 border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-base">
                🇮🇳
              </div>
              <div>
                <h4 className="text-sm font-bold text-white tracking-wide uppercase">
                  Unique Identification Authority of India (Simulated)
                </h4>
                <p className="text-[11px] text-slate-400">Verified Government Identity Document Representation</p>
              </div>
            </div>
            {renderAadhaarStatusBadge(profile?.aadhaar_status)}
          </div>

          {/* Contextual Warning Alert for non-ACTIVE statuses */}
          {profile?.aadhaar_status === 'INACTIVE' && (
            <div className="mt-3 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
              <span>Record marked <strong>INACTIVE</strong> in Demographic Registry. Presentation operations are temporarily restricted.</span>
            </div>
          )}
          {profile?.aadhaar_status === 'SUSPENDED' && (
            <div className="mt-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>Record <strong>SUSPENDED</strong> by authority governance. Identity presentation has been revoked.</span>
            </div>
          )}
          {profile?.aadhaar_status === 'UNAVAILABLE' && (
            <div className="mt-3 p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-300 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-yellow-400" />
              <span>Mock Aadhaar registry unreachable. Live status check failed. Presentation restricted until revalidation succeeds.</span>
            </div>
          )}

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mt-4 text-xs">
            <div>
              <span className="text-slate-400 text-[11px] block">Name of Cardholder:</span>
              <span className="text-white font-bold text-sm block mt-0.5">{profile.full_name}</span>
            </div>
            <div>
              <span className="text-slate-400 text-[11px] block">DOB / Gender:</span>
              <span className="text-slate-200 font-medium block mt-0.5">{profile.dob} • {profile.gender}</span>
            </div>
            <div>
              <span className="text-slate-400 text-[11px] block">Aadhaar Number (Masked):</span>
              <span className="text-emerald-400 font-mono font-bold text-sm block mt-0.5">{profile.masked_aadhaar}</span>
            </div>
            <div>
              <span className="text-slate-400 text-[11px] block">BOCW Reg Number:</span>
              <span className="text-cyan-400 font-mono font-medium block mt-0.5">{profile.bocw_number}</span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-col sm:flex-row justify-between items-center text-[11px] text-slate-500 gap-2">
            <span>Simulated verification visual issued via Mock Aadhaar Gateway. Raw 12-digit Aadhaar number is never stored on blockchain.</span>
            <span className="font-mono text-slate-400">DID: {profile.did?.slice(0, 22)}...</span>
          </div>
        </div>
      )}

      {successMsg && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs font-medium">
          {successMsg}
        </div>
      )}

      {/* Main Grid: Credential Wallet & QR Presentation Card */}
      <div className="grid grid-cols-1 xl:grid-cols-3 lg:grid-cols-1 gap-6">

        {/* Left 2 Cols: Credential Wallet & Employment History */}
        <div className="xl:col-span-2 space-y-6">
          
          {/* Credential Wallet */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-blue-400" />
                <h3 className="font-bold text-white text-base">My Credential Wallet</h3>
              </div>
              <span className="text-xs text-slate-400">W3C Verifiable Credentials</span>
            </div>

            {profile?.is_credential_anchored ? (
              <div className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {wallet?.credentials && wallet.credentials.length > 0 ? (
                    wallet.credentials.map((cred, i) => (
                      <div
                        key={i}
                        className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-slate-700 transition-all space-y-2.5"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center text-sm font-bold">
                              {cred.issuer_role === 'GOVERNMENT' ? '🏛️' : (cred.issuer_role === 'EMPLOYER' ? '🏢' : '🆔')}
                            </div>
                            <div>
                              <h4 className="text-sm font-semibold text-white">{cred.title}</h4>
                              <div className="flex items-center gap-1.5 mt-0.5">
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">
                                  {cred.type}
                                </span>
                                {cred.issuer_role && (
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                                    cred.issuer_role === 'GOVERNMENT'
                                      ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                                      : cred.issuer_role === 'EMPLOYER'
                                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                      : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                                  }`}>
                                    {cred.issuer_role}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            cred.status === 'VALID'
                              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                              : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                          }`}>
                            {cred.status}
                          </span>
                        </div>

                        {cred.skills && cred.skills.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {cred.skills.map((s, idx) => (
                              <span key={idx} className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-cyan-300 border border-slate-700">
                                {s}
                              </span>
                            ))}
                          </div>
                        )}

                        <div className="text-[11px] text-slate-400 pt-2 border-t border-slate-900 flex items-center justify-between">
                          <span className="truncate max-w-[180px]">Issuer: {cred.issuer}</span>
                          <span className="text-blue-400 font-mono text-[10px]">Verified SSI ✓</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="col-span-2 text-center py-6 text-slate-400">
                      <p className="text-xs">No extra credentials issued yet. Government and employers can issue verified credentials to your wallet.</p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-slate-400 space-y-2">
                <Shield className="w-10 h-10 mx-auto text-slate-600" />
                <p className="text-sm font-medium">No verified credentials yet.</p>
                <p className="text-xs text-slate-500">Verify your government identity to activate your wallet.</p>
              </div>
            )}
          </div>

          {/* Portable Employment History */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-emerald-400" />
                <h3 className="font-bold text-white text-base">Portable Employment History</h3>
              </div>
              <span className="text-xs text-slate-400">Follows you across employers & states</span>
            </div>

            {wallet?.employments && wallet.employments.length > 0 ? (
              <div className="space-y-3">
                {wallet.employments.map((emp) => (
                  <div
                    key={emp.id}
                    className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-sm">{emp.employer_name}</span>
                        <span className="px-2 py-0.5 rounded bg-blue-500/15 text-blue-300 font-medium">
                          {emp.category}
                        </span>
                        {emp.level && (
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">
                            {emp.level}
                          </span>
                        )}
                      </div>
                      <p className="text-slate-400">
                        Role: {emp.job_role} • Location: {emp.location} • Type: {emp.nature_of_employment || "Contract"}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold ${
                        emp.status === 'ACTIVE'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : emp.status === 'DISMISSED'
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                          : 'bg-slate-800 text-slate-300'
                      }`}>
                        {emp.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-slate-500 text-xs">
                No active employment records logged on-chain yet.
              </div>
            )}
          </div>

        </div>

        {/* Right Col: Portable QR Identity Presentation Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <QrCode className="w-5 h-5 text-blue-400" />
                <h3 className="font-bold text-white text-base">Share Identity</h3>
              </div>
              <button
                onClick={handleRefreshQr}
                className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                title="Generate Fresh QR Presentation"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Refresh</span>
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Presents a cryptographically signed verifiable presentation without exposing raw Aadhaar or PII.
            </p>

            {profile?.is_credential_anchored ? (
              profile?.aadhaar_status === 'ACTIVE' ? (
                qrData ? (
                  <div className="space-y-4">
                    {/* QR Display Card */}
                    <div className="bg-white rounded-2xl p-4 shadow-xl flex flex-col items-center justify-center space-y-2">
                      <img
                        src={qrData.qr_base64_data_uri}
                        alt="Worker Identity QR"
                        className="w-48 h-48 object-contain rounded-lg"
                      />
                      <div className="text-center">
                        <p className="text-xs font-bold text-slate-900">{profile.full_name}</p>
                        <p className="text-[10px] font-mono text-slate-500 truncate max-w-[200px]">
                          {profile.did}
                        </p>
                      </div>
                    </div>

                    {/* Expiration Countdown Bar */}
                    <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between text-xs">
                      <span className="text-slate-400">Presentation Valid For:</span>
                      <span className={`font-mono font-bold text-sm ${timerSeconds < 60 ? 'text-rose-400 animate-pulse' : 'text-blue-400'}`}>
                        {formatTimer(timerSeconds)}
                      </span>
                    </div>

                    {/* Download Button */}
                    <button
                      type="button"
                      onClick={handleDownloadQr}
                      className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-semibold text-xs transition-all shadow-md shadow-blue-600/20 flex items-center justify-center gap-2 text-center"
                    >
                      <Download className="w-4 h-4" />
                      <span>Download QR Image Card (PNG)</span>
                    </button>
                    <p className="text-[11px] text-slate-500 text-center">
                      Share this PNG file with employers or government officers for web verification.
                    </p>

                    {/* Single-Use QR Advisory */}
                    <div className="p-2.5 rounded-xl bg-slate-950/90 border border-blue-500/20 text-[11px] text-slate-300 space-y-1">
                      <div className="font-semibold text-blue-300 flex items-center gap-1.5">
                        <Shield className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                        <span>Single-Use Verifiable Presentation</span>
                      </div>
                      <p className="text-slate-400 leading-relaxed text-[10.5px]">
                        Each generated QR code is an ephemeral, single-use token valid for 5 minutes. If an employer or officer has already scanned this presentation, tap <strong>"Refresh"</strong> above to generate a fresh QR presentation before re-scanning.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-10 text-slate-400 space-y-3">
                    <RefreshCw className="w-8 h-8 mx-auto animate-spin text-blue-400" />
                    <p className="text-xs">Generating verified presentation card...</p>
                    <button
                      onClick={handleRefreshQr}
                      className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
                    >
                      Generate QR
                    </button>
                  </div>
                )
              ) : (
                /* Gated / Locked State for non-ACTIVE statuses */
                <div className="space-y-4">
                  {profile?.aadhaar_status === 'INACTIVE' && (
                    <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs space-y-2">
                      <div className="flex items-center gap-2 font-bold text-sm text-amber-400">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span>QR Presentation Locked: Inactive Record</span>
                      </div>
                      <p>
                        Your citizen Aadhaar record in the demographic registry is currently marked <strong className="underline">INACTIVE</strong>.
                        Identity presentation has been temporarily locked by platform security invariants.
                      </p>
                    </div>
                  )}

                  {profile?.aadhaar_status === 'SUSPENDED' && (
                    <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs space-y-2">
                      <div className="flex items-center gap-2 font-bold text-sm text-rose-400">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span>QR Presentation Revoked: Suspended Record</span>
                      </div>
                      <p>
                        Your citizen Aadhaar record has been <strong className="underline">SUSPENDED</strong> by UIDAI governance.
                        Credential presentation and QR issuance are strictly forbidden until re-activation.
                      </p>
                    </div>
                  )}

                  {profile?.aadhaar_status === 'UNAVAILABLE' && (
                    <div className="p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-300 text-xs space-y-2">
                      <div className="flex items-center gap-2 font-bold text-sm text-yellow-400">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span>Status Check Unavailable</span>
                      </div>
                      <p>
                        Mock Aadhaar registry is unreachable or citizen record link could not be confirmed.
                        Live check failed; QR generation is held for conservative safety.
                      </p>
                      <p className="text-[11px] text-yellow-400/80 font-mono">
                        Last confirmed: {profile?.updated_at ? new Date(profile.updated_at).toLocaleString() : 'Session load'}
                      </p>
                    </div>
                  )}

                  {(!profile?.aadhaar_status || profile?.aadhaar_status === 'UNVERIFIED') && (
                    <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700 text-slate-300 text-xs space-y-2">
                      <div className="flex items-center gap-2 font-bold text-sm text-slate-200">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span>Verification Required</span>
                      </div>
                      <p>Citizen identity must be verified before QR presentations can be issued.</p>
                    </div>
                  )}

                  {/* Disabled QR Mock Card */}
                  <div className="bg-slate-950/60 rounded-2xl p-6 border border-slate-800 flex flex-col items-center justify-center space-y-2 text-center text-slate-500 opacity-60">
                    <QrCode className="w-20 h-20 text-slate-700" />
                    <span className="text-xs font-mono font-medium">QR Presentation Locked</span>
                    <span className="text-[10px] text-slate-600">Aadhaar Status: {profile?.aadhaar_status || 'NOT ACTIVE'}</span>
                  </div>

                  {/* Disabled Download Button */}
                  <button
                    type="button"
                    disabled
                    className="w-full py-2.5 px-4 bg-slate-800/80 border border-slate-700/60 text-slate-500 rounded-xl font-semibold text-xs cursor-not-allowed flex items-center justify-center gap-2 text-center"
                    title={`Download locked: Aadhaar status is ${profile?.aadhaar_status || 'NOT ACTIVE'}`}
                  >
                    <Download className="w-4 h-4 text-slate-600" />
                    <span>Download Locked (Status: {profile?.aadhaar_status || 'NOT ACTIVE'})</span>
                  </button>
                  <p className="text-[11px] text-slate-500 text-center">
                    Identity must be ACTIVE in the demographic registry to present credentials.
                  </p>
                </div>
              )
            ) : (
              <div className="text-center py-10 text-slate-500 space-y-2">
                <QrCode className="w-12 h-12 mx-auto text-slate-700" />
                <p className="text-xs">QR Presentation unavailable until government identity is verified.</p>
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Aadhaar Verification Modal */}
      {showAadhaarModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-blue-400" />
                <h3 className="font-bold text-white text-base">Verify Government Identity</h3>
              </div>
              <button
                onClick={() => setShowAadhaarModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Connects to the Mock Aadhaar Authority. Full Aadhaar number is verified demographic-only and <strong>never stored on the blockchain</strong>.
            </p>

            {errorMsg && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleVerifyAadhaar} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Aadhaar Number (12 Digits)
                </label>
                <input
                  type="text"
                  value={aadhaarInput}
                  onChange={(e) => setAadhaarInput(e.target.value)}
                  placeholder="e.g. 123456784821"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white font-mono focus:border-blue-500 outline-none"
                  required
                />
                <span className="text-[11px] text-slate-500 mt-1 block">
                  Demo Active Numbers: <code>123456784821</code>, <code>987654321012</code>
                </span>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Full Name (as registered with Aadhaar)
                </label>
                <input
                  type="text"
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  placeholder="Mohammed Uzair"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:border-blue-500 outline-none"
                  required
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAadhaarModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={verifyingAadhaar}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-semibold shadow-md shadow-blue-600/30 flex items-center gap-2"
                >
                  {verifyingAadhaar ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Issuing DID & Pinned Credential...</span>
                    </>
                  ) : (
                    <span>Submit & Issue Decentralized Identity</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Update Migration Location Modal */}
      {showLocationModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Navigation className="w-5 h-5 text-blue-400" />
                <h3 className="font-bold text-white text-base">Update Migration Location</h3>
              </div>
              <button
                onClick={() => setShowLocationModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Declare your current migration destination state (e.g. Goa, Maharashtra). Government officers and employers in your destination state use this location to verify your credentials and disburse regional welfare grants.
            </p>

            <form onSubmit={handleUpdateLocation} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Home / Origin State (Anchored by Identity)
                </label>
                <input
                  type="text"
                  value={profile?.origin_state || 'Not Set'}
                  disabled
                  className="w-full px-3 py-2 bg-slate-950/60 border border-slate-800 rounded-xl text-slate-400 font-medium cursor-not-allowed"
                />
                <span className="text-[10.5px] text-slate-500 mt-1 block">
                  Home state is tied to citizen Aadhaar records and cannot be altered.
                </span>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Current Destination / Work State <span className="text-rose-400">*</span>
                </label>
                <select
                  value={targetCurrentState}
                  onChange={(e) => setTargetCurrentState(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white font-medium focus:border-blue-500 outline-none"
                  required
                >
                  {INDIAN_STATES.map((st) => (
                    <option key={st} value={st}>{st}</option>
                  ))}
                </select>
                <span className="text-[10.5px] text-blue-400/80 mt-1 block">
                  Select the state where you are currently residing or seeking employment.
                </span>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Current Address / Work Site (Optional)
                </label>
                <input
                  type="text"
                  value={targetAddress}
                  onChange={(e) => setTargetAddress(e.target.value)}
                  placeholder="e.g. Panaji Construction Cluster, Goa"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white focus:border-blue-500 outline-none"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowLocationModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updatingLocation}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-semibold shadow-md shadow-blue-600/30 flex items-center gap-2"
                >
                  {updatingLocation ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Updating Location...</span>
                    </>
                  ) : (
                    <span>Save Location</span>
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
