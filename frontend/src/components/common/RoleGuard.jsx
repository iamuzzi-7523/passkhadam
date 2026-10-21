import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { ShieldAlert, Clock, AlertTriangle, LogIn } from 'lucide-react';

/**
 * RoleGuard enforces authoritative backend access control per portal:
 * - Checks if user is authenticated
 * - Checks if account status is SUSPENDED or DISABLED
 * - Handles PENDING_REVIEW accounts with an onboarding/review view instead of locking them out
 * - Verifies user role matches requiredRole
 */
export default function RoleGuard({ requiredRole, children, onOpenAuth }) {
  const { currentUser } = useAuth();

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
            onClick={onOpenAuth}
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

  // Dual Verification Enforcement for non-demo users
  if (currentUser && !currentUser.is_demo) {
    const isEmailVerified = Boolean(currentUser.is_email_verified);
    const isPhoneVerified = Boolean(currentUser.is_phone_verified);
    if (!isEmailVerified || !isPhoneVerified) {
      return (
        <div className="min-h-[500px] flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-slate-900 border border-amber-900/40 rounded-2xl p-6 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-amber-600/20 text-amber-400 border border-amber-500/30 flex items-center justify-center mx-auto">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Dual Verification Required</h3>
              <p className="text-sm text-slate-400 mt-1">
                PassKhadam security invariants require dual verification (Email &amp; Phone) before accessing operational portal features.
              </p>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-left space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Email Verification ({currentUser.email || 'N/A'}):</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${isEmailVerified ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}`}>
                  {isEmailVerified ? 'VERIFIED' : 'UNVERIFIED'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Phone Verification ({currentUser.phone || 'N/A'}):</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${isPhoneVerified ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}`}>
                  {isPhoneVerified ? 'VERIFIED' : 'UNVERIFIED'}
                </span>
              </div>
            </div>
            <button
              onClick={onOpenAuth}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium text-sm transition"
            >
              Verify Credentials
            </button>
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
  const userRole = (currentUser.role || '').toUpperCase();
  const reqRole = requiredRole.toUpperCase();

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
              You are signed in as <strong className="text-slate-200">{currentUser.role}</strong>. This portal requires the <strong className="text-blue-400">{requiredRole}</strong> role.
            </p>
          </div>
          <button
            onClick={onOpenAuth}
            className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-medium transition"
          >
            Switch Account / Sign In
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
