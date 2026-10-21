import React, { useState, useEffect } from 'react';
import { 
  Fingerprint, Activity, CheckCircle, XCircle, Clock, 
  Search, ShieldAlert, RefreshCw, Send, Database, PlusCircle, 
  Edit, CheckCircle2, AlertTriangle, ShieldCheck, Filter, 
  UserPlus, UserCheck, Lock, ExternalLink
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { apiFetch, formatMaskedAadhaar } from '../../utils/api';

export default function AadhaarPortal({ currentLang = 'en' }) {
  const { currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState('REGISTRY'); // 'REGISTRY' | 'SANDBOX' | 'LOGS'

  // Global Alerts & Loading
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Dashboard Stats
  const [dashboard, setDashboard] = useState(null);

  // Tab 1: Demographic Registry
  const [records, setRecords] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState(null);

  // Create Form State
  const [newAadhaar, setNewAadhaar] = useState('');
  const [newName, setNewName] = useState('');
  const [newDob, setNewDob] = useState('1994-06-15');
  const [newGender, setNewGender] = useState('Male');
  const [newState, setNewState] = useState('Bihar');
  const [newAddress, setNewAddress] = useState('Village Nawada, Dist Gaya, Bihar');
  const [newStatus, setNewStatus] = useState('ACTIVE');

  // Edit Form State
  const [editName, setEditName] = useState('');
  const [editDob, setEditDob] = useState('');
  const [editGender, setEditGender] = useState('Male');
  const [editState, setEditState] = useState('');
  const [editAddress, setEditAddress] = useState('');
  const [editStatus, setEditStatus] = useState('ACTIVE');

  // Tab 2: Verification Sandbox
  const [testAadhaar, setTestAadhaar] = useState('123456784821');
  const [testName, setTestName] = useState('Mohammed Uzair');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  // Tab 3: DBAadhaarAuditLog
  const [auditLogs, setAuditLogs] = useState([]);
  const [logResultFilter, setLogResultFilter] = useState('ALL');
  const [logSearchQuery, setLogSearchQuery] = useState('');

  // ==========================================
  // Data Loaders
  // ==========================================

  const fetchDashboard = async () => {
    try {
      const res = await apiFetch('/api/v1/aadhaar/dashboard');
      if (res.ok) {
        const data = await res.json();
        setDashboard(data);
      }
    } catch (e) {
      console.error('Failed to load Aadhaar dashboard metrics:', e);
    }
  };

  const fetchRecords = async () => {
    try {
      setLoading(true);
      let url = '/api/v1/aadhaar/records?limit=100';
      if (searchQuery.trim()) url += `&query=${encodeURIComponent(searchQuery.trim())}`;
      if (statusFilter !== 'ALL') url += `&status=${statusFilter}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        setRecords(data);
      }
    } catch (e) {
      console.error('Failed to load demographic records:', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchAuditLogs = async () => {
    try {
      let url = '/api/v1/aadhaar/logs?limit=100';
      if (logResultFilter !== 'ALL') url += `&result_code=${logResultFilter}`;
      if (logSearchQuery.trim()) url += `&masked_aadhaar=${encodeURIComponent(logSearchQuery.trim())}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data);
      }
    } catch (e) {
      console.error('Failed to load Aadhaar audit logs:', e);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  useEffect(() => {
    if (activeTab === 'REGISTRY') fetchRecords();
    else if (activeTab === 'LOGS') fetchAuditLogs();
  }, [activeTab, statusFilter, logResultFilter]);

  // ==========================================
  // Tab 1 CRUD Handlers
  // ==========================================

  const handleCreateRecord = async (e) => {
    e.preventDefault();
    const cleanNum = newAadhaar.replace(/\s+/g, '');
    if (!/^\d{12}$/.test(cleanNum)) {
      alert('Aadhaar number must contain exactly 12 numeric digits.');
      return;
    }

    try {
      setLoading(true);
      setErrorMsg('');
      setActionMsg('');
      const res = await apiFetch('/api/v1/aadhaar/records', {
        method: 'POST',
        body: {
          aadhaar_number: cleanNum,
          full_name: newName,
          dob: newDob,
          gender: newGender,
          origin_state: newState,
          address: newAddress,
          status: newStatus
        }
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          throw new Error('409 Conflict: An Aadhaar record with this 12-digit number already exists.');
        }
        throw new Error(data.detail || 'Failed to create demographic record');
      }

      setActionMsg(`Demographic record created successfully for ${data.full_name} (${formatMaskedAadhaar(data.masked_aadhaar)})`);
      setCreateModalOpen(false);
      setNewAadhaar('');
      setNewName('');
      await fetchRecords();
      await fetchDashboard();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenEdit = (rec) => {
    setSelectedRecord(rec);
    setEditName(rec.full_name || '');
    setEditDob(rec.dob || '');
    setEditGender(rec.gender || 'Male');
    setEditState(rec.origin_state || '');
    setEditAddress(rec.address || '');
    setEditStatus(rec.status || 'ACTIVE');
    setEditModalOpen(true);
  };

  const submitEditRecord = async (e) => {
    e.preventDefault();
    if (!selectedRecord) return;

    try {
      setLoading(true);
      setErrorMsg('');
      setActionMsg('');
      // URL PRIVACY BOUNDARY: strictly use surrogate UUID record_id in path
      const res = await apiFetch(`/api/v1/aadhaar/records/${selectedRecord.record_id}`, {
        method: 'PUT',
        body: {
          full_name: editName,
          dob: editDob,
          gender: editGender,
          origin_state: editState,
          address: editAddress,
          status: editStatus
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to update record');

      setActionMsg(`Record updated for ${data.full_name} (${formatMaskedAadhaar(data.masked_aadhaar)})`);
      setEditModalOpen(false);
      await fetchRecords();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStatus = async (recordId, newStatusVal) => {
    try {
      setLoading(true);
      setErrorMsg('');
      // URL PRIVACY BOUNDARY: strictly use surrogate UUID record_id in path
      const res = await apiFetch(`/api/v1/aadhaar/records/${recordId}/status`, {
        method: 'PUT',
        body: { status: newStatusVal }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to update status');

      setActionMsg(`Record status updated to ${data.status}`);
      await fetchRecords();
      await fetchDashboard();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // Tab 2 Sandbox Handler
  // ==========================================

  const handleTestVerify = async (e) => {
    e.preventDefault();
    setTesting(true);
    setTestResult(null);
    setErrorMsg('');

    try {
      const res = await apiFetch('/api/v1/aadhaar/test-verify', {
        method: 'POST',
        body: {
          aadhaar_number: testAadhaar.replace(/\s+/g, ''),
          full_name: testName
        }
      });
      const data = await res.json();
      setTestResult(data);
      await fetchDashboard();
    } catch (e) {
      setErrorMsg(e.message || 'Verification test failed');
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Identity Authority Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-rose-600/15 border border-rose-500/30 text-rose-400 flex items-center justify-center text-2xl font-bold">
              🆔
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">Mock Aadhaar Authority / Identity Center</h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1 font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span>ONLINE (v0.4 Gateway)</span>
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Simulated Government Identity Service. All raw 12-digit Aadhaar numbers are hashed with SHA-256 and never stored plaintext.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                fetchDashboard();
                if (activeTab === 'REGISTRY') fetchRecords();
                else if (activeTab === 'LOGS') fetchAuditLogs();
              }}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 flex items-center gap-1.5 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh Metrics</span>
            </button>
          </div>
        </div>

        {/* Authority Metrics KPI Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-slate-800 text-xs">
          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Total Records</span>
            <span className="text-base font-bold text-white font-mono mt-0.5 block">
              {dashboard?.total_records || records.length || 0}
            </span>
          </div>
          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Active Identities</span>
            <span className="text-base font-bold text-emerald-400 font-mono mt-0.5 block">
              {dashboard?.active_records || 0}
            </span>
          </div>
          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Verifications (24h)</span>
            <span className="text-base font-bold text-blue-400 font-mono mt-0.5 block">
              {dashboard?.verifications_today || 0}
            </span>
          </div>
          <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
            <span className="text-[10px] text-slate-400 block uppercase font-semibold">Match Success Rate</span>
            <span className="text-base font-bold text-purple-400 font-mono mt-0.5 block">
              {dashboard?.success_rate || '100%'}
            </span>
          </div>
        </div>

        {/* 3-Tab Navigation Bar */}
        <div className="mt-5 pt-3 border-t border-slate-800 flex items-center gap-2 overflow-x-auto text-xs font-medium">
          <button
            onClick={() => setActiveTab('REGISTRY')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl transition ${
              activeTab === 'REGISTRY'
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            <span>Demographic Registry &amp; CRUD</span>
          </button>

          <button
            onClick={() => setActiveTab('SANDBOX')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl transition ${
              activeTab === 'SANDBOX'
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <Fingerprint className="w-3.5 h-3.5" />
            <span>Verification Sandbox</span>
          </button>

          <button
            onClick={() => setActiveTab('LOGS')}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl transition ${
              activeTab === 'LOGS'
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>DBAadhaarAuditLog Stream</span>
          </button>
        </div>
      </div>

      {/* Global Alerts */}
      {actionMsg && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{actionMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* ============================================================
          TAB 1: DEMOGRAPHIC REGISTRY & CRUD
      ============================================================ */}
      {activeTab === 'REGISTRY' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-white">Demographic Registry</h3>
              <p className="text-xs text-slate-400">Manage government identity records with strict UUID privacy boundaries and masked displays.</p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && fetchRecords()}
                  placeholder="Search name or masked #..."
                  className="pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white outline-none w-48"
                />
              </div>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 outline-none"
              >
                <option value="ALL">All Statuses</option>
                <option value="ACTIVE">ACTIVE</option>
                <option value="INACTIVE">INACTIVE</option>
                <option value="SUSPENDED">SUSPENDED</option>
              </select>

              <button
                onClick={() => setCreateModalOpen(true)}
                className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-rose-600/20 flex items-center gap-1.5 transition"
              >
                <PlusCircle className="w-3.5 h-3.5" />
                <span>Add Record</span>
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                <tr>
                  <th className="py-3 px-3">Masked Aadhaar</th>
                  <th className="py-3 px-3">Citizen Name &amp; Gender</th>
                  <th className="py-3 px-3">DOB &amp; State</th>
                  <th className="py-3 px-3">Surrogate UUID (record_id)</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {records.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500 italic font-sans">
                      No demographic records found.
                    </td>
                  </tr>
                ) : (
                  records.map((r) => (
                    <tr key={r.record_id || r.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3 px-3 font-bold text-white tracking-wider">
                        {formatMaskedAadhaar(r.masked_aadhaar)}
                      </td>
                      <td className="py-3 px-3 font-sans">
                        <div className="font-semibold text-white">{r.full_name}</div>
                        <div className="text-[10px] text-slate-400">{r.gender || 'Not Specified'}</div>
                      </td>
                      <td className="py-3 px-3 font-sans text-slate-300">
                        <div>{r.origin_state}</div>
                        <div className="text-[10px] text-slate-500 font-mono">{r.dob || 'N/A'}</div>
                      </td>
                      <td className="py-3 px-3 text-slate-400 max-w-[140px] truncate" title={r.record_id}>
                        {r.record_id}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          r.status === 'ACTIVE' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' :
                          r.status === 'SUSPENDED' ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30' :
                          'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right font-sans">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleOpenEdit(r)}
                            className="p-1 rounded bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700"
                            title="Edit record demographics"
                          >
                            <Edit className="w-3.5 h-3.5" />
                          </button>
                          {r.status === 'ACTIVE' ? (
                            <button
                              onClick={() => handleToggleStatus(r.record_id, 'SUSPENDED')}
                              className="px-2 py-0.5 rounded bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 text-[10px] font-semibold"
                            >
                              Suspend
                            </button>
                          ) : (
                            <button
                              onClick={() => handleToggleStatus(r.record_id, 'ACTIVE')}
                              className="px-2 py-0.5 rounded bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-[10px] font-semibold"
                            >
                              Activate
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ============================================================
          TAB 2: VERIFICATION SANDBOX
      ============================================================ */}
      {activeTab === 'SANDBOX' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Fingerprint className="w-5 h-5 text-rose-400" />
                <span>Demographic Verification Sandbox</span>
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Test UIDAI biometric/demographic 1:1 match logic. Checks submitted Aadhaar against registered records.
              </p>
            </div>

            <form onSubmit={handleTestVerify} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">Aadhaar Number (12 Digits)</label>
                <input
                  type="text"
                  value={testAadhaar}
                  onChange={(e) => setTestAadhaar(e.target.value)}
                  placeholder="123456784821"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white font-mono outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Full Name</label>
                <input
                  type="text"
                  value={testName}
                  onChange={(e) => setTestName(e.target.value)}
                  placeholder="Mohammed Uzair"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div className="flex items-center gap-2 pt-1 text-[11px]">
                <span className="text-slate-500">Presets:</span>
                <button
                  type="button"
                  onClick={() => { setTestAadhaar('123456784821'); setTestName('Mohammed Uzair'); }}
                  className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700"
                >
                  Mohammed Uzair (Valid)
                </button>
                <button
                  type="button"
                  onClick={() => { setTestAadhaar('987654321098'); setTestName('Ramesh Kumar Verma'); }}
                  className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700"
                >
                  Ramesh Verma (Valid)
                </button>
              </div>

              <button
                type="submit"
                disabled={testing}
                className="w-full py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-bold text-xs transition shadow-md shadow-rose-600/20 flex items-center justify-center gap-2"
              >
                <Send className={`w-3.5 h-3.5 ${testing ? 'animate-pulse' : ''}`} />
                <span>{testing ? 'Verifying with Mock Gateway...' : 'Execute Test Verification'}</span>
              </button>
            </form>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-400" />
              <span>Gateway Response Output</span>
            </h3>

            {testResult ? (
              <div className="space-y-3 text-xs">
                <div className={`p-4 rounded-xl border flex items-center justify-between ${
                  testResult.verified 
                    ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300' 
                    : 'bg-rose-950/30 border-rose-500/40 text-rose-300'
                }`}>
                  <div className="flex items-center gap-2">
                    {testResult.verified ? <CheckCircle2 className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
                    <div>
                      <span className="font-bold text-sm block">
                        {testResult.verified ? 'Verification PASSED (100% Match)' : 'Verification FAILED'}
                      </span>
                      <span className="text-[11px] opacity-80">{testResult.message}</span>
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded font-mono text-[11px] font-bold bg-slate-950/80">
                    {testResult.result_code}
                  </span>
                </div>

                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1.5 font-mono text-[11px]">
                  <div className="flex justify-between text-slate-400">
                    <span>Masked Aadhaar:</span>
                    <span className="text-white font-bold">{formatMaskedAadhaar(testResult.masked_aadhaar)}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Aadhaar Hash:</span>
                    <span className="text-slate-300 truncate max-w-[200px]">{testResult.aadhaar_hash}</span>
                  </div>
                  {testResult.origin_state && (
                    <div className="flex justify-between text-slate-400">
                      <span>Origin State:</span>
                      <span className="text-blue-300">{testResult.origin_state}</span>
                    </div>
                  )}
                  {testResult.gender && (
                    <div className="flex justify-between text-slate-400">
                      <span>Gender:</span>
                      <span className="text-slate-300">{testResult.gender}</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-slate-500 space-y-2">
                <Fingerprint className="w-10 h-10 mx-auto text-slate-700" />
                <p className="text-xs">Submit a verification query on the left to inspect raw gateway telemetry.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============================================================
          TAB 3: DBAADHAARAUDITLOG STREAM
      ============================================================ */}
      {activeTab === 'LOGS' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-white">DBAadhaarAuditLog Stream</h3>
              <p className="text-xs text-slate-400">Immutable audit records logged for every government identity verification request.</p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={logSearchQuery}
                onChange={(e) => setLogSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchAuditLogs()}
                placeholder="Search masked Aadhaar..."
                className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white outline-none w-48 font-mono"
              />

              <select
                value={logResultFilter}
                onChange={(e) => setLogResultFilter(e.target.value)}
                className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 outline-none"
              >
                <option value="ALL">All Results</option>
                <option value="SUCCESS">SUCCESS</option>
                <option value="DEMOGRAPHIC_MISMATCH">DEMOGRAPHIC_MISMATCH</option>
                <option value="NOT_FOUND">NOT_FOUND</option>
                <option value="INACTIVE_RECORD">INACTIVE_RECORD</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                <tr>
                  <th className="py-3 px-3">Log ID</th>
                  <th className="py-3 px-3">Timestamp</th>
                  <th className="py-3 px-3">Masked Aadhaar</th>
                  <th className="py-3 px-3">Result Code</th>
                  <th className="py-3 px-3">Caller Identity / Service</th>
                  <th className="py-3 px-3 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500 italic font-sans">
                      No Aadhaar audit logs recorded matching criteria.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map(l => (
                    <tr key={l.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3 px-3 text-slate-500">#{l.id}</td>
                      <td className="py-3 px-3 text-slate-400">
                        {l.timestamp ? new Date(l.timestamp).toLocaleString() : 'N/A'}
                      </td>
                      <td className="py-3 px-3 font-bold text-white tracking-wider">
                        {formatMaskedAadhaar(l.masked_aadhaar)}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          l.result_code === 'SUCCESS' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' :
                          l.result_code === 'DEMOGRAPHIC_MISMATCH' ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' :
                          'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                        }`}>
                          {l.result_code}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-300 font-sans">
                        {l.caller_id || l.service_name || 'PassKhadam Worker Service'}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-400 font-sans">
                        {l.detail || 'Verified against mock biometric registry'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ============================================================
          MODALS
      ============================================================ */}

      {/* Add Demographic Record Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-rose-400" />
                <h3 className="font-bold text-white text-base">Add Demographic Record</h3>
              </div>
              <button onClick={() => setCreateModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleCreateRecord} className="space-y-3">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">Raw 12-Digit Aadhaar *</label>
                <input
                  type="text"
                  maxLength={12}
                  value={newAadhaar}
                  onChange={(e) => setNewAadhaar(e.target.value.replace(/\D/g, ''))}
                  placeholder="e.g. 556677889900"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white font-mono tracking-wider outline-none"
                  required
                />
                <span className="text-[10px] text-slate-500 mt-0.5 block">
                  Raw number is hashed with SHA-256 upon submission; never stored plaintext.
                </span>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Full Legal Name *</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Sunita Devi"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Date of Birth</label>
                  <input
                    type="date"
                    value={newDob}
                    onChange={(e) => setNewDob(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Gender</label>
                  <select
                    value={newGender}
                    onChange={(e) => setNewGender(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Origin State *</label>
                  <input
                    type="text"
                    value={newState}
                    onChange={(e) => setNewState(e.target.value)}
                    placeholder="e.g. Bihar"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Initial Status</label>
                  <select
                    value={newStatus}
                    onChange={(e) => setNewStatus(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  >
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="INACTIVE">INACTIVE</option>
                    <option value="SUSPENDED">SUSPENDED</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Registered Address</label>
                <input
                  type="text"
                  value={newAddress}
                  onChange={(e) => setNewAddress(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-bold transition shadow-md shadow-rose-600/20"
                >
                  Add Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Demographic Record Modal */}
      {editModalOpen && selectedRecord && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Edit Demographic Record</h3>
              <button onClick={() => setEditModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={submitEditRecord} className="space-y-3">
              <div>
                <span className="text-slate-400">Masked Identifier:</span>
                <div className="font-bold text-white text-sm font-mono">
                  {formatMaskedAadhaar(selectedRecord.masked_aadhaar)}
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  UUID: {selectedRecord.record_id}
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Full Legal Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Date of Birth</label>
                  <input
                    type="date"
                    value={editDob}
                    onChange={(e) => setEditDob(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Gender</label>
                  <select
                    value={editGender}
                    onChange={(e) => setEditGender(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Origin State</label>
                  <input
                    type="text"
                    value={editState}
                    onChange={(e) => setEditState(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Status</label>
                  <select
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  >
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="INACTIVE">INACTIVE</option>
                    <option value="SUSPENDED">SUSPENDED</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Address</label>
                <input
                  type="text"
                  value={editAddress}
                  onChange={(e) => setEditAddress(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold transition"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
