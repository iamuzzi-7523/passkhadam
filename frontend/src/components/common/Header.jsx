import React, { useState, useEffect } from 'react';
import {
  UserCheck, Building2, Landmark, Settings, Fingerprint,
  Wallet, Globe, Server, LogIn, LogOut, User, ChevronDown, ShieldAlert
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useWeb3Wallet } from '../../context/Web3Context';
import { languages, getTranslation } from '../../i18n/translations';
import AuthModal from './AuthModal';
import Web3WalletModal from './Web3WalletModal';
import NetworkSettingsModal from './NetworkSettingsModal';

export default function Header({
  currentRole,
  onRoleChange,
  currentLang,
  onLangChange,
  isAuthOpen: externalAuthOpen,
  setIsAuthOpen: externalSetAuthOpen
}) {
  const { currentUser, logout } = useAuth();
  const { isConnected, account, networkName, isSimulated } = useWeb3Wallet();

  const [internalAuthOpen, setInternalAuthOpen] = useState(false);
  const isAuthOpen = externalAuthOpen !== undefined ? externalAuthOpen : internalAuthOpen;
  const setIsAuthOpen = externalSetAuthOpen !== undefined ? externalSetAuthOpen : setInternalAuthOpen;
  const [authInitialTab, setAuthInitialTab] = useState('login');
  const [authInitialToken, setAuthInitialToken] = useState('');
  const [isWalletOpen, setIsWalletOpen] = useState(false);
  const [isNetworkOpen, setIsNetworkOpen] = useState(false);
  const [langDropdownOpen, setLangDropdownOpen] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const search = window.location.search;
    const pathname = window.location.pathname.toLowerCase();

    if (search || pathname.includes('activate')) {
      const params = new URLSearchParams(search);
      const rawToken = params.get('token') || params.get('activation_token');

      // IMMEDIATELY sanitize the browser URL before any network calls
      if (rawToken) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }

      if (rawToken || pathname.includes('activate')) {
        const isGov = pathname.includes('/government/activate') || params.get('target') === 'government' || params.get('type') === 'government';
        const isEmp = pathname.includes('/employer/activate') || params.get('target') === 'employer' || params.get('type') === 'employer';

        const targetTab = isGov ? 'activate_gov' : (isEmp ? 'activate' : 'activate_gov');

        setAuthInitialTab(targetTab);
        if (rawToken) {
          setAuthInitialToken(rawToken);
        }
        setIsAuthOpen(true);
      }
    }

    const handlePkOpenAuth = () => {
      setAuthInitialTab('login');
      setIsAuthOpen(true);
    };

    window.addEventListener('pk_open_auth', handlePkOpenAuth);
    return () => {
      window.removeEventListener('pk_open_auth', handlePkOpenAuth);
    };
  }, []);

  const roles = [
    { id: 'WORKER', key: 'roleWorker', icon: UserCheck, color: 'text-blue-400' },
    { id: 'EMPLOYER', key: 'roleEmployer', icon: Building2, color: 'text-emerald-400' },
    { id: 'GOVERNMENT', key: 'roleGov', icon: Landmark, color: 'text-purple-400' },
    { id: 'ADMIN', key: 'roleAdmin', icon: Settings, color: 'text-amber-400' },
    { id: 'AADHAAR', key: 'roleAadhaar', icon: Fingerprint, color: 'text-rose-400' },
  ];

  const handleRoleClick = (roleId) => {
    onRoleChange(roleId);
  };

  const currentLangObj = languages.find(l => l.code === currentLang) || languages[0];

  return (
    <>
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-40">
        <div className="max-w-[1600px] w-full mx-auto px-3 sm:px-6 lg:px-8 py-3">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            
            {/* Logo & Platform Tagline */}
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/20 text-white font-black text-xl">
                PK
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h1 className="font-bold text-lg text-white tracking-tight">{getTranslation(currentLang, 'appName')}</h1>
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                    {getTranslation(currentLang, 'version')}
                  </span>
                </div>
                <p className="text-xs text-slate-400">{getTranslation(currentLang, 'appTagline')}</p>
              </div>
            </div>

            {/* Global Controls: Wallet, Network, Language, Auth */}
            <div className="flex items-center flex-wrap gap-2 text-xs">
              
              {/* Cloud Staging Status Badge */}
              <div
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700/60 text-slate-300 shadow-sm"
                title="Connected to PassKhadam Cloud Staging (Ethereum Sepolia & IPFS)"
              >
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="font-mono text-[11px] font-medium text-slate-200">Cloud Staging • Sepolia</span>
              </div>

              {/* Language Selector Dropdown */}
              <div className="relative">
                <button
                  onClick={() => setLangDropdownOpen(!langDropdownOpen)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 text-slate-200 transition"
                >
                  <Globe className="w-3.5 h-3.5 text-blue-400" />
                  <span className="text-[11px] font-medium">{currentLangObj.flag} {currentLangObj.native}</span>
                  <ChevronDown className="w-3 h-3 text-slate-400" />
                </button>

                {langDropdownOpen && (
                  <div className="absolute right-0 mt-1.5 w-36 bg-slate-900 border border-slate-800 rounded-xl shadow-xl overflow-hidden z-50 py-1">
                    {languages.map((l) => (
                      <button
                        key={l.code}
                        onClick={() => {
                          onLangChange(l.code);
                          setLangDropdownOpen(false);
                        }}
                        className={`w-full px-3 py-1.5 text-left text-xs flex items-center justify-between hover:bg-slate-800 transition ${
                          currentLang === l.code ? 'bg-blue-600/20 text-blue-300 font-semibold' : 'text-slate-300'
                        }`}
                      >
                        <span>{l.flag} {l.native}</span>
                        <span className="text-[10px] text-slate-500 font-mono uppercase">{l.code}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* User Authentication Pill / Login Button */}
              {currentUser ? (
                <div className="flex items-center gap-2 pl-1 border-l border-slate-800">
                  {currentUser.is_demo && false && (
                    <span
                      className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-semibold tracking-wider hidden"
                      title="Operating with Demo Principal"
                    >
                      <ShieldAlert className="w-3 h-3 text-amber-400" />
                      DEMO MODE
                    </span>
                  )}
                  <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1 rounded-xl border border-slate-800">
                    <User className="w-3 h-3 text-emerald-400" />
                    <span className="text-[11px] text-slate-300 font-medium max-w-[110px] truncate">
                      {currentUser.full_name?.split(' ')[0]}
                    </span>
                    <span className="text-[9px] px-1 rounded bg-blue-500/20 text-blue-300 font-mono font-semibold">
                      {currentUser.role}
                    </span>
                  </div>
                  <button
                    onClick={logout}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition"
                    title={getTranslation(currentLang, 'logout')}
                  >
                    <LogOut className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setIsAuthOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium transition shadow-sm"
                >
                  <LogIn className="w-3.5 h-3.5" />
                  <span>{getTranslation(currentLang, 'login')}</span>
                </button>
              )}

            </div>

          </div>

          {/* Active Roles Navigation Bar (De-demonized in production; not rendered in active UI) */}
          {false && (
            <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center space-x-1 sm:space-x-2 overflow-x-auto pb-1 hidden">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 mr-2 flex items-center">
                {getTranslation(currentLang, 'activeRole')}:
              </span>
              {roles.map((r) => {
                const Icon = r.icon;
                const active = currentRole === r.id;
                return (
                  <button
                    key={r.id}
                    onClick={() => handleRoleClick(r.id)}
                    className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                      active
                        ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30 font-semibold'
                        : 'bg-slate-800/50 hover:bg-slate-800 text-slate-300 border border-slate-700/50'
                    }`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${active ? 'text-white' : r.color}`} />
                    <span>{getTranslation(currentLang, r.key)}</span>
                  </button>
                );
              })}
            </div>
          )}

        </div>
      </header>

      {/* Global Modals */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => {
          setIsAuthOpen(false);
          setAuthInitialToken('');
          setAuthInitialTab('login');
        }}
        onRoleSelect={(role) => onRoleChange(role)}
        initialTab={authInitialTab}
        initialToken={authInitialToken}
      />
      <Web3WalletModal
        isOpen={isWalletOpen}
        onClose={() => setIsWalletOpen(false)}
      />
      <NetworkSettingsModal
        isOpen={isNetworkOpen}
        onClose={() => setIsNetworkOpen(false)}
      />
    </>
  );
}
