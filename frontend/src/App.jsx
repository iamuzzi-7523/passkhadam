import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Web3Provider } from './context/Web3Context';
import Header from './components/common/Header';
import RoleGuard from './components/common/RoleGuard';
import AuthPage from './components/common/AuthPage';
import WorkerPortal from './components/worker/WorkerPortal';
import EmployerPortal from './components/employer/EmployerPortal';
import GovernmentPortal from './components/government/GovernmentPortal';
import AdminPortal from './components/admin/AdminPortal';
import AadhaarPortal from './components/aadhaar/AadhaarPortal';

function MainApp() {
  const { currentUser, configError } = useAuth();
  const [currentRole, setCurrentRole] = useState('WORKER');
  const [currentLang, setCurrentLang] = useState('en');

  // Automatically route authenticated user to their provisioned role workspace
  useEffect(() => {
    if (currentUser?.role) {
      setCurrentRole(currentUser.role);
    }
  }, [currentUser?.role]);

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-blue-600 selection:text-white">
      {/* Cloud Desktop Configuration Error Alert Banner */}
      {configError && (
        <div className="bg-red-950/70 border-b border-red-500/40 px-4 py-3 text-xs text-red-200">
          <div className="max-w-[1600px] mx-auto flex items-start space-x-2.5">
            <span className="text-base leading-none">⚠️</span>
            <div>
              <strong className="font-semibold text-red-100 block">Cloud Desktop Configuration Error:</strong>
              <span className="text-red-300 leading-relaxed block">{configError}</span>
              <span className="text-[11px] text-red-400 mt-0.5 block">
                Place a <code>config.json</code> file containing <code>&#123;&quot;apiUrl&quot;: &quot;https://your-backend.onrender.com&quot;&#125;</code> in the application directory.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Header with Live MetaMask Wallet, Network & Multilingual Controls */}
      <Header
        currentRole={currentRole}
        onRoleChange={setCurrentRole}
        currentLang={currentLang}
        onLangChange={setCurrentLang}
      />

      {/* Main Content Area: Default Unauthenticated Authentication Page or Authenticated Workspace */}
      <main className="flex-1 w-full max-w-[1600px] mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6">
        {!currentUser ? (
          <AuthPage
            currentLang={currentLang}
            onRoleSelect={(role) => setCurrentRole(role)}
          />
        ) : (
          <>
            {currentRole === 'WORKER' && (
              <RoleGuard requiredRole="WORKER">
                <WorkerPortal currentLang={currentLang} />
              </RoleGuard>
            )}
            {currentRole === 'EMPLOYER' && (
              <RoleGuard requiredRole="EMPLOYER">
                <EmployerPortal currentLang={currentLang} />
              </RoleGuard>
            )}
            {currentRole === 'GOVERNMENT' && (
              <RoleGuard requiredRole="GOVERNMENT">
                <GovernmentPortal currentLang={currentLang} />
              </RoleGuard>
            )}
            {currentRole === 'ADMIN' && (
              <RoleGuard requiredRole="ADMIN">
                <AdminPortal currentLang={currentLang} />
              </RoleGuard>
            )}
            {currentRole === 'AADHAAR' && (
              <RoleGuard requiredRole="AADHAAR">
                <AadhaarPortal currentLang={currentLang} />
              </RoleGuard>
            )}
          </>
        )}
      </main>

      {/* Responsive Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/60 py-4 text-xs text-slate-500">
        <div className="w-full max-w-[1600px] mx-auto px-3 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
          <p>
            <strong>PASSKHADAM</strong> — Decentralized Portable Identity Platform for Migrant Workers.
          </p>
          <p className="font-mono text-[11px] text-slate-400">
            EVM Blockchain • W3C Verifiable Credentials • AES-256 IPFS • Web QR Upload • Zero Camera Required
          </p>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Web3Provider>
        <MainApp />
      </Web3Provider>
    </AuthProvider>
  );
}
