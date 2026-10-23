import React, { useState, useEffect } from 'react';
import { 
  User, CheckCircle, AlertTriangle, QrCode, Shield, Briefcase, 
  Download, RefreshCw, Key, Award, FileText, ChevronRight, MapPin, Sparkles, Volume2, Navigation,
  CheckCircle2, ShieldCheck, Clock
} from 'lucide-react';
import VoiceNarrator from '../common/VoiceNarrator';
import { getTranslation } from '../../i18n/translations';
import { useAuth } from '../../context/AuthContext';
import { apiFetch, formatAadhaarInput, cleanAadhaarDigits } from '../../utils/api';

const INDIAN_STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
  'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand',
  'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
  'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
  'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
  'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Delhi', 'Jammu & Kashmir', 'Ladakh', 'Puducherry'
];

const STANDARD_TRADES = [
  'Mason',
  'Electrician',
  'Plumber',
  'Carpenter',
  'Painter',
  'Welder',
  'Heavy Machinery Operator',
  'Driver',
  'Steel Fixer',
  'Tile Setter',
  'General Construction'
];

const SUGGESTED_SKILLS_MAP = {
  Mason: ['Bricklaying', 'Concreting', 'Plastering', 'Formwork', 'Scaffolding', 'Mortar Mixing'],
  Electrician: ['Conduit Wiring', 'Switchgear', 'Panel Installation', 'Solar PV', 'Earthing', 'Fault Finding'],
  Plumber: ['PVC Piping', 'GI Piping', 'Drainage Systems', 'Sanitary Fixtures', 'Water Pumps', 'Leak Detection'],
  Carpenter: ['Formwork', 'Framing', 'Door & Window Fitting', 'Scaffolding', 'Roof Trussing'],
  Painter: ['Surface Preparation', 'Primer Application', 'Emulsion Painting', 'Enamel Coating', 'Spray Painting'],
  Welder: ['Arc Welding', 'MIG Welding', 'TIG Welding', 'Gas Cutting', 'Structural Steel Fabrication'],
  'Heavy Machinery Operator': ['Excavator Operation', 'Backhoe Loader', 'Dump Truck', 'Compactor', 'Safety Rigging'],
  Driver: ['Heavy Commercial Vehicle', 'Light Commercial Vehicle', 'Route Logistics', 'Vehicle Maintenance'],
  'Steel Fixer': ['Rebar Cutting', 'Rebar Bending', 'Mesh Tying', 'Column Caging'],
  'Tile Setter': ['Ceramic Tiling', 'Marble Flooring', 'Granite Fitting', 'Tile Grouting'],
  'General Construction': ['Site Clearance', 'Material Handling', 'Concrete Pouring', 'Trench Digging']
};

const formatTimestamp = (ts) => {
  if (!ts) return '';
  const date = new Date(ts > 1e11 ? ts : ts * 1000);
  return date.toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' });
};

const renderEmploymentStatusBadge = (status) => {
  const norm = (status || '').toUpperCase();
  switch (norm) {
    case 'ACTIVE':
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center gap-1.5 shadow-sm shadow-emerald-500/10">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          ACTIVE
        </span>
      );
    case 'COMPLETED':
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/40 flex items-center gap-1 shadow-sm shadow-blue-500/10">
          ✓ COMPLETED
        </span>
      );
    case 'DISCONTINUED':
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 flex items-center gap-1 shadow-sm shadow-amber-500/10">
          ⚠️ DISCONTINUED
        </span>
      );
    case 'TERMINATED':
    case 'DISMISSED':
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40 flex items-center gap-1 shadow-sm shadow-rose-500/10">
          ✕ {norm}
        </span>
      );
    case 'RESIGNED':
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40 flex items-center gap-1">
          RESIGNED
        </span>
      );
    case 'SUSPENDED':
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-yellow-500/20 text-yellow-300 border border-yellow-500/40 flex items-center gap-1">
          SUSPENDED
        </span>
      );
    default:
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
          {status || 'UNKNOWN'}
        </span>
      );
  }
};

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

  const [employmentHistory, setEmploymentHistory] = useState(null);
  const [historyFilter, setHistoryFilter] = useState('ALL'); // 'ALL' | 'ACTIVE' | 'HISTORICAL'

  // Skills modal state
  const [showSkillsModal, setShowSkillsModal] = useState(false);
  const [modalTrade, setModalTrade] = useState('Mason');
  const [customTradeInput, setCustomTradeInput] = useState('');
  const [modalSkills, setModalSkills] = useState([]);
  const [newSkillInput, setNewSkillInput] = useState('');
  const [savingSkills, setSavingSkills] = useState(false);

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

          try {
            const histRes = await apiFetch('/api/v1/worker/employment-history/me');
            if (histRes.ok) setEmploymentHistory(await histRes.json());
          } catch (err) {
            console.warn('Employment history fetch error', err);
          }

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
          setEmploymentHistory(null);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenSkillsModal = () => {
    const currentCategory = profile?.worker_category || 'Mason';
    if (STANDARD_TRADES.includes(currentCategory)) {
      setModalTrade(currentCategory);
      setCustomTradeInput('');
    } else {
      setModalTrade('Other');
      setCustomTradeInput(currentCategory);
    }
    setModalSkills(Array.isArray(profile?.skills) ? [...profile.skills] : []);
    setNewSkillInput('');
    setErrorMsg('');
    setShowSkillsModal(true);
  };

  const handleAddSkill = () => {
    const trimmed = newSkillInput.trim();
    if (trimmed && !modalSkills.includes(trimmed)) {
      setModalSkills([...modalSkills, trimmed]);
      setNewSkillInput('');
    }
  };

  const handleRemoveSkill = (index) => {
    setModalSkills(modalSkills.filter((_, idx) => idx !== index));
  };

  const handleAddSuggestedSkill = (skill) => {
    if (skill && !modalSkills.includes(skill)) {
      setModalSkills([...modalSkills, skill]);
    }
  };

  const handleSaveSkillsAndTrade = async (e) => {
    e.preventDefault();
    setSavingSkills(true);
    setErrorMsg('');
    setSuccessMsg('');
    try {
      const selectedCategory = modalTrade === 'Other' ? (customTradeInput.trim() || 'Other') : modalTrade;
      const res = await apiFetch('/api/v1/worker/skills/me', {
        method: 'PUT',
        body: {
          worker_category: selectedCategory,
          skills: modalSkills
        }
      });
      if (!res.ok) {
        // Fallback to /profile/me if /skills/me fails
        const fallbackRes = await apiFetch('/api/v1/worker/profile/me', {
          method: 'PUT',
          body: {
            worker_category: selectedCategory,
            skills: modalSkills
          }
        });
        if (!fallbackRes.ok) {
          const errData = await fallbackRes.json();
          throw new Error(errData.detail || 'Failed to update skills and trade profile');
        }
      }
      setSuccessMsg('Trade and skills profile successfully updated!');
      setShowSkillsModal(false);
      await fetchWorkerData();
    } catch (err) {
      setErrorMsg(err.message || 'Error updating skills');
    } finally {
      setSavingSkills(false);
    }
  };

  const effectiveEmployments = employmentHistory?.employments || wallet?.employments || [];
  const activeCount = employmentHistory?.active_count !== undefined 
    ? employmentHistory.active_count 
    : effectiveEmployments.filter(e => (e.status || '').toUpperCase() === 'ACTIVE').length;
  const historicalCount = employmentHistory?.historical_count !== undefined 
    ? employmentHistory.historical_count 
    : effectiveEmployments.filter(e => (e.status || '').toUpperCase() !== 'ACTIVE').length;

  const filteredEmployments = effectiveEmployments.filter(emp => {
    const isActive = (emp.status || '').toUpperCase() === 'ACTIVE';
    if (historyFilter === 'ACTIVE') return isActive;
    if (historyFilter === 'HISTORICAL') return !isActive;
    return true;
  });

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
      const cleanAadhaar = aadhaarInput.replace(/\s+/g, '');
      if (cleanAadhaar.length !== 12 || !/^\d{12}$/.test(cleanAadhaar)) {
        throw new Error("Aadhaar number must contain exactly 12 numeric digits (e.g. 1234 5678 4821).");
      }
      const res = await apiFetch('/api/v1/worker/verify-aadhaar/me', {
        method: "POST",
        body: { aadhaar_number: cleanAadhaar, full_name: nameInput.trim() }
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

      {/* Feature 16: Actionable Guidance Notice for Unanchored Worker Identity */}
      {!profile?.is_credential_anchored && (
        <div className="bg-gradient-to-r from-blue-950/70 via-slate-900 to-indigo-950/70 border border-blue-500/30 rounded-2xl p-5 shadow-xl space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-blue-500/20 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/40 text-blue-400 flex items-center justify-center">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-white text-sm">Action Required: Verify Government Identity to Activate Wallet</h3>
                <p className="text-[11px] text-blue-200/80">Step 2 of 2 in your decentralized digital identity onboarding</p>
              </div>
            </div>
            <button
              onClick={() => setShowAadhaarModal(true)}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition-all shadow-md shadow-blue-600/30 flex items-center gap-1.5 shrink-0"
            >
              <Shield className="w-4 h-4" />
              <span>Verify Government Identity (Aadhaar) Now</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-emerald-400 flex items-center gap-1">
                <CheckCircle className="w-3.5 h-3.5" /> Step 1: Contact Verified
              </span>
              <p className="text-[11px] text-slate-300">
                Email and phone SMS dual verification confirmed on your account.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-blue-500/30 space-y-1">
              <span className="text-[11px] font-semibold text-blue-300 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" /> Step 2: Anchor Decentralized DID
              </span>
              <p className="text-[11px] text-slate-300">
                Verify 12-digit Aadhaar to issue your Ed25519 cryptographic DID and portable W3C wallet.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-1">
              <span className="text-[11px] font-semibold text-cyan-300 flex items-center gap-1">
                <Key className="w-3.5 h-3.5" /> Zero PII Leak Guarantee
              </span>
              <p className="text-[11px] text-slate-300">
                Raw Aadhaar numbers are never stored on blockchain. Only one-way privacy hashes are anchored.
              </p>
            </div>
          </div>
        </div>
      )}

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
          
          {/* Skills & Trade Profile Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-amber-400" />
                <div>
                  <h3 className="font-bold text-white text-base">My Trade & Skills Profile</h3>
                  <p className="text-[11px] text-slate-400">Verified trade category and self-declared portable trade skills</p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleOpenSkillsModal}
                className="px-3 py-1.5 rounded-xl bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 border border-blue-500/30 text-xs font-semibold transition flex items-center gap-1.5 shadow-sm"
              >
                <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                <span>Manage Skills & Trade</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
                <span className="text-[11px] text-slate-400 block font-medium">Primary Trade / Profession</span>
                <span className="text-sm font-bold text-white block">
                  {profile?.worker_category || 'Mason'}
                </span>
                <span className="text-[10px] text-emerald-400 font-mono block">
                  Level: {profile?.employment_level || 'Skilled'}
                </span>
              </div>

              <div className="md:col-span-2 p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-slate-400 font-medium">Portable Skill Capabilities:</span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {(profile?.skills || []).length} registered skills
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(profile?.skills && profile.skills.length > 0) ? (
                    profile.skills.map((skill, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-900 border border-cyan-500/30 text-cyan-300 flex items-center gap-1"
                      >
                        <span>{skill}</span>
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500 italic">
                      No specific skills listed. Tap "Manage Skills & Trade" to declare your specialized skills.
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

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

          {/* Portable Employment History Ledger */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-3 gap-2">
              <div className="flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-emerald-400" />
                <div>
                  <h3 className="font-bold text-white text-base">Portable Employment History</h3>
                  <p className="text-[11px] text-slate-400">
                    Follows you across employers & states • Immutable workforce provenance ledger
                  </p>
                </div>
              </div>
              
              {/* Tab filters with counts */}
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setHistoryFilter('ALL')}
                  className={`px-2.5 py-1 rounded-lg font-medium transition ${
                    historyFilter === 'ALL'
                      ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  All ({effectiveEmployments.length})
                </button>
                <button
                  type="button"
                  onClick={() => setHistoryFilter('ACTIVE')}
                  className={`px-2.5 py-1 rounded-lg font-medium transition ${
                    historyFilter === 'ACTIVE'
                      ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Active ({activeCount})
                </button>
                <button
                  type="button"
                  onClick={() => setHistoryFilter('HISTORICAL')}
                  className={`px-2.5 py-1 rounded-lg font-medium transition ${
                    historyFilter === 'HISTORICAL'
                      ? 'bg-amber-600/30 text-amber-300 border border-amber-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Past & Concluded ({historicalCount})
                </button>
              </div>
            </div>

            {/* Feature 16: Worker Employment Provenance Permanence Reassurance */}
            {effectiveEmployments.some(e => (e.status || '').toUpperCase() === 'DISCONTINUED') && (
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                <div>
                  <strong className="font-semibold text-amber-200">Worker Permanence Invariant:</strong>
                  <p className="text-[11px] text-slate-300 mt-0.5 leading-relaxed">
                    Discontinued or concluded stints remain permanently preserved in your portable employment ledger. Employers or administrative changes cannot delete your accrued experience and tenure history.
                  </p>
                </div>
              </div>
            )}

            {filteredEmployments.length > 0 ? (
              <div className="space-y-3">
                {filteredEmployments.map((emp) => {
                  const isDiscontinued = (emp.status || '').toUpperCase() === 'DISCONTINUED';
                  const isCompleted = (emp.status || '').toUpperCase() === 'COMPLETED';
                  return (
                    <div
                      key={emp.id}
                      className={`p-4 rounded-xl bg-slate-950/80 border transition-all space-y-2.5 ${
                        isDiscontinued
                          ? 'border-amber-500/30 hover:border-amber-500/50'
                          : isCompleted
                          ? 'border-blue-500/30 hover:border-blue-500/50'
                          : 'border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 text-xs">
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-bold text-white text-sm">{emp.employer_name}</span>
                            <span className="px-2 py-0.5 rounded bg-blue-500/15 text-blue-300 font-medium text-[11px]">
                              {emp.category}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium text-[11px]">
                              {emp.level || 'Skilled'}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-slate-800/80 text-slate-400 text-[11px]">
                              {emp.nature_of_employment || 'Contract'}
                            </span>
                          </div>
                          <p className="text-slate-300 text-xs">
                            Role: <strong className="text-white">{emp.job_role}</strong> • Location: {emp.location}
                          </p>
                          <p className="text-slate-400 text-[11px] flex items-center gap-1.5 font-mono">
                            <span>Period: {formatTimestamp(emp.start_date)} → {emp.end_date && emp.end_date > 0 ? formatTimestamp(emp.end_date) : (emp.status === 'ACTIVE' ? 'Present (Active)' : 'Concluded')}</span>
                          </p>
                        </div>

                        <div className="text-right sm:shrink-0">
                          {renderEmploymentStatusBadge(emp.status)}
                        </div>
                      </div>

                      {/* Contextual Invariant Banners */}
                      {isDiscontinued && (
                        <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                          <span>
                            <strong>Permanence Invariant:</strong> Category authorization discontinued by platform governance. Historical stint permanently recorded in worker provenance ledger.
                          </span>
                        </div>
                      )}
                      {isCompleted && (
                        <div className="p-2.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-[11px] text-blue-300 flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 shrink-0 text-blue-400" />
                          <span>
                            Employment tenure successfully completed and verified on-chain.
                          </span>
                        </div>
                      )}

                      <div className="text-[10px] text-slate-500 pt-1.5 border-t border-slate-900 flex flex-wrap items-center justify-between gap-1">
                        <span className="font-mono">Employer Ref: {emp.employer_address?.slice(0, 16)}...</span>
                        <span className="font-mono text-cyan-400">
                          {emp.tx_hash ? `Tx: ${emp.tx_hash.slice(0, 16)}...` : 'On-Chain Ledger Anchor ✓'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500 text-xs space-y-1">
                <Briefcase className="w-8 h-8 mx-auto text-slate-700 mb-2" />
                <p className="font-medium text-slate-400">
                  {historyFilter === 'ACTIVE'
                    ? 'No active employment stints currently running.'
                    : historyFilter === 'HISTORICAL'
                    ? 'No past or discontinued stints recorded yet.'
                    : 'No employment records logged on-chain yet.'}
                </p>
                <p className="text-[11px] text-slate-600">
                  When authorized employers hire or conclude stints, records appear here permanently.
                </p>
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
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-slate-300 font-semibold text-xs flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-blue-400" />
                    Aadhaar Number (12 Digits)
                  </label>
                  {aadhaarInput.replace(/\s/g, '').length === 12 ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                      <CheckCircle2 className="w-3 h-3" /> 12/12 Digits Valid
                    </span>
                  ) : (
                    <span className="text-[11px] font-mono text-slate-400">
                      {aadhaarInput.replace(/\s/g, '').length}/12 digits
                    </span>
                  )}
                </div>
                <div className="relative">
                  <input
                    type="text"
                    value={aadhaarInput}
                    onChange={(e) => setAadhaarInput(formatAadhaarInput(e.target.value))}
                    onKeyDown={(e) => {
                      if (e.key === 'Backspace') {
                        const { selectionStart, selectionEnd, value } = e.target;
                        if (selectionStart === selectionEnd && selectionStart > 0 && value[selectionStart - 1] === ' ') {
                          e.preventDefault();
                          const cut = selectionStart - 1;
                          const updated = value.slice(0, cut - 1) + value.slice(selectionStart);
                          const formatted = formatAadhaarInput(updated);
                          setAadhaarInput(formatted);
                          setTimeout(() => {
                            e.target.setSelectionRange(Math.max(0, cut - 1), Math.max(0, cut - 1));
                          }, 0);
                        }
                      }
                    }}
                    onPaste={(e) => {
                      e.preventDefault();
                      setAadhaarInput(formatAadhaarInput(e.clipboardData.getData('text')));
                    }}
                    maxLength={14}
                    placeholder="1234 5678 4821"
                    className={`w-full px-3 py-2 pr-9 bg-slate-950 border rounded-xl font-mono text-sm tracking-wider outline-none transition ${
                      aadhaarInput.replace(/\s/g, '').length === 12
                        ? 'border-emerald-500/60 text-emerald-300 focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400/40'
                        : aadhaarInput.replace(/\s/g, '').length > 0
                        ? 'border-blue-500/50 text-white focus:border-blue-400'
                        : 'border-slate-800 text-slate-200 focus:border-blue-500'
                    }`}
                    required
                  />
                  {aadhaarInput.replace(/\s/g, '').length === 12 && (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 absolute right-3 top-2.5 pointer-events-none" />
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500 pt-0.5">
                  <span>Demo Active Numbers:</span>
                  <button
                    type="button"
                    onClick={() => {
                      setAadhaarInput(formatAadhaarInput('123456784821'));
                      setNameInput('Mohammed Uzair');
                    }}
                    className="text-blue-400 hover:text-blue-300 hover:underline font-mono"
                  >
                    1234 5678 4821 (Uzair)
                  </button>
                  <span>•</span>
                  <button
                    type="button"
                    onClick={() => {
                      setAadhaarInput(formatAadhaarInput('987654321012'));
                      setNameInput('Ramesh Kumar Verma');
                    }}
                    className="text-blue-400 hover:text-blue-300 hover:underline font-mono"
                  >
                    9876 5432 1012 (Ramesh)
                  </button>
                </div>
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

      {/* Manage Skills & Trade Modal */}
      {showSkillsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-lg w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-blue-400" />
                <h3 className="font-bold text-white text-base">Manage Skills & Trade Profile</h3>
              </div>
              <button
                onClick={() => setShowSkillsModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Update your recognized trade profession and declare your specialized construction and technical skills. These skills will be anchored to your portable identity profile and visible to hiring employers.
            </p>

            {errorMsg && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleSaveSkillsAndTrade} className="space-y-4 text-xs">
              {/* Trade Selection */}
              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Primary Trade / Profession <span className="text-rose-400">*</span>
                </label>
                <select
                  value={modalTrade}
                  onChange={(e) => setModalTrade(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white font-medium focus:border-blue-500 outline-none"
                  required
                >
                  {STANDARD_TRADES.map((trade) => (
                    <option key={trade} value={trade}>{trade}</option>
                  ))}
                  <option value="Other">Other / Custom Trade...</option>
                </select>
              </div>

              {/* Custom Trade Input when Other selected */}
              {modalTrade === 'Other' && (
                <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-1">
                  <label className="block text-amber-300 font-semibold">
                    Specify Custom Trade or Specialization
                  </label>
                  <input
                    type="text"
                    value={customTradeInput}
                    onChange={(e) => setCustomTradeInput(e.target.value)}
                    placeholder="e.g. Scaffolder, Solar Technician, Rigger"
                    className="w-full px-3 py-2 bg-slate-950 border border-amber-500/40 rounded-xl text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-400"
                    required
                  />
                </div>
              )}

              {/* Current Skills Chips with Remove button */}
              <div>
                <label className="block text-slate-300 font-semibold mb-1.5">
                  Your Skills ({modalSkills.length})
                </label>
                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 min-h-[50px] flex flex-wrap gap-1.5">
                  {modalSkills.length > 0 ? (
                    modalSkills.map((sk, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-600/20 text-blue-300 border border-blue-500/30"
                      >
                        <span>{sk}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveSkill(idx)}
                          className="w-4 h-4 rounded-full hover:bg-rose-500/40 hover:text-white flex items-center justify-center text-[10px] transition ml-0.5"
                          title={`Remove ${sk}`}
                        >
                          ✕
                        </button>
                      </span>
                    ))
                  ) : (
                    <span className="text-slate-500 text-xs italic">No skills added yet. Type below or choose from suggestions.</span>
                  )}
                </div>
              </div>

              {/* Add Skill Field */}
              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Add a New Skill
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newSkillInput}
                    onChange={(e) => setNewSkillInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddSkill();
                      }
                    }}
                    placeholder="e.g. Arc Welding, Conduit Wiring, Tiling"
                    className="flex-1 px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white placeholder:text-slate-600 focus:border-blue-500 outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleAddSkill}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl font-medium"
                  >
                    Add
                  </button>
                </div>
              </div>

              {/* Suggested Skills based on selected trade */}
              {SUGGESTED_SKILLS_MAP[modalTrade] && (
                <div className="space-y-1.5">
                  <span className="text-[11px] text-slate-400 font-medium">Quick-Add Suggested Skills for {modalTrade}:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {SUGGESTED_SKILLS_MAP[modalTrade].map((s) => (
                      <button
                        key={s}
                        type="button"
                        disabled={modalSkills.includes(s)}
                        onClick={() => handleAddSuggestedSkill(s)}
                        className={`px-2 py-0.5 rounded-lg text-[11px] transition ${
                          modalSkills.includes(s)
                            ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed line-through'
                            : 'bg-blue-600/10 hover:bg-blue-600/25 text-blue-300 border border-blue-500/20'
                        }`}
                      >
                        + {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowSkillsModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingSkills}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-semibold shadow-md shadow-blue-600/30 flex items-center gap-2"
                >
                  {savingSkills ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving Profile...</span>
                    </>
                  ) : (
                    <span>Save Trade & Skills</span>
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
