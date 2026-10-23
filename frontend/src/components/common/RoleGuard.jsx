import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  ShieldAlert, Clock, AlertTriangle, LogIn, CheckCircle2,
  RefreshCw, Mail, Phone, LogOut, ExternalLink, ArrowRight
} from 'lucide-react';

/**
 * RoleGuard enforces authoritative backend access control per portal:
 * - Checks if user is authenticated
 * - Checks if account status is SUSPENDED or DISABLED
 * - Handles PENDING_REVIEW accounts with an onboarding/review view instead of locking them out
 * - Verifies user role matches requiredRole
 * - Provides interactive, self-service dual verification (Email & Phone) so users are never trapped
 */
export default function RoleGuard({ requiredRole, children, onOpenAuth }) {
  const {
    currentUser,
    checkFirebaseEmailStatus,
    sendEmailOtp,
    verifyEmailOtp,
    sendPhoneOtp,
    verifyPhoneOtp,
    syncVerification,
    logout
  } = useAuth();

  const [checkingEmail, setCheckingEmail] = useState(false);
  const [emailOtpSent, setEmailOtpSent] = useState(false);
  const [emailOtp, setEmailOtp] = useState('');
  const [sendingEmailOtp, setSendingEmailOtp] = useState(false);
  const [verifyingEmailOtp, setVerifyingEmailOtp] = useState(false);

  const [phoneInput, setPhoneInput] = useState(currentUser?.phone || '+91 98765 43210');
  const [phoneOtpSent, setPhoneOtpSent] = useState(false);
  const [phoneOtp, setPhoneOtp] = useState('');
  const [sendingPhoneOtp, setSendingPhoneOtp] = useState(false);
  const [verifyingPhoneOtp, setVerifyingPhoneOtp] = useState(false);

  const [feedbackMsg, setFeedbackMsg] = useState(null);
  const [feedbackType, setFeedbackType] = useState('info');

  const handleOpenAuth = async () => {
    await logout();
    if (onOpenAuth) {
      onOpenAuth();
    } else if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('pk_open_auth'));
    }
  };

  useEffect(() => {
    if (currentUser?.phone) {
      setPhoneInput(currentUser.phone);
    }
  }, [currentUser?.phone]);

  const handleCheckEmailLink = async () => {
    setFeedbackMsg(null);
    setCheckingEmail(true);
    const res = await checkFirebaseEmailStatus(currentUser?.email);
    setCheckingEmail(false);
    if (res.verified || res.success) {
      setFeedbackType('success');
      setFeedbackMsg('Email verified successfully! Firebase status confirmed.');
      await syncVerification();
    } else {
      setFeedbackType('error');
      setFeedbackMsg(res.error || 'Email link not activated yet. Please click the link sent to your inbox (or check spam folder), then click this button again.');
    }
  };

  const handleSendEmailOtp = async () => {
    setFeedbackMsg(null);
    setSendingEmailOtp(true);
    const res = await sendEmailOtp(currentUser?.email);
    setSendingEmailOtp(false);
    if (res.success) {
      setEmailOtpSent(true);
      setFeedbackType('info');
      setFeedbackMsg(res.message || `Verification OTP code dispatched to ${currentUser?.email}`);
      if (res.otp_hint && res.delivery_mode !== 'smtp') {
        setEmailOtp(res.otp_hint);
      }
    } else {
      setFeedbackType('error');
      setFeedbackMsg(res.error || 'Failed to dispatch email verification OTP.');
    }
  };

  const handleVerifyEmailOtp = async () => {
    if (!emailOtp.trim()) {
      setFeedbackType('error');
      setFeedbackMsg('Please enter the 6-digit OTP code received in your email.');
      return;
    }
    setFeedbackMsg(null);
    setVerifyingEmailOtp(true);
    const res = await verifyEmailOtp(currentUser?.email, emailOtp.trim());
    setVerifyingEmailOtp(false);
    if (res.success) {
      setFeedbackType('success');
      setFeedbackMsg(res.message || 'Email successfully verified!');
      await syncVerification();
    } else {
      setFeedbackType('error');
      setFeedbackMsg(res.error || 'Invalid email verification code.');
    }
  };

  const handleSendPhoneOtp = async () => {
    setFeedbackMsg(null);
    setSendingPhoneOtp(true);
    const res = await sendPhoneOtp(phoneInput, 'recaptcha-guard-container');
    setSendingPhoneOtp(false);
    if (res.success) {
      setPhoneOtpSent(true);
      setFeedbackType('info');
      setFeedbackMsg(res.message || 'SMS OTP code dispatched.');
      if (res.is_test_number) {
        setPhoneOtp('123456');
      } else if (res.otp_hint) {
        setPhoneOtp(res.otp_hint);
      }
    } else {
      setFeedbackType('error');
      setFeedbackMsg(res.error || 'Failed to send SMS OTP.');
    }
  };

  const handleVerifyPhoneOtp = async () => {
    if (!phoneOtp.trim()) {
      setFeedbackType('error');
      setFeedbackMsg('Please enter the 6-digit SMS OTP code.');
      return;
    }
    setFeedbackMsg(null);
    setVerifyingPhoneOtp(true);
    const res = await verifyPhoneOtp(phoneInput, phoneOtp.trim());
    setVerifyingPhoneOtp(false);
    if (res.success) {
      setFeedbackType('success');
      setFeedbackMsg(res.message || 'Phone number successfully verified!');
      await syncVerification();
    } else {
      setFeedbackType('error');
      setFeedbackMsg(res.error || 'Invalid phone verification code.');
    }
  };

  if (!currentUser) {
    return (
      <div className="min-h-[500px] flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-6 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center mx-auto">
            <LogIn className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Authentication Required</h3>
            <p className="text-sm text-slate-400 mt-1">
              Please sign in with your credentials or select a 1-click demo role to access the {requiredRole} portal.
            </p>
          </div>
          <button
            onClick={handleOpenAuth}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium text-sm transition"
          >
            Open Sign-In Dialog
          </button>
        </div>
      </div>
    );
  }

  // Check Account Status
  if (currentUser.status === 'SUSPENDED' || currentUser.status === 'DISABLED') {
    return (
      <div className="min-h-[500px] flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-slate-900 border border-rose-900/50 rounded-2xl p-6 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-600/20 text-rose-400 border border-rose-500/30 flex items-center justify-center mx-auto">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-rose-400">Account Access Suspended</h3>
            <p className="text-sm text-slate-400 mt-1">
              Your account has been suspended by system governance. Protected portal operations are restricted.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Dual Verification Enforcement for non-demo users: Interactive Self-Service Panel
  if (currentUser && !currentUser.is_demo) {
    const isEmailVerified = Boolean(currentUser.is_email_verified);
    const isPhoneVerified = Boolean(currentUser.is_phone_verified);
    if (!isEmailVerified || !isPhoneVerified) {
      return (
        <div className="min-h-[500px] flex items-center justify-center p-4 sm:p-6">
          <div className="max-w-lg w-full bg-slate-900 border border-amber-900/40 rounded-2xl p-6 sm:p-8 space-y-5 shadow-2xl">
            {/* reCAPTCHA DOM anchor for Firebase phone verification */}
            <div id="recaptcha-guard-container" className="hidden"></div>

            <div className="text-center space-y-2">
              <div className="w-14 h-14 rounded-full bg-amber-600/20 text-amber-400 border border-amber-500/30 flex items-center justify-center mx-auto">
                <ShieldAlert className="w-7 h-7" />
              </div>
              <h3 className="text-xl font-bold text-white">Dual Verification Required</h3>
              <p className="text-xs sm:text-sm text-slate-400">
                PassKhadam protocol requires dual verification (Email &amp; Phone) before accessing operational portal features.
              </p>
            </div>

            {/* Status Checklist & Action Cards */}
            <div className="space-y-4">
              {/* Email Verification Section */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2">
                    <Mail className="w-4 h-4 text-slate-400" />
                    <span className="text-slate-300 font-medium truncate max-w-[220px]">
                      Email ({currentUser.email || 'N/A'})
                    </span>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded text-[10px] font-semibold ${isEmailVerified ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'}`}>
                    {isEmailVerified ? 'VERIFIED' : 'UNVERIFIED'}
                  </span>
                </div>

                {!isEmailVerified && (
                  <div className="space-y-2.5 pt-2 border-t border-slate-800/80">
                    <p className="text-[11px] text-slate-400">
                      Verify via the link received in your email or dispatch a 6-digit OTP:
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <button
                        onClick={handleCheckEmailLink}
                        disabled={checkingEmail}
                        className="py-2 px-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 disabled:opacity-50"
                      >
                        {checkingEmail ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                        Check Email Link
                      </button>
                      <button
                        onClick={handleSendEmailOtp}
                        disabled={sendingEmailOtp}
                        className="py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition flex items-center justify-center gap-1.5 disabled:opacity-50"
                      >
                        {sendingEmailOtp ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}
                        Send 6-Digit OTP
                      </button>
                    </div>

                    {emailOtpSent && (
                      <div className="flex items-center gap-2 pt-1">
                        <input
                          type="text"
                          placeholder="Enter 6-digit email OTP"
                          value={emailOtp}
                          onChange={(e) => setEmailOtp(e.target.value)}
                          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono tracking-widest"
                          maxLength={6}
                        />
                        <button
                          onClick={handleVerifyEmailOtp}
                          disabled={verifyingEmailOtp}
                          className="py-1.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition disabled:opacity-50"
                        >
                          {verifyingEmailOtp ? 'Verifying...' : 'Verify OTP'}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Phone Verification Section */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2">
                    <Phone className="w-4 h-4 text-slate-400" />
                    <span className="text-slate-300 font-medium truncate max-w-[220px]">
                      Phone ({currentUser.phone || phoneInput || 'N/A'})
                    </span>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded text-[10px] font-semibold ${isPhoneVerified ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'}`}>
                    {isPhoneVerified ? 'VERIFIED' : 'UNVERIFIED'}
                  </span>
                </div>

                {!isPhoneVerified && (
                  <div className="space-y-2.5 pt-2 border-t border-slate-800/80">
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        placeholder="+91 98765 43210"
                        value={phoneInput}
                        onChange={(e) => setPhoneInput(e.target.value)}
                        className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                      />
                      <button
                        onClick={handleSendPhoneOtp}
                        disabled={sendingPhoneOtp}
                        className="py-1.5 px-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition whitespace-nowrap disabled:opacity-50"
                      >
                        {sendingPhoneOtp ? 'Sending...' : 'Send SMS OTP'}
                      </button>
                    </div>

                    {phoneOtpSent && (
                      <div className="flex items-center gap-2 pt-1">
                        <input
                          type="text"
                          placeholder="Enter 6-digit SMS OTP"
                          value={phoneOtp}
                          onChange={(e) => setPhoneOtp(e.target.value)}
                          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono tracking-widest"
                          maxLength={6}
                        />
                        <button
                          onClick={handleVerifyPhoneOtp}
                          disabled={verifyingPhoneOtp}
                          className="py-1.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition disabled:opacity-50"
                        >
                          {verifyingPhoneOtp ? 'Verifying...' : 'Verify Phone'}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Interactive Feedback Alert */}
            {feedbackMsg && (
              <div className={`p-3 rounded-xl text-xs flex items-start space-x-2 ${
                feedbackType === 'success'
                  ? 'bg-emerald-950/60 border border-emerald-500/40 text-emerald-200'
                  : feedbackType === 'error'
                  ? 'bg-rose-950/60 border border-rose-500/40 text-rose-200'
                  : 'bg-blue-950/60 border border-blue-500/40 text-blue-200'
              }`}>
                <span className="text-sm">
                  {feedbackType === 'success' ? '✓' : feedbackType === 'error' ? '⚠️' : 'ℹ️'}
                </span>
                <span className="leading-relaxed">{feedbackMsg}</span>
              </div>
            )}

            {/* Optional Modal Fallback Trigger if provided */}
            {onOpenAuth && (
              <button
                onClick={onOpenAuth}
                className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl font-medium text-xs transition flex items-center justify-center gap-1.5"
              >
                Open Advanced Auth Dialog
              </button>
            )}

            {/* Sign Out / Restart Registration Footer */}
            <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
              <span>Wrong email or need to restart?</span>
              <button
                onClick={logout}
                className="text-rose-400 hover:text-rose-300 font-medium transition flex items-center gap-1"
              >
                <LogOut className="w-3.5 h-3.5" />
                Sign Out / Switch Account
              </button>
            </div>
          </div>
        </div>
      );
    }
  }

  // Handle PENDING_REVIEW Employer Accounts: Show onboarding/review route
  if (requiredRole === 'EMPLOYER' && (currentUser.organization_status === 'PENDING_REVIEW' || currentUser.status === 'PENDING_REVIEW')) {
    return (
      <div className="min-h-[500px] flex items-center justify-center p-6">
        <div className="max-w-lg w-full bg-slate-900 border border-amber-900/40 rounded-2xl p-6 space-y-4">
          <div className="w-12 h-12 rounded-full bg-amber-600/20 text-amber-400 border border-amber-500/30 flex items-center justify-center mx-auto">
            <Clock className="w-6 h-6" />
          </div>
          <div className="text-center">
            <h3 className="text-lg font-bold text-white">Application Under Review</h3>
            <p className="text-sm text-amber-300/90 mt-1 font-medium">
              Status: PENDING_REVIEW
            </p>
            <p className="text-xs text-slate-400 mt-2">
              Your organization registration for <strong className="text-slate-200">{currentUser.organization_name || 'Organization Under Review'}</strong> has been submitted. Platform governance must approve your application before workforce management and worker verification are enabled.
            </p>
          </div>
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400 space-y-1">
            <div className="flex justify-between">
              <span>Organization:</span>
              <span className="text-slate-200 font-mono">{currentUser.organization_name || 'Pending Review'}</span>
            </div>
            <div className="flex justify-between">
              <span>Account Email:</span>
              <span className="text-slate-200">{currentUser.email}</span>
            </div>
            <div className="flex justify-between">
              <span>Activation:</span>
              <span className="text-amber-400">Awaiting Admin Token</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Check Role Match
  const rawRole = currentUser.role || currentUser.user?.role || '';
  const userRole = String(rawRole).trim().toUpperCase();
  const reqRole = String(requiredRole || '').trim().toUpperCase();

  // If user is authenticated but has no valid role assigned
  if (!userRole) {
    return (
      <div className="min-h-[500px] flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-slate-900 border border-amber-900/40 rounded-2xl p-6 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-amber-600/20 text-amber-400 border border-amber-500/30 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Session Incomplete</h3>
            <p className="text-sm text-slate-400 mt-1">
              Your profile does not have an active system role or your session has expired. Please sign in again.
            </p>
          </div>
          <button
            onClick={handleOpenAuth}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-medium transition flex items-center justify-center gap-1.5"
          >
            <LogIn className="w-4 h-4" />
            Sign In / Switch Account
          </button>
        </div>
      </div>
    );
  }

  if (userRole !== reqRole && userRole !== 'ADMIN') {
    return (
      <div className="min-h-[500px] flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-6 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-amber-600/20 text-amber-400 border border-amber-500/30 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Role Mismatch</h3>
            <p className="text-sm text-slate-400 mt-1">
              You are signed in as <strong className="text-slate-200">{userRole}</strong>. This portal requires the <strong className="text-blue-400">{reqRole}</strong> role.
            </p>
          </div>
          <button
            onClick={handleOpenAuth}
            className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-medium transition flex items-center justify-center gap-1.5"
          >
            <LogOut className="w-3.5 h-3.5" />
            Switch Account / Sign In
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
