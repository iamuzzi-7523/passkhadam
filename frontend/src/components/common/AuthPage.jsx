import React, { useState, useEffect } from 'react';
import {
  Lock, Mail, Phone, User, CheckCircle2, AlertCircle, ArrowRight,
  Shield, Building2, KeyRound, RefreshCw, Landmark, Sparkles
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getTranslation } from '../../i18n/translations';

export default function AuthPage({ currentLang = 'en', onRoleSelect }) {
  const { login, register, resetPassword, sendPhoneOtp, verifyPhoneOtp, sendEmailOtp, verifyEmailOtp, checkFirebaseEmailStatus, loading } = useAuth();
  
  const [tab, setTab] = useState('login'); // 'login' | 'register' | 'activate' | 'activate_gov'
  
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
  
  // Employer Org fields
  const [orgName, setOrgName] = useState('');
  const [orgRegNo, setOrgRegNo] = useState('');
  const [orgCategories, setOrgCategories] = useState('Mason, Electrician, Plumber');

  // Employer Activation fields
  const [actToken, setActToken] = useState('');
  const [actPassword, setActPassword] = useState('');

  // Government Officer Activation fields
  const [govToken, setGovToken] = useState('');
  const [govPassword, setGovPassword] = useState('');
  const [govConfirmPassword, setGovConfirmPassword] = useState('');
  const [activatingGov, setActivatingGov] = useState(false);

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

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const search = window.location.search;
    const pathname = window.location.pathname.toLowerCase();

    if (search || pathname.includes('activate')) {
      const params = new URLSearchParams(search);
      const rawToken = params.get('token') || params.get('activation_token');

      if (rawToken) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }

      if (rawToken || pathname.includes('activate')) {
        const isGov = pathname.includes('/government/activate') || params.get('target') === 'government' || params.get('type') === 'government';
        const isEmp = pathname.includes('/employer/activate') || params.get('target') === 'employer' || params.get('type') === 'employer';

        const targetTab = isGov ? 'activate_gov' : (isEmp ? 'activate' : 'activate_gov');
        setTab(targetTab);
        if (rawToken) {
          if (targetTab === 'activate_gov') setGovToken(rawToken);
          else setActToken(rawToken);
        }
      }
    }
  }, []);

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    const res = await login(email, password);
    if (res.success) {
      if (onRoleSelect) onRoleSelect(res.user.role);
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
    const res = await verifyEmailOtp(targetEmail, emailOtpCode.trim());
    if (res.success) {
      setEmailVerified(true);
      setSuccessMsg(res.message || 'Email verified and confirmed in Firebase!');
    } else {
      setErrorMsg(res.error || 'Invalid or expired email OTP');
    }
  };

  const handleCheckEmailVerified = async () => {
    setErrorMsg(null);
    setCheckingEmailStatus(true);
    const targetEmail = emailDispatchedTo || regEmail;
    const res = await checkFirebaseEmailStatus(targetEmail, regPassword);
    setCheckingEmailStatus(false);
    if (res.verified || res.success) {
      setEmailVerified(true);
      setSuccessMsg(res.message || 'Email link verification confirmed in Firebase!');
    } else {
      setErrorMsg(res.error || res.message || 'Email not verified yet. Please click the link sent to your email.');
    }
  };

  const handleSendPhoneOtp = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);
    const res = await sendPhoneOtp(regPhone);
    if (res.success) {
      setOtpSent(true);
      setSmsNotification(res.message);
      setSuccessMsg(res.message);
      if (res.simulated && res.otp_hint) {
        setOtpCode(res.otp_hint);
      }
    } else {
      setErrorMsg(res.error || 'Failed to send SMS OTP');
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

    const payload = {
      full_name: regName,
      email: regEmail,
      phone: regPhone,
      password: regPassword,
      role: regRole,
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
    <div className="w-full min-h-[calc(100vh-160px)] flex items-center justify-center py-6 px-3 sm:px-6">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden text-slate-100 flex flex-col">
        
        {/* Invisible reCAPTCHA Container */}
        <div id="recaptcha-container"></div>

        {/* Top Header Card */}
        <div className="px-6 py-5 border-b border-slate-800 bg-slate-950/60 text-center space-y-1">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/20 text-white font-black text-2xl mx-auto mb-2">
            PK
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">PASSKHADAM Authentication</h2>
          <p className="text-xs text-slate-400">
            Decentralized Portable Identity • W3C Verifiable Credentials • EVM Anchored
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="grid grid-cols-2 sm:grid-cols-4 p-1 m-4 sm:m-6 mb-3 gap-1 bg-slate-950 rounded-xl border border-slate-800/80 text-xs font-medium">
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
          <div className="mx-4 sm:mx-6 mb-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg)}</span>
          </div>
        )}
        {successMsg && (
          <div className="mx-4 sm:mx-6 mb-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{typeof successMsg === 'string' ? successMsg : JSON.stringify(successMsg)}</span>
          </div>
        )}

        {/* Form Body */}
        <div className="px-4 sm:px-6 pb-6 space-y-4">
          
          {/* TAB 1: SIGN IN */}
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
                      placeholder="user@example.com"
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

          {/* TAB 2: REGISTER */}
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
                    placeholder={regRole === 'WORKER' ? 'Ramesh Verma' : 'Apex Infra Projects Ltd'}
                    value={regRole === 'WORKER' ? regName : orgName}
                    onChange={(e) => regRole === 'WORKER' ? setRegName(e.target.value) : setOrgName(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              {regRole === 'EMPLOYER' && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Contact Person Name</label>
                    <input
                      type="text"
                      required
                      placeholder="Vikram Malhotra"
                      value={regName}
                      onChange={(e) => setRegName(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Registration / CIN / PAN Number</label>
                    <input
                      type="text"
                      placeholder="U45200MH2012PLC234567"
                      value={orgRegNo}
                      onChange={(e) => setOrgRegNo(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">Trade Categories Requested (Comma separated)</label>
                    <input
                      type="text"
                      placeholder="Mason, Electrician, Plumber"
                      value={orgCategories}
                      onChange={(e) => setOrgCategories(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="email"
                    required
                    placeholder="user@example.com"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="password"
                    required
                    placeholder="••••••••••••"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              {/* Worker Dual-Verification (Email & Phone) */}
              {regRole === 'WORKER' && (
                <div className="space-y-3 pt-2 border-t border-slate-800">
                  <p className="text-xs font-semibold text-blue-400 flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5" />
                    Dual Verification (Security Invariant)
                  </p>

                  {/* 1. Email Verification */}
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-300">1. Email Verification:</span>
                      {emailVerified ? (
                        <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Verified ✓
                        </span>
                      ) : (
                        <span className="text-[11px] text-amber-400">Required</span>
                      )}
                    </div>
                    {!emailVerified && (
                      <div className="space-y-2">
                        <button
                          type="button"
                          onClick={handleSendEmailOtp}
                          disabled={sendingEmail}
                          className="w-full py-1.5 bg-slate-800 hover:bg-slate-750 text-slate-200 rounded-lg text-xs font-medium transition"
                        >
                          {sendingEmail ? 'Dispatching...' : (emailOtpSent ? 'Resend Verification' : 'Send Email Verification Code')}
                        </button>
                        {emailOtpSent && (
                          <div className="flex gap-2">
                            <input
                              type="text"
                              maxLength={6}
                              placeholder="6-Digit Code"
                              value={emailOtpCode}
                              onChange={(e) => setEmailOtpCode(e.target.value)}
                              className="w-1/2 px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs font-mono text-center tracking-widest text-slate-200"
                            />
                            <button
                              type="button"
                              onClick={handleVerifyEmailOtp}
                              className="w-1/2 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition"
                            >
                              Confirm Code
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* 2. Phone Verification */}
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-300">2. Phone SMS OTP:</span>
                      {otpVerified ? (
                        <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Verified ✓
                        </span>
                      ) : (
                        <span className="text-[11px] text-amber-400">Required</span>
                      )}
                    </div>
                    {!otpVerified && (
                      <div className="space-y-2">
                        <div className="flex gap-2">
                          <input
                            type="text"
                            placeholder="+91 98765 43210"
                            value={regPhone}
                            onChange={(e) => setRegPhone(e.target.value)}
                            className="w-2/3 px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200"
                          />
                          <button
                            type="button"
                            onClick={handleSendPhoneOtp}
                            className="w-1/3 py-1.5 bg-slate-800 hover:bg-slate-750 text-slate-200 rounded-lg text-xs font-medium transition"
                          >
                            {otpSent ? 'Resend' : 'Send OTP'}
                          </button>
                        </div>
                        {otpSent && (
                          <div className="flex gap-2">
                            <input
                              type="text"
                              maxLength={6}
                              placeholder="6-Digit SMS OTP"
                              value={otpCode}
                              onChange={(e) => setOtpCode(e.target.value)}
                              className="w-1/2 px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs font-mono text-center tracking-widest text-slate-200"
                            />
                            <button
                              type="button"
                              onClick={handleVerifyOtp}
                              className="w-1/2 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition"
                            >
                              Verify Phone
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium text-sm transition shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2"
              >
                {loading ? 'Creating Account...' : (regRole === 'EMPLOYER' ? 'Submit Employer Registration' : 'Complete Worker Registration')}
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          )}

          {/* TAB 3: ACTIVATE ORG */}
          {tab === 'activate' && (
            <form onSubmit={handleActivateSubmit} className="space-y-3">
              <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs">
                Activate an approved employer organization using the single-use token sent to your official email.
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Activation Token</label>
                <input
                  type="text"
                  required
                  placeholder="Paste 32-64 character token"
                  value={actToken}
                  onChange={(e) => setActToken(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Set Password</label>
                <input
                  type="password"
                  required
                  placeholder="Minimum 6 characters"
                  value={actPassword}
                  onChange={(e) => setActPassword(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <button
                type="submit"
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium text-sm transition"
              >
                Activate Employer Organization
              </button>
            </form>
          )}

          {/* TAB 4: ACTIVATE GOV */}
          {tab === 'activate_gov' && (
            <form onSubmit={handleActivateGovSubmit} className="space-y-3">
              <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-300 text-xs">
                Activate a provisioned Government Officer account using the secure token issued by Platform Governance.
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Secure Officer Activation Token</label>
                <input
                  type="text"
                  required
                  placeholder="Paste single-use officer token"
                  value={govToken}
                  onChange={(e) => setGovToken(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm font-mono text-slate-200 focus:outline-none focus:border-purple-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Set Official Password</label>
                <input
                  type="password"
                  required
                  placeholder="Minimum 6 characters"
                  value={govPassword}
                  onChange={(e) => setGovPassword(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-purple-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Confirm Password</label>
                <input
                  type="password"
                  required
                  placeholder="Re-enter password"
                  value={govConfirmPassword}
                  onChange={(e) => setGovConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-purple-500"
                />
              </div>
              <button
                type="submit"
                disabled={activatingGov}
                className="w-full py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl font-medium text-sm transition"
              >
                {activatingGov ? 'Activating Officer Profile...' : 'Activate Government Account'}
              </button>
            </form>
          )}

        </div>
      </div>
    </div>
  );
}
