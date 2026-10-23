import React, { useState, useEffect } from 'react';
import { X, Lock, Mail, Phone, User, CheckCircle2, AlertCircle, ArrowRight, Shield, Smartphone, Building2, KeyRound, RefreshCw, Landmark } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function AuthModal({ isOpen, onClose, onRoleSelect, initialTab = 'login', initialToken = '' }) {
  const { login, register, resetPassword, sendPhoneOtp, verifyPhoneOtp, sendEmailOtp, verifyEmailOtp, checkFirebaseEmailStatus, loading } = useAuth();
  const [tab, setTab] = useState(initialTab || 'login'); // 'login' | 'register' | 'activate' | 'activate_gov'
  
  // Login fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [resetSent, setResetSent] = useState(false);
  
  // Register fields
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPhone, setRegPhone] = useState('+91 98765 43210');
  const [regPassword, setRegPassword] = useState('');
  const [regRole, setRegRole] = useState('WORKER'); // WORKER or EMPLOYER only
  const [workerCategory, setWorkerCategory] = useState('Mason');
  const [customProfession, setCustomProfession] = useState('');
  const [workerOriginState, setWorkerOriginState] = useState('Karnataka');
  
  // Employer Org fields
  const [orgName, setOrgName] = useState('');
  const [orgRegNo, setOrgRegNo] = useState('');
  const [orgCategories, setOrgCategories] = useState('Mason, Electrician, Plumber');

  // Employer Activation fields
  const [actToken, setActToken] = useState(initialTab === 'activate' ? initialToken || '' : '');
  const [actPassword, setActPassword] = useState('');

  // Government Officer Activation fields
  const [govToken, setGovToken] = useState(initialTab === 'activate_gov' ? initialToken || '' : '');
  const [govPassword, setGovPassword] = useState('');
  const [govConfirmPassword, setGovConfirmPassword] = useState('');
  const [activatingGov, setActivatingGov] = useState(false);

  useEffect(() => {
    if (isOpen) {
      if (initialTab) setTab(initialTab);
      if (initialToken) {
        if (initialTab === 'activate_gov') {
          setGovToken(initialToken);
        } else if (initialTab === 'activate') {
          setActToken(initialToken);
        }
      }
    }
  }, [isOpen, initialTab, initialToken]);

  // Email OTP & Link state
  const [emailOtpSent, setEmailOtpSent] = useState(false);
  const [emailOtpCode, setEmailOtpCode] = useState('');
  const [emailVerified, setEmailVerified] = useState(false);
  const [emailNotification, setEmailNotification] = useState(null);
  const [emailDeliveryMode, setEmailDeliveryMode] = useState(null);
  const [emailDispatchedTo, setEmailDispatchedTo] = useState('');
  const [simulatedOtpHint, setSimulatedOtpHint] = useState(null);
  const [checkingEmailStatus, setCheckingEmailStatus] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);

  // Phone OTP state
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [otpVerified, setOtpVerified] = useState(false);
  const [smsNotification, setSmsNotification] = useState(null);

  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  if (!isOpen) return null;

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    const res = await login(email, password);
    if (res.success) {
      if (onRoleSelect) onRoleSelect(res.user.role);
      onClose();
    } else {
      setErrorMsg(res.error || 'Authentication failed');
    }
  };

  const handleForgotPassword = async () => {
    if (!email) {
      setErrorMsg('Please enter your email address to reset password');
      return;
    }
    setErrorMsg(null);
    const res = await resetPassword(email);
    if (res.success) {
      setResetSent(true);
      setSuccessMsg(res.message);
    } else {
      setErrorMsg(res.error || 'Failed to dispatch reset email');
    }
  };



  const handleSendEmailOtp = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);
    if (!regEmail || regEmail.trim() === '' || !regEmail.includes('@')) {
      setErrorMsg('Please enter a valid official email address first');
      return;
    }
    if (!regPassword || regPassword.length < 6) {
      setErrorMsg('Please enter a password (minimum 6 characters) to initialize your Firebase identity');
      return;
    }
    setSendingEmail(true);
    const res = await sendEmailOtp(regEmail, regPassword);
    setSendingEmail(false);
    if (res.success) {
      setEmailOtpSent(true);
      setEmailDeliveryMode(res.delivery_mode || 'simulated');
      setEmailDispatchedTo(regEmail);
      setEmailNotification(res.message);
      setSuccessMsg(res.message);
      if (res.delivery_mode === 'smtp') {
        setEmailOtpCode('');
        setSimulatedOtpHint(null);
      } else {
        setSimulatedOtpHint(res.otp_hint || '729415');
        if (res.otp_hint) {
          setEmailOtpCode(res.otp_hint);
        }
      }
    } else {
      setErrorMsg(res.error || 'Failed to dispatch email verification');
    }
  };

  const handleVerifyEmailOtp = async () => {
    setErrorMsg(null);
    if (!emailOtpCode || emailOtpCode.trim() === '') {
      setErrorMsg('Please enter the 6-digit email verification code');
      return;
    }
    const targetEmail = emailDispatchedTo || regEmail;
    if (emailDispatchedTo && regEmail && regEmail.trim().toLowerCase() !== emailDispatchedTo.trim().toLowerCase()) {
      setErrorMsg(`Verification code was sent to ${emailDispatchedTo}. Please click "Resend verification email & OTP" to update recipient.`);
      return;
    }
    const res = await verifyEmailOtp(targetEmail, emailOtpCode);
    if (res.success) {
      setEmailVerified(true);
      setSuccessMsg(res.message || 'Email verified successfully!');
    } else {
      setErrorMsg(res.error || 'Invalid email verification code');
    }
  };

  const handleCheckEmailLinkStatus = async () => {
    setErrorMsg(null);
    if (emailDispatchedTo && regEmail && regEmail.trim().toLowerCase() !== emailDispatchedTo.trim().toLowerCase()) {
      setErrorMsg(`Verification email was sent to ${emailDispatchedTo}. Please click "Resend verification email & OTP" to update recipient.`);
      return;
    }
    const targetEmail = emailDispatchedTo || regEmail;
    setCheckingEmailStatus(true);
    const res = await checkFirebaseEmailStatus(targetEmail, regPassword);
    setCheckingEmailStatus(false);
    if (res.verified || res.success) {
      setEmailVerified(true);
      setSuccessMsg(res.message || 'Email verified successfully via Google Firebase official verification link!');
    } else {
      setErrorMsg(res.error || 'Email link not activated yet. Please click the link sent to your inbox from noreply@passkhadam-live.firebaseapp.com, or verify using the 6-digit OTP code below.');
    }
  };

  const handleSendOtp = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);
    if (!regPhone || regPhone.trim() === '') {
      setErrorMsg('Please enter a phone number (e.g. +91 98765 43210 or your mobile number).');
      return;
    }
    const res = await sendPhoneOtp(regPhone, 'recaptcha-container');
    if (res.success) {
      setOtpSent(true);
      setSmsNotification(res.message || res.simulated_sms || 'Firebase SMS verification dispatched');
      setSuccessMsg(res.message || `OTP dispatched to ${regPhone}`);
      if (res.is_test_number) {
        setOtpCode('123456');
      } else if (res.otp_hint) {
        setOtpCode(res.otp_hint);
      }
    } else {
      setErrorMsg(res.error || 'Failed to send OTP via Firebase Gateway');
    }
  };

  const handleVerifyOtp = async () => {
    setErrorMsg(null);
    const res = await verifyPhoneOtp(regPhone, otpCode);
    if (res.success) {
      setOtpVerified(true);
      setSuccessMsg(res.message || 'Phone verified and linked successfully in Firebase!');
    } else {
      setErrorMsg(res.error || 'Invalid OTP code');
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);

    if (regRole === 'WORKER') {
      if (!emailVerified) {
        setErrorMsg('Please verify your email address via 6-digit code or email link first');
        return;
      }
      if (!otpVerified) {
        setErrorMsg('Please verify your phone number via SMS OTP first');
        return;
      }
    }

    let effectiveCategory = workerCategory;
    if (regRole === 'WORKER' && workerCategory === 'Other') {
      const cleanCustom = customProfession.trim();
      if (!cleanCustom) {
        setErrorMsg('Please specify your custom trade or profession');
        return;
      }
      effectiveCategory = cleanCustom;
    }

    const payload = {
      full_name: regName,
      email: regEmail,
      phone: regPhone,
      password: regPassword,
      role: regRole,
      worker_category: regRole === 'WORKER' ? effectiveCategory : null,
      skills: regRole === 'WORKER' ? [effectiveCategory] : null,
      origin_state: regRole === 'WORKER' ? workerOriginState : null,
      current_state: regRole === 'WORKER' ? 'Karnataka' : null,
      organization_name: regRole === 'EMPLOYER' ? orgName : null,
      organization_status: regRole === 'EMPLOYER' ? 'PENDING_REVIEW' : 'APPROVED',
      registration_number: regRole === 'EMPLOYER' ? (orgRegNo || 'REG-' + Date.now()) : null,
      categories_requested: regRole === 'EMPLOYER' ? (orgCategories ? orgCategories.split(',').map(s => s.trim()).filter(Boolean) : ['Mason', 'Electrician']) : null
    };

    try {
      const res = await register(payload);
      if (res.success) {
        if (regRole === 'EMPLOYER') {
          setSuccessMsg('Employer organization registered in PENDING_REVIEW. Admin review required before activation.');
        } else {
          if (onRoleSelect) onRoleSelect(res.user.role);
          onClose();
        }
      } else {
        const errDetail = res.error?.response?.data?.detail || res.error || (res.detail ? (typeof res.detail === 'string' ? res.detail : JSON.stringify(res.detail)) : 'Registration failed');
        setErrorMsg(typeof errDetail === 'object' ? JSON.stringify(errDetail) : String(errDetail));
      }
    } catch (err) {
      const errDetail = err.response?.data?.detail || err.message || 'Registration failed';
      setErrorMsg(typeof errDetail === 'object' ? JSON.stringify(errDetail) : String(errDetail));
    }
  };

  const handleActivateSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    try {
      const res = await fetch('/api/v1/auth/activate-employer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          activation_token: actToken.trim(),
          password: actPassword
        })
      });
      const data = await res.json();
      if (res.ok) {
        setSuccessMsg('Account activated successfully! You may now sign in as Employer.');
        setTab('login');
        setEmail(data.email || '');
      } else {
        const detailMsg = typeof data.detail === 'string'
          ? data.detail
          : (Array.isArray(data.detail) ? data.detail.map(d => d.msg || 'Invalid field').join(', ') : 'Activation failed');
        if (detailMsg.includes('WRONG_TARGET_TYPE')) {
          setErrorMsg(detailMsg + ' — If you are activating a Government Officer account, please use the "Activate Gov" tab.');
        } else {
          setErrorMsg(detailMsg);
        }
      }
    } catch {
      setErrorMsg('Network error during activation');
    }
  };

  const handleActivateGovSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    const cleanToken = govToken.trim();
    if (!cleanToken) {
      setErrorMsg('Please enter the secure activation token');
      return;
    }
    if (!govPassword || govPassword.length < 6) {
      setErrorMsg('Password must be at least 6 characters');
      return;
    }
    if (govPassword !== govConfirmPassword) {
      setErrorMsg('Passwords do not match');
      return;
    }

    try {
      setActivatingGov(true);
      const res = await fetch('/api/v1/government/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          activation_token: cleanToken,
          password: govPassword
        })
      });
      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(
          data.message ||
          `Government officer account activated successfully! Officer ${data.officer_reference_id || 'ACTIVE'} is now ACTIVE. You may now sign in.`
        );
        setGovPassword('');
        setGovConfirmPassword('');
        setTab('login');
        if (data.official_email) {
          setEmail(data.official_email);
        }
      } else {
        const detailMsg = typeof data.detail === 'string'
          ? data.detail
          : (Array.isArray(data.detail) ? data.detail.map(d => d.msg || 'Invalid field').join(', ') : 'Activation failed');
        if (detailMsg.includes('WRONG_TARGET_TYPE')) {
          setErrorMsg(detailMsg + ' — If you are activating an Employer Organization, please use the "Activate Org" tab.');
        } else {
          setErrorMsg(detailMsg);
        }
      }
    } catch {
      setErrorMsg('Network error during government officer activation');
    } finally {
      setActivatingGov(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in">
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden text-slate-100 max-h-[90vh] flex flex-col">
        
        {/* Invisible reCAPTCHA Container */}
        <div id="recaptcha-container"></div>

        {/* Top Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50 shrink-0">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-white">PASSKHADAM Authentication</h3>
              <p className="text-xs text-slate-400">Firebase Auth & Role-Based Access Control</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="grid grid-cols-2 sm:grid-cols-4 p-1 m-6 mb-3 gap-1 bg-slate-950 rounded-xl border border-slate-800/80 text-xs font-medium shrink-0">
          <button
            onClick={() => { setTab('login'); setErrorMsg(null); }}
            className={`py-2 rounded-lg transition ${tab === 'login' ? 'bg-blue-600 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-white'}`}
          >
            Sign In
          </button>
          <button
            onClick={() => { setTab('register'); setErrorMsg(null); }}
            className={`py-2 rounded-lg transition ${tab === 'register' ? 'bg-blue-600 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-white'}`}
          >
            Register
          </button>
          <button
            onClick={() => { setTab('activate'); setErrorMsg(null); }}
            className={`py-2 rounded-lg transition ${tab === 'activate' ? 'bg-indigo-600 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-white'}`}
          >
            Activate Org
          </button>
          <button
            onClick={() => { setTab('activate_gov'); setErrorMsg(null); }}
            className={`py-2 rounded-lg transition ${tab === 'activate_gov' ? 'bg-purple-600 text-white shadow-sm font-semibold' : 'text-slate-400 hover:text-white'}`}
          >
            Activate Gov
          </button>
        </div>

        {/* Alerts */}
        {errorMsg && (
          <div className="mx-6 mb-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2 shrink-0">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg)}</span>
          </div>
        )}
        {successMsg && (
          <div className="mx-6 mb-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2 shrink-0">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{typeof successMsg === 'string' ? successMsg : JSON.stringify(successMsg)}</span>
          </div>
        )}

        {/* Scrollable Form Content */}
        <div className="px-6 pb-6 overflow-y-auto space-y-4">
          {tab === 'login' && (
            <div className="space-y-4">
              <form onSubmit={handleLoginSubmit} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Email Address</label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                    <input
                      type="email"
                      required
                      placeholder="worker@passkhadam.org"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-xs font-medium text-slate-400">Password</label>
                    <button
                      type="button"
                      onClick={handleForgotPassword}
                      className="text-[11px] text-blue-400 hover:underline"
                    >
                      Forgot password?
                    </button>
                  </div>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                    <input
                      type="password"
                      required
                      placeholder="••••••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium text-sm transition shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2"
                >
                  {loading ? 'Authenticating with Firebase...' : 'Sign In via Firebase'}
                  <ArrowRight className="w-4 h-4" />
                </button>
              </form>

              {/* Authorized Access Information */}
              <div className="pt-3 border-t border-slate-800 text-xs space-y-2">
                <div className="flex items-center gap-1.5 text-slate-400 font-semibold text-[11px] uppercase tracking-wider">
                  <Shield className="w-3.5 h-3.5 text-blue-400" />
                  <span>Authorized Access</span>
                </div>
                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-slate-400">
                  <p className="text-[11px] leading-relaxed">
                    Sign in with your verified credentials. Worker accounts self-register via the <strong>Register</strong> tab. Employers and Government Officers activate via single-use token in <strong>Activate Org</strong> or <strong>Activate Gov</strong>.
                  </p>
                </div>
              </div>
            </div>
          )}

          {tab === 'register' && (
            <form onSubmit={handleRegisterSubmit} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Select Role to Register</label>
                <div className="grid grid-cols-2 gap-2 text-xs font-medium">
                  <button
                    type="button"
                    onClick={() => setRegRole('WORKER')}
                    className={`py-2 px-3 rounded-xl border text-center transition ${
                      regRole === 'WORKER' ? 'bg-blue-600/30 border-blue-500 text-blue-300 font-semibold' : 'bg-slate-950 border-slate-800 text-slate-400'
                    }`}
                  >
                    👷 Migrant Worker
                  </button>
                  <button
                    type="button"
                    onClick={() => setRegRole('EMPLOYER')}
                    className={`py-2 px-3 rounded-xl border text-center transition ${
                      regRole === 'EMPLOYER' ? 'bg-indigo-600/30 border-indigo-500 text-indigo-300 font-semibold' : 'bg-slate-950 border-slate-800 text-slate-400'
                    }`}
                  >
                    🏢 Construction Employer
                  </button>
                </div>
                <p className="text-[10px] text-slate-500 mt-1">
                  * Government, Admin, and Aadhaar operator accounts are controlled and securely provisioned.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  {regRole === 'WORKER' ? 'Full Legal Name' : 'Company / Organization Name'}
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    placeholder={regRole === 'WORKER' ? 'Ramesh Kumar Verma' : 'Apex Infrastructure & Construction Ltd'}
                    value={regName}
                    onChange={(e) => {
                      setRegName(e.target.value);
                      if (regRole === 'EMPLOYER') setOrgName(e.target.value);
                    }}
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Official Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="email"
                    required
                    placeholder={regRole === 'WORKER' ? 'ramesh@worker.org' : 'hr@apexinfra.com'}
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Set Password (Required for Firebase Identity)</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="password"
                    required
                    placeholder="•••••••••••• (min. 6 characters)"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              {/* Worker Trade and Origin State */}
              {regRole === 'WORKER' && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-xl bg-slate-950 border border-slate-800/80">
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">Trade / Profession</label>
                    <select
                      value={workerCategory}
                      onChange={(e) => setWorkerCategory(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                    >
                      <option value="Mason">Mason (Bricklayer & Concreting)</option>
                      <option value="Electrician">Electrician (Wiring & Maintenance)</option>
                      <option value="Plumber">Plumber (Pipefitting & Drainage)</option>
                      <option value="Carpenter">Carpenter (Formwork & Woodwork)</option>
                      <option value="Painter">Painter (Finishing & Coating)</option>
                      <option value="Welder">Welder (Arc, Gas & Structural)</option>
                      <option value="Heavy Machinery Operator">Heavy Machinery Operator</option>
                      <option value="Driver">Commercial Driver / Logistics</option>
                      <option value="Steel Fixer">Steel Fixer & Barbender</option>
                      <option value="Tile Setter">Tile & Marble Flooring Setter</option>
                      <option value="General Construction">General Construction Labour</option>
                      <option value="Other">Other / Custom Trade...</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">Home / Origin State</label>
                    <select
                      value={workerOriginState}
                      onChange={(e) => setWorkerOriginState(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                    >
                      <option value="Karnataka">Karnataka</option>
                      <option value="Bihar">Bihar</option>
                      <option value="Uttar Pradesh">Uttar Pradesh</option>
                      <option value="West Bengal">West Bengal</option>
                      <option value="Odisha">Odisha</option>
                      <option value="Maharashtra">Maharashtra</option>
                      <option value="Kerala">Kerala</option>
                      <option value="Rajasthan">Rajasthan</option>
                      <option value="Tamil Nadu">Tamil Nadu</option>
                      <option value="Madhya Pradesh">Madhya Pradesh</option>
                      <option value="Assam">Assam</option>
                      <option value="Jharkhand">Jharkhand</option>
                    </select>
                  </div>
                  {workerCategory === 'Other' && (
                    <div className="col-span-1 sm:col-span-2 pt-2 border-t border-slate-800/80">
                      <label className="block text-[11px] font-medium text-amber-300 mb-1 flex items-center gap-1.5">
                        <span>Specify Custom Trade / Specialization</span>
                        <span className="text-[10px] text-slate-400 font-normal">(e.g. Scaffolder, Solar Technician, Rigger)</span>
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="Enter your specialized trade or profession..."
                        value={customProfession}
                        onChange={(e) => setCustomProfession(e.target.value)}
                        className="w-full px-3 py-1.5 bg-slate-900 border border-amber-500/40 rounded-lg text-xs text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400"
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Email Verification Section */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5 text-blue-400" />
                    Official Email Verification
                  </label>
                  {emailVerified ? (
                    <span className="text-[10px] font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-500/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> Email Verified
                    </span>
                  ) : (
                    <span className="text-[10px] font-medium text-amber-400 bg-amber-950/60 border border-amber-500/30 px-2 py-0.5 rounded-full">
                      Verification Required
                    </span>
                  )}
                </div>

                {!emailVerified && !emailOtpSent && (
                  <div className="space-y-2">
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      Sends Google's official email verification message (<span className="text-blue-300 font-mono text-[10px]">noreply@passkhadam-live.firebaseapp.com</span>) and a 6-digit OTP code directly to <strong className="text-slate-200">{regEmail || 'your email'}</strong>.
                    </p>
                    <button
                      type="button"
                      disabled={sendingEmail}
                      onClick={handleSendEmailOtp}
                      className="w-full py-2 bg-blue-600/30 hover:bg-blue-600/50 border border-blue-500/40 text-blue-300 rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5"
                    >
                      {sendingEmail ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          <span>Dispatching Verification Emails...</span>
                        </>
                      ) : (
                        <>
                          <Mail className="w-3.5 h-3.5" />
                          <span>Send Verification Email & 6-Digit OTP</span>
                        </>
                      )}
                    </button>
                  </div>
                )}

                {emailOtpSent && !emailVerified && (
                  <div className="space-y-3 pt-1">
                    {/* Dispatched Notification Card */}
                    {emailDeliveryMode === 'smtp' ? (
                      <div className="p-2.5 rounded-lg bg-blue-950/50 border border-blue-500/40 text-[11px] text-blue-200 space-y-1">
                        <div className="flex items-center gap-1.5 font-semibold text-blue-300">
                          <Mail className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                          <span>Real verification email dispatched via SMTP to: <span className="font-mono text-white underline">{emailDispatchedTo || regEmail}</span></span>
                        </div>
                        <p className="text-slate-300 text-[10.5px] leading-relaxed">
                          ⚠️ <strong>Inbox Notice:</strong> If the email is delayed, please check your <strong>Spam / Junk folder</strong> and mark as "Not Spam".
                        </p>
                      </div>
                    ) : (
                      <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-500/40 text-[11px] text-amber-200 space-y-1.5">
                        <div className="flex items-center justify-between font-semibold text-amber-300">
                          <div className="flex items-center gap-1.5">
                            <Shield className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                            <span>Demo Fallback Mode ({emailDeliveryMode === 'simulated_fallback' ? 'SMTP Fallback' : 'Simulation'}):</span>
                          </div>
                          <span className="font-mono bg-amber-900/60 border border-amber-500/50 text-white px-2 py-0.5 rounded text-xs font-bold tracking-widest">
                            {simulatedOtpHint || '729415'}
                          </span>
                        </div>
                        <p className="text-amber-100/80 text-[10.5px] leading-relaxed">
                          SMTP server unconfigured or offline. Preserving simulated on-screen OTP fallback so local development and manual testing are never blocked.
                        </p>
                      </div>
                    )}

                    {/* Dual Verification Guidance */}
                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[10.5px] text-slate-300 space-y-1.5">
                      <div className="font-semibold text-slate-200">Dual Verification Options (Use Either Method):</div>
                      <div className="space-y-1 text-slate-400 pl-1">
                        <div>
                          <strong className="text-blue-300">Option 1:</strong> Enter the 6-digit numeric OTP code sent to your inbox.
                        </div>
                        <div>
                          <strong className="text-indigo-300">Option 2:</strong> Click the official link in your email from Google, then press <em>"Check Verification Status"</em>.
                        </div>
                      </div>
                    </div>

                    {/* OTP Entry */}
                    <div className="space-y-1.5">
                      <label className="block text-[11px] font-medium text-slate-400">Option 1: Enter 6-Digit OTP Code</label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          maxLength={6}
                          placeholder="e.g. 729415"
                          value={emailOtpCode}
                          onChange={(e) => setEmailOtpCode(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              handleVerifyEmailOtp();
                            }
                          }}
                          className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 font-mono tracking-widest placeholder:tracking-normal focus:outline-none focus:border-blue-500"
                        />
                        <button
                          type="button"
                          onClick={handleVerifyEmailOtp}
                          className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition shrink-0 shadow-sm"
                        >
                          Verify OTP
                        </button>
                      </div>
                    </div>

                    {/* Link Status Checker */}
                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                      <div className="text-[11px] text-slate-400">
                        Option 2: Clicked Google link?
                      </div>
                      <button
                        type="button"
                        disabled={checkingEmailStatus}
                        onClick={handleCheckEmailLinkStatus}
                        className="px-3 py-1 bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-indigo-200 rounded-lg text-[11px] font-medium transition flex items-center gap-1.5 shrink-0"
                      >
                        {checkingEmailStatus ? (
                          <>
                            <RefreshCw className="w-3 h-3 animate-spin" />
                            <span>Checking...</span>
                          </>
                        ) : (
                          <>
                            <RefreshCw className="w-3 h-3" />
                            <span>Check Verification Status</span>
                          </>
                        )}
                      </button>
                    </div>

                    {/* Resend Link */}
                    <div className="flex justify-end">
                      <button
                        type="button"
                        disabled={sendingEmail}
                        onClick={handleSendEmailOtp}
                        className="text-[10px] text-blue-400 hover:text-blue-300 underline"
                      >
                        {sendingEmail ? 'Resending...' : 'Resend verification email & OTP'}
                      </button>
                    </div>
                  </div>
                )}

                {emailVerified && (
                  <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-xs text-emerald-300 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Email address <strong className="font-mono text-white">{regEmail}</strong> verified and linked to your PassKhadam identity.</span>
                  </div>
                )}
              </div>

              {/* Worker Phone OTP Verification Section */}
              {regRole === 'WORKER' && (
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                      <Smartphone className="w-3.5 h-3.5 text-blue-400" />
                      Firebase Phone Linking (SMS OTP)
                    </label>
                    {otpVerified && (
                      <span className="text-[10px] font-medium text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> Phone Verified
                      </span>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="+91 98765 43210"
                      value={regPhone}
                      onChange={(e) => setRegPhone(e.target.value)}
                      disabled={otpVerified}
                      className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 font-mono"
                    />
                    {!otpVerified && (
                      <button
                        type="button"
                        onClick={handleSendOtp}
                        className="px-3 py-1.5 bg-blue-600/30 hover:bg-blue-600/50 border border-blue-500/40 text-blue-300 rounded-lg text-xs font-medium transition"
                      >
                        {otpSent ? 'Resend OTP' : 'Send Code'}
                      </button>
                    )}
                  </div>

                  <div className="flex items-center justify-between">
                    <p className="text-[10px] text-slate-400">
                      * Supports Console test number or real mobile number.
                    </p>
                    <button
                      type="button"
                      onClick={() => setRegPhone('+91 98765 43210')}
                      className="text-[10px] text-blue-400 hover:text-blue-300 underline font-mono"
                    >
                      Fill Test Number (+91 98765 43210)
                    </button>
                  </div>

                  <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-[10px] text-slate-400 space-y-1">
                    <div className="font-semibold text-slate-300">ℹ️ Why no real SMS arrives for test numbers:</div>
                    <div>• <strong>Test Number (+91 98765 43210):</strong> Google Firebase skips cellular SMS by design for fictional numbers. Use code <span className="font-mono text-emerald-400 font-semibold">123456</span> directly.</div>
                    <div>• <strong>Real Mobile Number:</strong> Firebase dispatches a real SMS via Google Cloud Gateway (free Spark plan allows 10 SMS/day).</div>
                  </div>

                  {smsNotification && (
                    <div className="p-2 rounded-lg bg-blue-950/60 border border-blue-500/40 text-[11px] text-blue-200 font-mono">
                      📲 <strong>Firebase SMS Gateway:</strong>
                      <div className="text-slate-300 mt-0.5">{smsNotification}</div>
                    </div>
                  )}

                  {otpSent && !otpVerified && (
                    <div className="flex gap-2 pt-1">
                      <input
                        type="text"
                        placeholder="Enter 6-digit code (e.g. 123456)"
                        value={otpCode}
                        onChange={(e) => setOtpCode(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleVerifyOtp();
                          }
                        }}
                        className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 font-mono"
                      />
                      <button
                        type="button"
                        onClick={handleVerifyOtp}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition"
                      >
                        Link Phone
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Employer Corporate Information */}
              {regRole === 'EMPLOYER' && (
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2 text-xs">
                  <div className="flex items-center gap-1.5 text-indigo-400 font-semibold">
                    <Building2 className="w-3.5 h-3.5" />
                    Corporate Onboarding & Scope
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-0.5">Registration Ref Number</label>
                    <input
                      type="text"
                      placeholder="CIN-U45200MH2026PTC109876"
                      value={orgRegNo}
                      onChange={(e) => setOrgRegNo(e.target.value)}
                      className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-0.5">Requested Categories</label>
                    <input
                      type="text"
                      value={orgCategories}
                      onChange={(e) => setOrgCategories(e.target.value)}
                      className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200"
                    />
                  </div>
                  <div className="p-2 rounded-lg bg-amber-950/40 border border-amber-500/30 text-[11px] text-amber-300">
                    ⏳ Organization status will be set to <strong>PENDING_REVIEW</strong>. An administrator must approve your application before operational employer features are unlocked.
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={loading || (regRole === 'WORKER' && (!otpVerified || !emailVerified))}
                className={`w-full py-2.5 rounded-xl font-medium text-sm transition shadow-lg flex items-center justify-center gap-2 ${
                  regRole === 'EMPLOYER' || (otpVerified && emailVerified)
                    ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/20'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                }`}
              >
                {loading ? 'Submitting Registration...' : regRole === 'EMPLOYER' ? 'Submit Organization for Review' : 'Complete Worker Registration'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          )}

          {tab === 'activate' && (
            <form onSubmit={handleActivateSubmit} className="space-y-4">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 space-y-1">
                <div className="font-semibold text-white flex items-center gap-1.5">
                  <KeyRound className="w-4 h-4 text-indigo-400" />
                  Employer Account Activation
                </div>
                <p className="text-[11px] text-slate-400">
                  Approved organizations receive a secure activation token via registered email. Enter your token below to activate your account.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Secure Activation Token</label>
                <input
                  type="text"
                  required
                  placeholder="act_token_..."
                  value={actToken}
                  onChange={(e) => setActToken(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Set Account Password</label>
                <input
                  type="password"
                  required
                  placeholder="••••••••••••"
                  value={actPassword}
                  onChange={(e) => setActPassword(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium text-sm transition shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2"
              >
                Activate Organization Account
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          )}

          {tab === 'activate_gov' && (
            <form onSubmit={handleActivateGovSubmit} className="space-y-4">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 space-y-1">
                <div className="font-semibold text-white flex items-center gap-1.5">
                  <Landmark className="w-4 h-4 text-purple-400" />
                  Government Officer Activation
                </div>
                <p className="text-[11px] text-slate-400">
                  Provisioned state and national welfare officers activate accounts using the secure token dispatched by the platform administrator.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Secure Activation Token</label>
                <input
                  type="text"
                  required
                  placeholder="act_token_..."
                  value={govToken}
                  onChange={(e) => setGovToken(e.target.value)}
                  disabled={activatingGov}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 font-mono focus:outline-none focus:border-purple-500 disabled:opacity-50"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Set Account Password</label>
                <input
                  type="password"
                  required
                  placeholder="•••••••••••• (min. 6 characters)"
                  value={govPassword}
                  onChange={(e) => setGovPassword(e.target.value)}
                  disabled={activatingGov}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-purple-500 disabled:opacity-50"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Confirm Account Password</label>
                <input
                  type="password"
                  required
                  placeholder="••••••••••••"
                  value={govConfirmPassword}
                  onChange={(e) => setGovConfirmPassword(e.target.value)}
                  disabled={activatingGov}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-purple-500 disabled:opacity-50"
                />
              </div>

              <button
                type="submit"
                disabled={activatingGov}
                className="w-full py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl font-medium text-sm transition shadow-lg shadow-purple-600/20 flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {activatingGov ? 'Activating Officer Account...' : 'Activate Government Account'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          )}
        </div>

      </div>
    </div>
  );
}
