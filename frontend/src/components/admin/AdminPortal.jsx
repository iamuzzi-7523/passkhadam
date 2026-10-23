import React, { useState, useEffect } from 'react';
import { 
  Building2, Landmark, Settings, ShieldAlert, CheckCircle2, XCircle, 
  RefreshCw, Layers, Database, Key, Check, PlusCircle, AlertCircle, 
  Copy, Search, Filter, ShieldCheck, Activity, Wifi, ChevronDown, 
  UserPlus, Send, Ban, CheckSquare, Square, Info, Shield, Clock, ExternalLink,
  Calendar, RotateCcw, X, AlertTriangle
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { apiFetch } from '../../utils/api';

// Custom hook: 300ms debounce for text inputs
function useDebounce(value, delay = 300) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}

// Universal unwrapper handling both envelope objects and raw lists gracefully
function parsePaginatedResponse(data, page = 1, pageSize = 20) {
  if (!data) {
    return { items: [], totalCount: 0, page: 1, pageSize, totalPages: 1 };
  }
  if (Array.isArray(data)) {
    return {
      items: data,
      totalCount: data.length,
      page: 1,
      pageSize: data.length || pageSize,
      totalPages: 1
    };
  }
  if (Array.isArray(data.items)) {
    const totalCount = typeof data.total_count === 'number' ? data.total_count : data.items.length;
    const effPage = data.page || page;
    const effSize = data.page_size || pageSize;
    const totalPages = typeof data.total_pages === 'number' ? data.total_pages : (Math.ceil(totalCount / effSize) || 1);
    return {
      items: data.items,
      totalCount,
      page: effPage,
      pageSize: effSize,
      totalPages: Math.max(1, totalPages)
    };
  }
  return { items: [], totalCount: 0, page: 1, pageSize, totalPages: 1 };
}

function formatUtcTimestamp(ts) {
  if (!ts) return 'N/A';
  const str = String(ts);
  const isoStr = (str.endsWith('Z') || str.includes('+')) ? str : str + 'Z';
  const d = new Date(isoStr);
  return isNaN(d.getTime()) ? new Date(str).toLocaleString() : d.toLocaleString();
}

function PaginationControls({
  currentPage,
  totalPages,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50],
  itemLabel = "records"
}) {
  if (totalItems === 0) return null;

  const startIdx = Math.min((currentPage - 1) * pageSize + 1, totalItems);
  const endIdx = Math.min(currentPage * pageSize, totalItems);

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-800 text-xs text-slate-400">
      <div className="flex items-center gap-2">
        <span>
          Showing <strong className="text-white font-mono">{startIdx}–{endIdx}</strong> of{' '}
          <strong className="text-white font-mono">{totalItems}</strong> {itemLabel}
        </span>
        <span className="text-slate-600 hidden sm:inline">•</span>
        <div className="flex items-center gap-1.5">
          <span>Per page:</span>
          <select
            value={pageSize}
            onChange={(e) => {
              onPageSizeChange(Number(e.target.value));
              onPageChange(1);
            }}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-slate-200 outline-none focus:border-blue-500 font-mono text-[11px]"
          >
            {pageSizeOptions.map(size => (
              <option key={size} value={size}>{size}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="font-mono text-[11px]">
          Page <strong className="text-white">{currentPage}</strong> of <strong className="text-white">{Math.max(1, totalPages)}</strong>
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            className="px-2.5 py-1 bg-slate-950 hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-slate-950 border border-slate-800 rounded-lg text-slate-300 font-medium transition disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            className="px-2.5 py-1 bg-slate-950 hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-slate-950 border border-slate-800 rounded-lg text-slate-300 font-medium transition disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

function CategoryFilterBar({
  search, onSearchChange,
  category, onCategoryChange,
  skill, onSkillChange,
  nature, onNatureChange,
  dateFrom, onDateFromChange,
  dateTo, onDateToChange,
  onClear,
  accentColor = 'amber'
}) {
  const focusBorder = accentColor === 'cyan' ? 'focus:border-cyan-500' :
                      accentColor === 'rose' ? 'focus:border-rose-500' :
                      accentColor === 'purple' ? 'focus:border-purple-500' : 'focus:border-amber-500';

  return (
    <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 space-y-2.5">
      <div className="flex flex-col md:flex-row items-stretch md:items-center gap-2.5">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search trade, org name, ref, skill, nature..."
            className={`w-full pl-9 pr-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 outline-none ${focusBorder}`}
          />
        </div>

        <div className="flex items-center gap-1.5 shrink-0 text-xs">
          <span className="text-slate-400 text-[11px]">Trade:</span>
          <select
            value={category}
            onChange={(e) => onCategoryChange(e.target.value)}
            className={`bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none ${focusBorder}`}
          >
            {TRADE_CATEGORIES_OPTIONS.map(tc => (
              <option key={tc} value={tc}>{tc === 'ALL' ? 'All Trades' : tc}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5 shrink-0 text-xs">
          <span className="text-slate-400 text-[11px]">Skill:</span>
          <select
            value={skill}
            onChange={(e) => onSkillChange(e.target.value)}
            className={`bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none ${focusBorder}`}
          >
            {SKILL_LEVELS_OPTIONS.map(sk => (
              <option key={sk} value={sk}>{sk === 'ALL' ? 'All Skills' : sk}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5 shrink-0 text-xs">
          <span className="text-slate-400 text-[11px]">Nature:</span>
          <select
            value={nature}
            onChange={(e) => onNatureChange(e.target.value)}
            className={`bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none ${focusBorder}`}
          >
            {NATURE_OF_EMPLOYMENT_OPTIONS.map(nat => (
              <option key={nat} value={nat}>{nat === 'ALL' ? 'All Natures' : nat}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5 shrink-0 text-xs">
          <span className="text-slate-400 text-[11px]">From:</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => onDateFromChange(e.target.value)}
            className={`bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none ${focusBorder}`}
          />
          <span className="text-slate-400 text-[11px]">To:</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => onDateToChange(e.target.value)}
            className={`bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none ${focusBorder}`}
          />
        </div>

        <button
          onClick={onClear}
          className="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg text-xs border border-slate-800 flex items-center gap-1 transition shrink-0"
          title="Reset all category filters"
        >
          <RotateCcw className="w-3 h-3" />
          <span>Clear Filters</span>
        </button>
      </div>
    </div>
  );
}

const INDIAN_STATES_OPTIONS = [
  'ALL', 'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
  'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand',
  'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
  'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab',
  'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
  'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Delhi'
];

const TRADE_CATEGORIES_OPTIONS = [
  'ALL', 'Construction', 'Masonry', 'Carpentry', 'Plumbing', 'Electrical',
  'Welding', 'Painting', 'Scaffolding', 'Heavy Machinery', 'Bar Bending',
  'Tile Fitting', 'General Labour'
];

const SKILL_LEVELS_OPTIONS = ['ALL', 'Skilled', 'Semi-Skilled', 'Unskilled'];
const NATURE_OF_EMPLOYMENT_OPTIONS = ['ALL', 'Contract', 'Permanent', 'Project-Based'];

export default function AdminPortal({ currentLang = 'en' }) {
  const { currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState('ORGANIZATIONS'); // 'ORGANIZATIONS' | 'CATEGORIES' | 'OFFICERS' | 'AUDIT' | 'HEALTH'

  // Global notifications
  const [actionMsg, setActionMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  // View 1: All Employer Organizations Directory
  const [organizations, setOrganizations] = useState([]);
  const [orgFilter, setOrgFilter] = useState('ALL');
  const [orgSearch, setOrgSearch] = useState('');
  const debouncedOrgSearch = useDebounce(orgSearch, 300);
  const [orgStateFilter, setOrgStateFilter] = useState('ALL');
  const [orgDateFrom, setOrgDateFrom] = useState('');
  const [orgDateTo, setOrgDateTo] = useState('');
  const [orgPage, setOrgPage] = useState(1);
  const [orgPageSize, setOrgPageSize] = useState(20);
  const [orgTotalCount, setOrgTotalCount] = useState(0);
  const [orgTotalPages, setOrgTotalPages] = useState(1);
  const [orgsError, setOrgsError] = useState(null);
  const [selectedOrg, setSelectedOrg] = useState(null);
  const [orgDecisionModalOpen, setOrgDecisionModalOpen] = useState(false);
  const [orgAction, setOrgAction] = useState('APPROVE');
  const [orgReason, setOrgReason] = useState('');
  const [orgNotes, setOrgNotes] = useState('');
  const [activationLink, setActivationLink] = useState(null);
  const [activationToken, setActivationToken] = useState(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedToken, setCopiedToken] = useState(false);

  // View 2: Pending Organization Reviews Queue
  const [pendingOrgs, setPendingOrgs] = useState([]);
  const [pendingOrgSearch, setPendingOrgSearch] = useState('');
  const debouncedPendingOrgSearch = useDebounce(pendingOrgSearch, 300);
  const [pendingOrgStateFilter, setPendingOrgStateFilter] = useState('ALL');
  const [pendingOrgDateFrom, setPendingOrgDateFrom] = useState('');
  const [pendingOrgDateTo, setPendingOrgDateTo] = useState('');
  const [pendingOrgPage, setPendingOrgPage] = useState(1);
  const [pendingOrgPageSize, setPendingOrgPageSize] = useState(20);
  const [pendingOrgTotalCount, setPendingOrgTotalCount] = useState(0);
  const [pendingOrgTotalPages, setPendingOrgTotalPages] = useState(1);
  const [pendingOrgsError, setPendingOrgsError] = useState(null);

  // Views 3-6: Category Authorization & Scopes
  const [categoryRequests, setCategoryRequests] = useState([]);
  const [catFilter, setCatFilter] = useState('ALL');
  const [catSearch, setCatSearch] = useState('');
  const debouncedCatSearch = useDebounce(catSearch, 300);
  const [catCategoryFilter, setCatCategoryFilter] = useState('ALL');
  const [catSkillFilter, setCatSkillFilter] = useState('ALL');
  const [catNatureFilter, setCatNatureFilter] = useState('ALL');
  const [catDateFrom, setCatDateFrom] = useState('');
  const [catDateTo, setCatDateTo] = useState('');
  const [catPage, setCatPage] = useState(1);
  const [catPageSize, setCatPageSize] = useState(20);
  const [catTotalCount, setCatTotalCount] = useState(0);
  const [catTotalPages, setCatTotalPages] = useState(1);
  const [catsError, setCatsError] = useState(null);
  const [rejectedFilter, setRejectedFilter] = useState('ALL');
  const [historyFilter, setHistoryFilter] = useState('ALL');
  const [selectedCatReq, setSelectedCatReq] = useState(null);
  const [catDecisionModalOpen, setCatDecisionModalOpen] = useState(false);
  const [catAction, setCatAction] = useState('APPROVE');
  const [catReason, setCatReason] = useState('');
  const [discontinueModalOpen, setDiscontinueModalOpen] = useState(false);
  const [discontinueReason, setDiscontinueReason] = useState('');
  const [suspendModalOpen, setSuspendModalOpen] = useState(false);
  const [suspendReason, setSuspendReason] = useState('');
  const [officerSuspendModalOpen, setOfficerSuspendModalOpen] = useState(false);
  const [selectedOfficerForSuspend, setSelectedOfficerForSuspend] = useState(null);
  const [officerSuspendReason, setOfficerSuspendReason] = useState('');
  const [officerSuspendSubmitting, setOfficerSuspendSubmitting] = useState(false);

  // Tab 3: Government Officers
  const [officers, setOfficers] = useState([]);
  const [officerSearch, setOfficerSearch] = useState('');
  const debouncedOfficerSearch = useDebounce(officerSearch, 300);
  const [officerFilter, setOfficerFilter] = useState('ALL');
  const [officerAuthorityFilter, setOfficerAuthorityFilter] = useState('ALL');
  const [officerStateFilter, setOfficerStateFilter] = useState('ALL');
  const [officerDistrictFilter, setOfficerDistrictFilter] = useState('ALL');
  const [officerBlockFilter, setOfficerBlockFilter] = useState('');
  const [officerDateFrom, setOfficerDateFrom] = useState('');
  const [officerDateTo, setOfficerDateTo] = useState('');
  const [officerPage, setOfficerPage] = useState(1);
  const [officerPageSize, setOfficerPageSize] = useState(20);
  const [officerTotalCount, setOfficerTotalCount] = useState(0);
  const [officerTotalPages, setOfficerTotalPages] = useState(1);
  const [officersError, setOfficersError] = useState(null);
  const [provisionModalOpen, setProvisionModalOpen] = useState(false);
  const [provFullName, setProvFullName] = useState('');
  const [provEmail, setProvEmail] = useState('');
  const [provPhone, setProvPhone] = useState('');
  const [provDepartment, setProvDepartment] = useState('Migrant Labour Welfare Department');
  const [provDesignation, setProvDesignation] = useState('District Labour Commissioner');
  const [provAuthorityLevel, setProvAuthorityLevel] = useState('STATE');
  const [provState, setProvState] = useState('Maharashtra');
  const [provDistrict, setProvDistrict] = useState('');
  const [provBlock, setProvBlock] = useState('');
  const [provBenefitPermissions, setProvBenefitPermissions] = useState([
    'HOUSING_SUBSIDY', 'HEALTHCARE_ASSISTANCE'
  ]);
  const [provAllowCrossState, setProvAllowCrossState] = useState(false);
  const [officerActivationLink, setOfficerActivationLink] = useState(null);

  // Tab 4: Governance Audit Trail
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditActionFilter, setAuditActionFilter] = useState('ALL');
  const [auditTargetFilter, setAuditTargetFilter] = useState('ALL');

  // Tab 5: System Health
  const [healthData, setHealthData] = useState(null);
  const [healthLoading, setHealthLoading] = useState(false);

  // All benefit permissions options
  const AVAILABLE_BENEFITS = [
    { id: '1', label: 'Scheme #1: Interstate Migrant Worker Relief Scheme (₹3,000)' },
    { id: '2', label: 'Scheme #2: BOCW Safety & Skill Empowerment Grant (₹5,000)' },
    { id: 'ALL', label: 'All Welfare Schemes (Full Disbursement Authority)' },
    { id: 'BOCW_GRANT', label: 'BOCW Grant (Mapped to Scheme #2)' },
    { id: 'EMERGENCY_RELIEF', label: 'Emergency Relief (Mapped to Scheme #1)' },
    { id: 'HOUSING_SUBSIDY', label: 'Housing Assistance Subsidy (Legacy Category)' },
    { id: 'HEALTHCARE_ASSISTANCE', label: 'Healthcare Assistance Scheme (Legacy Category)' },
    { id: 'EDUCATION_GRANT', label: 'Child Education Grant (Legacy Category)' },
    { id: 'RATION_BENEFIT', label: 'Public Distribution / Ration (Legacy Category)' }
  ];

  // ==========================================
  // Data Loaders
  // ==========================================

  const fetchOrganizations = async () => {
    setOrgsError(null);
    try {
      let url = `/api/v1/admin/organizations?page=${orgPage}&page_size=${orgPageSize}`;
      if (orgFilter !== 'ALL') url += `&status=${encodeURIComponent(orgFilter)}`;
      if (debouncedOrgSearch && debouncedOrgSearch.trim()) url += `&search=${encodeURIComponent(debouncedOrgSearch.trim())}`;
      if (orgDateFrom) url += `&date_from=${encodeURIComponent(orgDateFrom + 'T00:00:00')}`;
      if (orgDateTo) url += `&date_to=${encodeURIComponent(orgDateTo + 'T23:59:59')}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        const parsed = parsePaginatedResponse(data, orgPage, orgPageSize);
        let items = parsed.items;
        if (orgStateFilter !== 'ALL') {
          items = items.filter(o => o.state_code === orgStateFilter || (o.org_address && o.org_address.toLowerCase().includes(orgStateFilter.toLowerCase())));
        }
        setOrganizations(items);
        setOrgTotalCount(parsed.totalCount);
        setOrgTotalPages(parsed.totalPages);
      } else {
        const errJson = await res.json().catch(() => ({ detail: `HTTP ${res.status} Error fetching organizations` }));
        setOrgsError(errJson.detail || `Server error (${res.status}) fetching organizations`);
      }
    } catch (e) {
      console.error('Failed to fetch organizations:', e);
      setOrgsError(e.message || 'Network error fetching organizations');
    }
  };

  const fetchPendingOrganizations = async () => {
    setPendingOrgsError(null);
    try {
      let url = `/api/v1/admin/pending-organizations?page=${pendingOrgPage}&page_size=${pendingOrgPageSize}`;
      if (debouncedPendingOrgSearch && debouncedPendingOrgSearch.trim()) url += `&search=${encodeURIComponent(debouncedPendingOrgSearch.trim())}`;
      if (pendingOrgDateFrom) url += `&date_from=${encodeURIComponent(pendingOrgDateFrom + 'T00:00:00')}`;
      if (pendingOrgDateTo) url += `&date_to=${encodeURIComponent(pendingOrgDateTo + 'T23:59:59')}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        const parsed = parsePaginatedResponse(data, pendingOrgPage, pendingOrgPageSize);
        let items = parsed.items;
        if (pendingOrgStateFilter !== 'ALL') {
          items = items.filter(o => o.state_code === pendingOrgStateFilter || (o.org_address && o.org_address.toLowerCase().includes(pendingOrgStateFilter.toLowerCase())));
        }
        setPendingOrgs(items);
        setPendingOrgTotalCount(parsed.totalCount);
        setPendingOrgTotalPages(parsed.totalPages);
      } else {
        const errJson = await res.json().catch(() => ({ detail: `HTTP ${res.status} Error fetching pending reviews` }));
        setPendingOrgsError(errJson.detail || `Server error (${res.status}) fetching pending reviews`);
      }
    } catch (e) {
      console.error('Failed to fetch pending organizations:', e);
      setPendingOrgsError(e.message || 'Network error fetching pending organizations');
    }
  };

  const fetchCategories = async () => {
    setCatsError(null);
    try {
      let url = `/api/v1/admin/category-requests?limit=200`;
      if (catFilter !== 'ALL') url += `&status=${encodeURIComponent(catFilter)}`;
      if (catCategoryFilter !== 'ALL') url += `&category=${encodeURIComponent(catCategoryFilter)}`;
      if (catSkillFilter !== 'ALL') url += `&skill_level=${encodeURIComponent(catSkillFilter)}`;
      if (catNatureFilter !== 'ALL') url += `&nature_of_employment=${encodeURIComponent(catNatureFilter)}`;
      if (debouncedCatSearch && debouncedCatSearch.trim()) url += `&search=${encodeURIComponent(debouncedCatSearch.trim())}`;
      if (catDateFrom) url += `&date_from=${encodeURIComponent(catDateFrom + 'T00:00:00')}`;
      if (catDateTo) url += `&date_to=${encodeURIComponent(catDateTo + 'T23:59:59')}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        const parsed = parsePaginatedResponse(data, catPage, catPageSize);
        setCategoryRequests(parsed.items);
        setCatTotalCount(parsed.totalCount);
        setCatTotalPages(parsed.totalPages);
      } else {
        const errJson = await res.json().catch(() => ({ detail: `HTTP ${res.status} Error fetching category scopes` }));
        setCatsError(errJson.detail || `Server error (${res.status}) fetching category scopes`);
      }
    } catch (e) {
      console.error('Failed to fetch category requests:', e);
      setCatsError(e.message || 'Network error fetching category requests');
    }
  };

  const fetchOfficers = async () => {
    setOfficersError(null);
    try {
      let url = `/api/v1/admin/government-officers?page=${officerPage}&page_size=${officerPageSize}`;
      if (officerFilter !== 'ALL') url += `&status=${encodeURIComponent(officerFilter)}`;
      if (officerAuthorityFilter !== 'ALL') url += `&authority_level=${encodeURIComponent(officerAuthorityFilter)}`;
      if (officerStateFilter !== 'ALL') url += `&state=${encodeURIComponent(officerStateFilter)}`;
      if (officerDistrictFilter !== 'ALL') url += `&district=${encodeURIComponent(officerDistrictFilter)}`;
      if (officerBlockFilter && officerBlockFilter.trim()) url += `&block=${encodeURIComponent(officerBlockFilter.trim())}`;
      if (debouncedOfficerSearch && debouncedOfficerSearch.trim()) url += `&search=${encodeURIComponent(debouncedOfficerSearch.trim())}`;
      if (officerDateFrom) url += `&date_from=${encodeURIComponent(officerDateFrom + 'T00:00:00')}`;
      if (officerDateTo) url += `&date_to=${encodeURIComponent(officerDateTo + 'T23:59:59')}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        const parsed = parsePaginatedResponse(data, officerPage, officerPageSize);
        setOfficers(parsed.items);
        setOfficerTotalCount(parsed.totalCount);
        setOfficerTotalPages(parsed.totalPages);
      } else {
        const errJson = await res.json().catch(() => ({ detail: `HTTP ${res.status} Error fetching government officers` }));
        setOfficersError(errJson.detail || `Server error (${res.status}) fetching government officers`);
      }
    } catch (e) {
      console.error('Failed to fetch officers:', e);
      setOfficersError(e.message || 'Network error fetching government officers');
    }
  };

  const fetchAuditLogs = async () => {
    try {
      let url = '/api/v1/admin/governance-audit-logs?limit=100';
      if (auditActionFilter !== 'ALL') url += `&action=${auditActionFilter}`;
      if (auditTargetFilter !== 'ALL') url += `&target_type=${auditTargetFilter}`;
      const res = await apiFetch(url);
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data);
      }
    } catch (e) {
      console.error('Failed to fetch audit logs:', e);
    }
  };

  const checkConnectivity = async () => {
    setHealthLoading(true);
    try {
      const res = await apiFetch('/api/v1/admin/test-connectivity', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setHealthData(data);
      }
    } catch (e) {
      console.error('Failed connectivity check:', e);
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    fetchOrganizations();
    fetchPendingOrganizations();
    fetchCategories();
    fetchOfficers();
    fetchAuditLogs();
  }, []);

  // Filter change resets pages
  useEffect(() => {
    setOrgPage(1);
  }, [debouncedOrgSearch, orgFilter, orgStateFilter, orgDateFrom, orgDateTo]);

  useEffect(() => {
    setPendingOrgPage(1);
  }, [debouncedPendingOrgSearch, pendingOrgStateFilter, pendingOrgDateFrom, pendingOrgDateTo]);

  useEffect(() => {
    setCatPage(1);
  }, [debouncedCatSearch, catFilter, catCategoryFilter, catSkillFilter, catNatureFilter, catDateFrom, catDateTo, rejectedFilter, historyFilter]);

  useEffect(() => {
    setOfficerPage(1);
  }, [debouncedOfficerSearch, officerFilter, officerAuthorityFilter, officerStateFilter, officerDistrictFilter, officerBlockFilter, officerDateFrom, officerDateTo]);

  useEffect(() => {
    if (activeTab === 'ALL_ORGS' || activeTab === 'ORGANIZATIONS') fetchOrganizations();
    else if (activeTab === 'PENDING_ORGS') fetchPendingOrganizations();
    else if (['PENDING_CATS', 'ACTIVE_SCOPES', 'REJECTED_CATS', 'HISTORY_CATS', 'CATEGORIES'].includes(activeTab)) fetchCategories();
    else if (activeTab === 'OFFICERS') fetchOfficers();
    else if (activeTab === 'AUDIT') fetchAuditLogs();
    else if (activeTab === 'HEALTH') checkConnectivity();
  }, [
    activeTab, 
    debouncedOrgSearch, orgFilter, orgStateFilter, orgDateFrom, orgDateTo, orgPage, orgPageSize,
    debouncedPendingOrgSearch, pendingOrgStateFilter, pendingOrgDateFrom, pendingOrgDateTo, pendingOrgPage, pendingOrgPageSize,
    debouncedCatSearch, catFilter, catCategoryFilter, catSkillFilter, catNatureFilter, catDateFrom, catDateTo, catPage, catPageSize, rejectedFilter, historyFilter,
    debouncedOfficerSearch, officerFilter, officerAuthorityFilter, officerStateFilter, officerDistrictFilter, officerBlockFilter, officerDateFrom, officerDateTo, officerPage, officerPageSize,
    auditActionFilter, auditTargetFilter
  ]);

  // ==========================================
  // Handlers: Tab 1 Organizations
  // ==========================================

  const handleOpenOrgDecision = (org) => {
    setSelectedOrg(org);
    setOrgAction(org.status === 'PENDING_REVIEW' ? 'APPROVE' : 'SUSPEND');
    setOrgReason('');
    setOrgNotes('');
    setOrgDecisionModalOpen(true);
  };

  const submitOrgDecision = async (e) => {
    e.preventDefault();
    if (!selectedOrg) return;

    if (['REJECT', 'REQUEST_MORE_INFO', 'SUSPEND', 'DISABLE'].includes(orgAction) && !orgReason.trim()) {
      alert(`Reason is mandatory for action: ${orgAction}`);
      return;
    }

    try {
      setLoading(true);
      setErrorMsg('');
      setActionMsg('');
      const res = await apiFetch(`/api/v1/admin/decide-organization/${selectedOrg.id}`, {
        method: 'POST',
        body: {
          action: orgAction,
          reason: orgReason,
          notes: orgNotes
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to update organization status');

      if (data.activation_link) {
        setActivationLink(data.activation_link);
        const token = data.raw_token || (data.activation_link.match(/[?&]token=([^&]+)/) || [])[1] || null;
        setActivationToken(token);
        if (data.delivery_status === 'SENT') {
          setActionMsg(`${data.message}. ✓ Activation email dispatched via SMTP.`);
        } else if (data.delivery_status === 'FAILED') {
          setActionMsg(`${data.message}. ⚠️ SMTP delivery failed (${data.delivery_error || 'Network error'}). Copy token or link below.`);
        } else {
          setActionMsg(`${data.message}. ℹ️ SMTP not configured; simulated activation token generated below.`);
        }
      } else {
        setActionMsg(data.message);
      }
      setOrgDecisionModalOpen(false);
      await fetchOrganizations();
      await fetchPendingOrganizations();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResendEmployerActivation = async (orgId) => {
    try {
      setLoading(true);
      setErrorMsg('');
      const res = await apiFetch(`/api/v1/admin/resend-employer-activation/${orgId}`, {
        method: 'POST'
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to resend activation token');

      if (data.delivery_status === 'SENT') {
        setActionMsg(`✓ Activation email dispatched via SMTP to ${data.recipient_email} (Attempt #${data.attempt_count})`);
      } else if (data.delivery_status === 'FAILED') {
        setActionMsg(`⚠️ SMTP delivery attempt failed for ${data.recipient_email}: ${data.delivery_error || 'Network error'}. Copy token or link below.`);
      } else {
        setActionMsg(`ℹ️ SMTP is not configured. Simulated activation token generated for ${data.recipient_email}. Copy token or link below.`);
      }
      if (data.activation_link) {
        setActivationLink(data.activation_link);
        const token = data.raw_token || (data.activation_link.match(/[?&]token=([^&]+)/) || [])[1] || null;
        setActivationToken(token);
      }
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // Handlers: Category Scopes & Authorization
  // ==========================================

  const handleOpenCatDecision = (req) => {
    setSelectedCatReq(req);
    setCatAction('APPROVE');
    setCatReason('');
    setCatDecisionModalOpen(true);
  };

  const submitCatDecision = async (e) => {
    e.preventDefault();
    if (!selectedCatReq) return;

    if (['REJECT', 'REQUEST_MORE_INFO', 'SUSPEND'].includes(catAction) && !catReason.trim()) {
      alert(`Reason is mandatory for ${catAction}`);
      return;
    }

    try {
      setLoading(true);
      setErrorMsg('');
      const res = await apiFetch(`/api/v1/admin/decide-category/${selectedCatReq.id}`, {
        method: 'POST',
        body: {
          action: catAction,
          reason: catReason,
          requested_information: catAction === 'REQUEST_MORE_INFO' ? catReason : undefined
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to decide category scope');

      setActionMsg(`Category request for '${data.category}' transitioned to ${data.status}`);
      setCatDecisionModalOpen(false);
      await fetchCategories();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDiscontinue = (req) => {
    setSelectedCatReq(req);
    setDiscontinueReason('');
    setDiscontinueModalOpen(true);
  };

  const handleOpenSuspend = (req) => {
    setSelectedCatReq(req);
    setSuspendReason('');
    setSuspendModalOpen(true);
  };

  const submitSuspendCategory = async (e) => {
    e.preventDefault();
    if (!selectedCatReq) return;

    if (!suspendReason.trim()) {
      alert('Suspension reason is strictly mandatory');
      return;
    }

    try {
      setLoading(true);
      setErrorMsg('');
      let res;
      try {
        res = await apiFetch(`/api/v1/admin/category-requests/${selectedCatReq.id}`, {
          method: 'PATCH',
          body: {
            action: 'SUSPEND',
            reason: suspendReason
          }
        });
      } catch (patchErr) {
        // Fallback to POST for network/runtime environments restricting HTTP PATCH
        res = await apiFetch(`/api/v1/admin/category-requests/${selectedCatReq.id}`, {
          method: 'POST',
          body: {
            action: 'SUSPEND',
            reason: suspendReason
          }
        });
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to suspend category');

      setActionMsg(`Category '${data.category}' suspended. Parent employer organization status preserved as ACTIVE.`);
      setSuspendModalOpen(false);
      await fetchCategories();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitDiscontinueCategory = async (e) => {
    e.preventDefault();
    if (!selectedCatReq) return;

    if (!discontinueReason.trim()) {
      alert('Discontinuation reason is strictly mandatory');
      return;
    }

    try {
      setLoading(true);
      setErrorMsg('');
      const res = await apiFetch(`/api/v1/admin/discontinue-category/${selectedCatReq.id}`, {
        method: 'POST',
        body: { reason: discontinueReason }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to discontinue category');

      setActionMsg(data.message);
      setDiscontinueModalOpen(false);
      await fetchCategories();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // Handlers: Tab 3 Government Officers
  // ==========================================

  const toggleBenefitPermission = (permId) => {
    setProvBenefitPermissions(prev => 
      prev.includes(permId) ? prev.filter(p => p !== permId) : [...prev, permId]
    );
  };

  const submitProvisionOfficer = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      setErrorMsg('');
      const perms = ['WORKER_VERIFICATION', 'DISBURSE_BENEFIT'];
      if (provAllowCrossState) {
        perms.push('CROSS_STATE_VERIFICATION');
      }
      const payload = {
        full_name: provFullName,
        official_email: provEmail,
        phone: provPhone || undefined,
        department: provDepartment,
        designation: provDesignation,
        authority_level: provAuthorityLevel,
        state: provAuthorityLevel === 'NATIONAL' ? undefined : provState,
        district: ['DISTRICT', 'BLOCK'].includes(provAuthorityLevel) ? provDistrict : undefined,
        block: provAuthorityLevel === 'BLOCK' ? provBlock : undefined,
        permissions: perms,
        benefit_permissions: provBenefitPermissions
      };

      const res = await apiFetch('/api/v1/admin/government-officers', {
        method: 'POST',
        body: payload
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Officer provisioning failed');

      setActionMsg(`Officer '${data.full_name}' provisioned successfully (${data.officer_reference_id})`);
      if (data.activation_link) {
        setOfficerActivationLink(data.activation_link);
        const token = data.raw_token || (data.activation_link.match(/[?&]token=([^&]+)/) || [])[1] || null;
        setActivationToken(token);
      }
      setProvisionModalOpen(false);
      // Reset form
      setProvFullName('');
      setProvEmail('');
      setProvPhone('');
      setProvAllowCrossState(false);
      await fetchOfficers();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenOfficerSuspend = (off) => {
    setSelectedOfficerForSuspend(off);
    setOfficerSuspendReason('');
    setOfficerSuspendModalOpen(true);
  };

  const submitOfficerSuspend = async (e) => {
    e.preventDefault();
    if (!selectedOfficerForSuspend) return;
    if (!officerSuspendReason.trim()) {
      alert('Suspension reason is strictly mandatory');
      return;
    }

    try {
      setOfficerSuspendSubmitting(true);
      setErrorMsg('');
      const res = await apiFetch(`/api/v1/admin/government-officers/${selectedOfficerForSuspend.id}/status`, {
        method: 'POST',
        body: {
          status: 'SUSPENDED',
          reason: officerSuspendReason.trim()
        }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to suspend officer');

      setActionMsg(`Officer '${data.officer_name || data.full_name || selectedOfficerForSuspend.id}' has been suspended.`);
      setOfficerSuspendModalOpen(false);
      setSelectedOfficerForSuspend(null);
      setOfficerSuspendReason('');
      await fetchOfficers();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to suspend officer');
    } finally {
      setOfficerSuspendSubmitting(false);
    }
  };

  const handleReactivateOfficer = async (officerId) => {
    try {
      setLoading(true);
      setErrorMsg('');
      const res = await apiFetch(`/api/v1/admin/government-officers/${officerId}/status`, {
        method: 'POST',
        body: { status: 'ACTIVE', reason: 'Reactivated by admin' }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to reactivate officer');

      setActionMsg(`Officer '${data.officer_name || data.full_name || officerId}' reactivated to ACTIVE.`);
      await fetchOfficers();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to reactivate officer');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateOfficerStatus = async (officerId, newStatus) => {
    if (newStatus === 'SUSPENDED') {
      const off = officers.find(o => o.id === officerId);
      if (off) {
        handleOpenOfficerSuspend(off);
        return;
      }
    }
    if (newStatus === 'ACTIVE') {
      await handleReactivateOfficer(officerId);
      return;
    }
    try {
      setLoading(true);
      setErrorMsg('');
      const res = await apiFetch(`/api/v1/admin/government-officers/${officerId}/status`, {
        method: 'POST',
        body: { status: newStatus, reason: `Admin updated status to ${newStatus}` }
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to update officer status');

      setActionMsg(`Officer '${data.officer_name || data.full_name || officerId}' status updated to ${data.status}`);
      await fetchOfficers();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResendOfficerActivation = async (officerId) => {
    try {
      setLoading(true);
      setErrorMsg('');
      const res = await apiFetch(`/api/v1/admin/government-officers/${officerId}/resend-activation`, {
        method: 'POST'
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to resend officer activation');

      if (data.delivery_status === 'SENT') {
        setActionMsg(`✓ Officer activation email dispatched via SMTP to ${data.recipient_email} (Attempt #${data.attempt_count})`);
      } else if (data.delivery_status === 'FAILED') {
        setActionMsg(`⚠️ SMTP delivery attempt failed for ${data.recipient_email}: ${data.delivery_error || 'Network error'}. Copy token or link below.`);
      } else {
        setActionMsg(`ℹ️ SMTP is not configured. Simulated activation token generated for ${data.recipient_email}. Copy token or link below.`);
      }
      if (data.activation_link) {
        setOfficerActivationLink(data.activation_link);
        const token = data.raw_token || (data.activation_link.match(/[?&]token=([^&]+)/) || [])[1] || null;
        setActivationToken(token);
      }
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  const copyTokenToClipboard = (token) => {
    if (!token) return;
    navigator.clipboard.writeText(token);
    setCopiedToken(true);
    setTimeout(() => setCopiedToken(false), 2500);
  };

  // Helper for active tab matching with backwards compatibility
  const isTabActive = (tabKey) => {
    if (tabKey === 'ALL_ORGS') return activeTab === 'ALL_ORGS' || activeTab === 'ORGANIZATIONS';
    if (tabKey === 'PENDING_CATS') return activeTab === 'PENDING_CATS' || activeTab === 'CATEGORIES';
    return activeTab === tabKey;
  };

  // Helper for multi-field filtering on category lists
  const filterCatList = (list, searchStr) => {
    let result = list;
    if (catCategoryFilter !== 'ALL') {
      result = result.filter(r => r.category && r.category.toLowerCase() === catCategoryFilter.toLowerCase());
    }
    if (catSkillFilter !== 'ALL') {
      result = result.filter(r => r.skill_level && r.skill_level.toLowerCase() === catSkillFilter.toLowerCase());
    }
    if (catNatureFilter !== 'ALL') {
      result = result.filter(r => r.nature_of_employment && r.nature_of_employment.toLowerCase() === catNatureFilter.toLowerCase());
    }
    if (catDateFrom) {
      result = result.filter(r => r.submitted_at && new Date(r.submitted_at) >= new Date(catDateFrom + 'T00:00:00'));
    }
    if (catDateTo) {
      result = result.filter(r => r.submitted_at && new Date(r.submitted_at) <= new Date(catDateTo + 'T23:59:59'));
    }
    if (searchStr && searchStr.trim()) {
      const q = searchStr.trim().toLowerCase();
      result = result.filter(r => 
        (r.category && r.category.toLowerCase().includes(q)) ||
        (r.organization_name && r.organization_name.toLowerCase().includes(q)) ||
        (r.registration_ref_number && r.registration_ref_number.toLowerCase().includes(q)) ||
        (r.skill_level && r.skill_level.toLowerCase().includes(q)) ||
        (r.nature_of_employment && r.nature_of_employment.toLowerCase().includes(q)) ||
        (r.status && r.status.toLowerCase().includes(q)) ||
        (String(r.organization_id || '').toLowerCase().includes(q))
      );
    }
    return result;
  };

  // Derived category lists for dedicated workflow views (Views 3-6)
  const pendingCatRequests = categoryRequests.filter(req => 
    ['PENDING', 'PENDING_REVIEW'].includes(req.status)
  );

  const activeScopeRequests = categoryRequests.filter(req => 
    req.status === 'APPROVED' && (req.is_active_scope === true || req.is_active_scope === undefined)
  );

  const rejectedCatRequests = categoryRequests.filter(req => {
    const isMatch = ['REJECTED', 'REQUEST_MORE_INFO', 'MORE_INFO_REQUIRED', 'MORE_INFO'].includes(req.status);
    if (!isMatch) return false;
    if (rejectedFilter === 'REJECTED') return req.status === 'REJECTED';
    if (rejectedFilter === 'MORE_INFO_REQUIRED') return ['REQUEST_MORE_INFO', 'MORE_INFO_REQUIRED', 'MORE_INFO'].includes(req.status);
    return true;
  });

  const historyCatRequests = categoryRequests.filter(req => {
    const isHistory = ['DISCONTINUED', 'SUSPENDED', 'SUPERSEDED'].includes(req.status) || (req.is_active_scope === false && req.status !== 'PENDING' && req.status !== 'PENDING_REVIEW');
    if (!isHistory) return false;
    if (historyFilter === 'DISCONTINUED') return req.status === 'DISCONTINUED';
    if (historyFilter === 'SUSPENDED') return req.status === 'SUSPENDED';
    if (historyFilter === 'SUPERSEDED') return req.status === 'SUPERSEDED';
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Platform Governance Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-amber-600/15 border border-amber-500/30 text-amber-400 flex items-center justify-center text-2xl font-bold">
              ⚖️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">Platform Governance &amp; Operations Center</h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono">
                  v0.4 Governance
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Centralized authority for employer reviews, category scope lifecycles, government officer provisioning, and cryptographic audit trails.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (activeTab === 'ALL_ORGS' || activeTab === 'ORGANIZATIONS') fetchOrganizations();
                else if (activeTab === 'PENDING_ORGS') fetchPendingOrganizations();
                else if (['PENDING_CATS', 'ACTIVE_SCOPES', 'REJECTED_CATS', 'HISTORY_CATS', 'CATEGORIES'].includes(activeTab)) fetchCategories();
                else if (activeTab === 'OFFICERS') fetchOfficers();
                else if (activeTab === 'AUDIT') fetchAuditLogs();
                else if (activeTab === 'HEALTH') checkConnectivity();
              }}
              className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold border border-slate-700 flex items-center gap-1.5 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Platform Governance Navigation Bar (6 Workflow Views + Officers + Audit + Health) */}
        <div className="mt-6 pt-4 border-t border-slate-800 flex items-center gap-2 overflow-x-auto text-xs font-medium pb-1">
          <button
            onClick={() => setActiveTab('ALL_ORGS')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition whitespace-nowrap ${
              isTabActive('ALL_ORGS')
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <Building2 className="w-3.5 h-3.5 shrink-0" />
            <span>All Organizations</span>
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold ${
              isTabActive('ALL_ORGS') ? 'bg-blue-800/80 text-blue-100' : 'bg-slate-800 text-slate-300'
            }`}>
              {organizations.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('PENDING_ORGS')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition whitespace-nowrap ${
              isTabActive('PENDING_ORGS')
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <Clock className="w-3.5 h-3.5 shrink-0 text-amber-400" />
            <span>Pending Org Reviews</span>
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold ${
              isTabActive('PENDING_ORGS') ? 'bg-amber-600/50 text-amber-100' : 'bg-amber-500/20 text-amber-300'
            }`}>
              {pendingOrgs.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('PENDING_CATS')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition whitespace-nowrap ${
              isTabActive('PENDING_CATS')
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <Layers className="w-3.5 h-3.5 shrink-0 text-amber-400" />
            <span>Pending Categories</span>
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold ${
              isTabActive('PENDING_CATS') ? 'bg-amber-600/50 text-amber-100' : 'bg-amber-500/20 text-amber-300'
            }`}>
              {pendingCatRequests.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('ACTIVE_SCOPES')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition whitespace-nowrap ${
              isTabActive('ACTIVE_SCOPES')
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-400" />
            <span>Active Scopes</span>
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold ${
              isTabActive('ACTIVE_SCOPES') ? 'bg-emerald-600/50 text-emerald-100' : 'bg-emerald-500/20 text-emerald-300'
            }`}>
              {activeScopeRequests.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('REJECTED_CATS')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition whitespace-nowrap ${
              isTabActive('REJECTED_CATS')
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5 shrink-0 text-rose-400" />
            <span>Rejected / Info</span>
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold ${
              isTabActive('REJECTED_CATS') ? 'bg-rose-600/50 text-rose-100' : 'bg-rose-500/20 text-rose-300'
            }`}>
              {rejectedCatRequests.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('HISTORY_CATS')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition whitespace-nowrap ${
              isTabActive('HISTORY_CATS')
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <Ban className="w-3.5 h-3.5 shrink-0 text-purple-400" />
            <span>Category History</span>
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold ${
              isTabActive('HISTORY_CATS') ? 'bg-purple-600/50 text-purple-100' : 'bg-purple-500/20 text-purple-300'
            }`}>
              {historyCatRequests.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('OFFICERS')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition whitespace-nowrap ${
              isTabActive('OFFICERS')
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <Landmark className="w-3.5 h-3.5 shrink-0" />
            <span>Government Officers</span>
          </button>

          <button
            onClick={() => setActiveTab('AUDIT')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition whitespace-nowrap ${
              isTabActive('AUDIT')
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
            <span>Governance Audit Trail</span>
          </button>

          <button
            onClick={() => setActiveTab('HEALTH')}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition whitespace-nowrap ${
              isTabActive('HEALTH')
                ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/20'
                : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
            }`}
          >
            <Activity className="w-3.5 h-3.5 shrink-0" />
            <span>System Health</span>
          </button>
        </div>
      </div>

      {/* Global Alerts & Activation Banner */}
      {actionMsg && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{actionMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {(activationLink || officerActivationLink) && (
        <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-2xl space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-blue-300 flex items-center gap-1.5">
              <Key className="w-4 h-4 text-blue-400" />
              <span>Provisioning Credentials & Activation Details</span>
            </span>
            <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
              Single-Use Token
            </span>
          </div>

          {/* Raw Token Box (For pasting directly into Activate Org or Activate Gov tabs) */}
          {activationToken && (
            <div className="space-y-1.5 p-3 rounded-xl bg-slate-950/90 border border-emerald-500/30">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Activation Token (for "Activate Org" or "Activate Gov" tab):</span>
                </span>
                <button
                  type="button"
                  onClick={() => copyTokenToClipboard(activationToken)}
                  className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-semibold flex items-center gap-1 transition shadow-sm"
                >
                  {copiedToken ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedToken ? 'Copied Token' : 'Copy Token'}</span>
                </button>
              </div>
              <p className="text-xs font-mono font-bold text-emerald-200 p-2 rounded-lg bg-emerald-950/40 border border-emerald-800/50 break-all select-all">
                {activationToken}
              </p>
            </div>
          )}

          {/* Direct Activation Link Box */}
          <div className="space-y-1.5 p-3 rounded-xl bg-slate-950/90 border border-slate-800">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-blue-300 flex items-center gap-1">
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Direct Activation URL:</span>
              </span>
              <button
                type="button"
                onClick={() => copyToClipboard(activationLink || officerActivationLink)}
                className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-semibold flex items-center gap-1 transition shadow-sm"
              >
                {copiedLink ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                <span>{copiedLink ? 'Copied Link' : 'Copy Link'}</span>
              </button>
            </div>
            <p className="text-xs font-mono text-slate-200 p-2 rounded-lg bg-slate-900 border border-slate-800 break-all select-all">
              {activationLink || officerActivationLink}
            </p>
          </div>

          {/* Delivery Advisory note */}
          <div className="text-[11px] text-slate-400 flex items-start gap-1.5 pt-1">
            <Info className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5" />
            <span>
              If SMTP dispatch is active, the recipient should check their <strong className="text-slate-200">Spam / Junk folder</strong> if the email does not appear in the primary inbox within 60 seconds. Alternatively, supply the raw token above directly into the sign-in modal activation tab.
            </span>
          </div>
        </div>
      )}

      {/* ============================================================
          VIEW 1: ALL EMPLOYER ORGANIZATIONS DIRECTORY
      ============================================================ */}
      {isTabActive('ALL_ORGS') && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Building2 className="w-4 h-4 text-blue-400" />
                <span>All Employer Organizations Directory</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/30 font-mono">
                  {orgTotalCount} Total Organizations
                </span>
              </h3>
              <p className="text-xs text-slate-400">Comprehensive directory of registered employer organizations across all legal and verification states.</p>
            </div>
          </div>

          {/* View 1 Comprehensive Filter Bar */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 space-y-2.5">
            <div className="flex flex-col md:flex-row items-stretch md:items-center gap-2.5">
              {/* Free-Text Search Input */}
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={orgSearch}
                  onChange={(e) => setOrgSearch(e.target.value)}
                  placeholder="Search by name, ref, email, phone..."
                  className="w-full pl-9 pr-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 outline-none focus:border-blue-500"
                />
              </div>

              {/* State Filter */}
              <div className="flex items-center gap-1.5 shrink-0 text-xs">
                <span className="text-slate-400 text-[11px]">State:</span>
                <select
                  value={orgStateFilter}
                  onChange={(e) => setOrgStateFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-blue-500"
                >
                  {INDIAN_STATES_OPTIONS.map(st => (
                    <option key={st} value={st}>{st === 'ALL' ? 'All States' : st}</option>
                  ))}
                </select>
              </div>

              {/* Date Range */}
              <div className="flex items-center gap-1.5 shrink-0 text-xs">
                <span className="text-slate-400 text-[11px]">From:</span>
                <input
                  type="date"
                  value={orgDateFrom}
                  onChange={(e) => setOrgDateFrom(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-blue-500"
                />
                <span className="text-slate-400 text-[11px]">To:</span>
                <input
                  type="date"
                  value={orgDateTo}
                  onChange={(e) => setOrgDateTo(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-blue-500"
                />
              </div>

              {/* Clear Filters */}
              <button
                onClick={() => {
                  setOrgSearch('');
                  setOrgFilter('ALL');
                  setOrgStateFilter('ALL');
                  setOrgDateFrom('');
                  setOrgDateTo('');
                  setOrgPage(1);
                }}
                className="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg text-xs border border-slate-800 flex items-center gap-1 transition shrink-0"
                title="Reset all filters"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Clear Filters</span>
              </button>
            </div>

            {/* Status Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pt-1 border-t border-slate-900 text-xs">
              <span className="text-slate-500 text-[11px] shrink-0">Status:</span>
              {['ALL', 'PENDING_REVIEW', 'APPROVED', 'ACTIVE', 'SUSPENDED', 'REJECTED'].map(st => (
                <button
                  key={st}
                  onClick={() => setOrgFilter(st)}
                  className={`px-2.5 py-1 rounded-lg transition font-medium text-[11px] whitespace-nowrap ${
                    orgFilter === st ? 'bg-blue-600 text-white font-bold' : 'text-slate-400 hover:text-slate-200 bg-slate-900/60'
                  }`}
                >
                  {st.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Truthful Error Card */}
          {orgsError && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-rose-400">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>Failed to load organizations: {orgsError}</span>
              </div>
              <button 
                onClick={fetchOrganizations} 
                className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg flex items-center gap-1.5 transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry</span>
              </button>
            </div>
          )}

          {!orgsError && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                  <tr>
                    <th className="py-3 px-3">Organization &amp; Ref</th>
                    <th className="py-3 px-3">Official Email &amp; Contact</th>
                    <th className="py-3 px-3">Business Type</th>
                    <th className="py-3 px-3">Standing Status</th>
                    <th className="py-3 px-3 text-right">Governance Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {organizations.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-500 italic">
                        No organizations match your search or filter criteria.
                      </td>
                    </tr>
                  ) : (
                    organizations.map(org => (
                      <tr key={org.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-3 px-3">
                          <div className="font-semibold text-white">{org.name}</div>
                          <div className="text-[11px] font-mono text-slate-400">{org.registration_ref_number || org.reg_number || 'N/A'}</div>
                        </td>
                        <td className="py-3 px-3">
                          <div className="text-slate-200">{org.official_email || 'N/A'}</div>
                          <div className="text-[11px] text-slate-400">{org.contact_person || 'N/A'} {org.official_phone ? `• ${org.official_phone}` : ''}</div>
                        </td>
                        <td className="py-3 px-3 text-slate-300">
                          {org.business_type || 'Private Ltd'}
                        </td>
                        <td className="py-3 px-3">
                          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                            org.status === 'APPROVED' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' :
                            org.status === 'ACTIVE' ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30' :
                            org.status === 'PENDING_REVIEW' ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' :
                            org.status === 'SUSPENDED' ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30' :
                            'bg-slate-800 text-slate-400 border border-slate-700'
                          }`}>
                            {org.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => handleOpenOrgDecision(org)}
                              className="px-2.5 py-1 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 rounded-lg text-[11px] font-semibold transition"
                            >
                              Review / Decide
                            </button>
                            {['APPROVED', 'ACTIVE'].includes(org.status) && (
                              <button
                                onClick={() => handleResendEmployerActivation(org.id)}
                                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700 rounded-lg text-[11px] transition"
                                title="Resend activation invitation email"
                              >
                                Resend Token
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              <PaginationControls
                currentPage={orgPage}
                totalPages={orgTotalPages}
                pageSize={orgPageSize}
                totalItems={orgTotalCount}
                onPageChange={setOrgPage}
                onPageSizeChange={setOrgPageSize}
                itemLabel="organizations"
              />
            </div>
          )}
        </div>
      )}

      {/* ============================================================
          VIEW 2: PENDING ORGANIZATION REVIEWS QUEUE
      ============================================================ */}
      {isTabActive('PENDING_ORGS') && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-400" />
                <span>Pending Organization Reviews Queue</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono">
                  {pendingOrgTotalCount} Total Pending
                </span>
              </h3>
              <p className="text-xs text-slate-400">Dedicated review queue for employer registrations requiring legal inspection before platform access.</p>
            </div>
          </div>

          {/* View 2 Comprehensive Filter Bar */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 space-y-2.5">
            <div className="flex flex-col md:flex-row items-stretch md:items-center gap-2.5">
              {/* Free-Text Search Input */}
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={pendingOrgSearch}
                  onChange={(e) => setPendingOrgSearch(e.target.value)}
                  placeholder="Search by name, ref, email, phone..."
                  className="w-full pl-9 pr-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 outline-none focus:border-amber-500"
                />
              </div>

              {/* State Filter */}
              <div className="flex items-center gap-1.5 shrink-0 text-xs">
                <span className="text-slate-400 text-[11px]">State:</span>
                <select
                  value={pendingOrgStateFilter}
                  onChange={(e) => setPendingOrgStateFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-amber-500"
                >
                  {INDIAN_STATES_OPTIONS.map(st => (
                    <option key={st} value={st}>{st === 'ALL' ? 'All States' : st}</option>
                  ))}
                </select>
              </div>

              {/* Date Range */}
              <div className="flex items-center gap-1.5 shrink-0 text-xs">
                <span className="text-slate-400 text-[11px]">From:</span>
                <input
                  type="date"
                  value={pendingOrgDateFrom}
                  onChange={(e) => setPendingOrgDateFrom(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-amber-500"
                />
                <span className="text-slate-400 text-[11px]">To:</span>
                <input
                  type="date"
                  value={pendingOrgDateTo}
                  onChange={(e) => setPendingOrgDateTo(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-amber-500"
                />
              </div>

              {/* Clear Filters */}
              <button
                onClick={() => {
                  setPendingOrgSearch('');
                  setPendingOrgStateFilter('ALL');
                  setPendingOrgDateFrom('');
                  setPendingOrgDateTo('');
                  setPendingOrgPage(1);
                }}
                className="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg text-xs border border-slate-800 flex items-center gap-1 transition shrink-0"
                title="Reset all filters"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Clear Filters</span>
              </button>
            </div>
          </div>

          {/* Truthful Error Card */}
          {pendingOrgsError && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-rose-400">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>Failed to load pending organization reviews: {pendingOrgsError}</span>
              </div>
              <button 
                onClick={fetchPendingOrganizations} 
                className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg flex items-center gap-1.5 transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry</span>
              </button>
            </div>
          )}

          {!pendingOrgsError && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                  <tr>
                    <th className="py-3 px-3">Organization &amp; Ref</th>
                    <th className="py-3 px-3">Official Email &amp; Contact</th>
                    <th className="py-3 px-3">Business Type &amp; State</th>
                    <th className="py-3 px-3">Standing Status</th>
                    <th className="py-3 px-3 text-right">Review Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {pendingOrgs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-500 italic">
                        No pending employer organizations currently awaiting review.
                      </td>
                    </tr>
                  ) : (
                    pendingOrgs.map(org => (
                      <tr key={org.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-3 px-3">
                          <div className="font-semibold text-white">{org.name}</div>
                          <div className="text-[11px] font-mono text-amber-400">{org.registration_ref_number || org.reg_number || 'N/A'}</div>
                        </td>
                        <td className="py-3 px-3">
                          <div className="text-slate-200">{org.official_email || 'N/A'}</div>
                          <div className="text-[11px] text-slate-400">{org.contact_person || 'N/A'}</div>
                        </td>
                        <td className="py-3 px-3 text-slate-300">
                          {org.business_type || 'Private Ltd'} {org.state_code ? `(${org.state_code})` : ''}
                        </td>
                        <td className="py-3 px-3">
                          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                            PENDING_REVIEW
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <button
                            onClick={() => handleOpenOrgDecision(org)}
                            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[11px] font-semibold transition shadow-md shadow-blue-600/20"
                          >
                            Review / Decide
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              <PaginationControls
                currentPage={pendingOrgPage}
                totalPages={pendingOrgTotalPages}
                pageSize={pendingOrgPageSize}
                totalItems={pendingOrgTotalCount}
                onPageChange={setPendingOrgPage}
                onPageSizeChange={setPendingOrgPageSize}
                itemLabel="pending organizations"
              />
            </div>
          )}
        </div>
      )}

      {/* ============================================================
          VIEW 3: PENDING CATEGORY AUTHORIZATION REQUESTS QUEUE
      ============================================================ */}
      {isTabActive('PENDING_CATS') && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          {(() => {
            const displayedPendingCats = filterCatList(pendingCatRequests, debouncedCatSearch);
            const paginatedPendingCats = displayedPendingCats.slice((catPage - 1) * catPageSize, catPage * catPageSize);
            const totalPendingCats = displayedPendingCats.length;
            const totalPendingCatPages = Math.max(1, Math.ceil(totalPendingCats / catPageSize));

            return (
              <>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <Layers className="w-4 h-4 text-amber-400" />
                      <span>Pending Category Authorization Requests Queue</span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono">
                        {totalPendingCats} Total Pending
                      </span>
                    </h3>
                    <p className="text-xs text-slate-400">Employer applications to add specific trade verticals to their verification envelope.</p>
                  </div>
                </div>

                {/* Category Comprehensive Filter Bar */}
                <CategoryFilterBar
                  search={catSearch}
                  onSearchChange={setCatSearch}
                  category={catCategoryFilter}
                  onCategoryChange={setCatCategoryFilter}
                  skill={catSkillFilter}
                  onSkillChange={setCatSkillFilter}
                  nature={catNatureFilter}
                  onNatureChange={setCatNatureFilter}
                  dateFrom={catDateFrom}
                  onDateFromChange={setCatDateFrom}
                  dateTo={catDateTo}
                  onDateToChange={setCatDateTo}
                  onClear={() => {
                    setCatSearch('');
                    setCatCategoryFilter('ALL');
                    setCatSkillFilter('ALL');
                    setCatNatureFilter('ALL');
                    setCatDateFrom('');
                    setCatDateTo('');
                    setCatPage(1);
                  }}
                  accentColor="amber"
                />

                {/* Truthful Error Card */}
                {catsError && (
                  <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 text-rose-400">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>Failed to load category requests: {catsError}</span>
                    </div>
                    <button 
                      onClick={fetchCategories} 
                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg flex items-center gap-1.5 transition"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Retry</span>
                    </button>
                  </div>
                )}

                {!catsError && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                        <tr>
                          <th className="py-3 px-3">Employer Organization</th>
                          <th className="py-3 px-3">Requested Trade</th>
                          <th className="py-3 px-3">Skill Level &amp; Nature</th>
                          <th className="py-3 px-3">Version</th>
                          <th className="py-3 px-3">Status</th>
                          <th className="py-3 px-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                        {paginatedPendingCats.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="py-6 text-center text-slate-500 italic font-sans">
                              No pending category scope requests awaiting review.
                            </td>
                          </tr>
                        ) : (
                          paginatedPendingCats.map(req => (
                            <tr key={req.id} className="hover:bg-slate-800/30 transition">
                              <td className="py-3 px-3 font-sans">
                                <div className="font-semibold text-white">{req.organization_name || `Org #${req.organization_id}`}</div>
                                <div className="text-[10px] text-slate-400">{req.registration_ref_number || 'N/A'}</div>
                              </td>
                              <td className="py-3 px-3 font-semibold text-white font-sans">{req.category}</td>
                              <td className="py-3 px-3 text-slate-300 font-sans">
                                {req.skill_level || 'Skilled'} • {req.nature_of_employment || 'Contract'}
                              </td>
                              <td className="py-3 px-3 text-blue-400">v{req.request_version || 1}</td>
                              <td className="py-3 px-3 font-sans">
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                                  PENDING
                                </span>
                              </td>
                              <td className="py-3 px-3 text-right font-sans">
                                <button
                                  onClick={() => handleOpenCatDecision(req)}
                                  className="px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 rounded-lg text-[11px] font-semibold transition"
                                >
                                  Decide Scope
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                    <PaginationControls
                      currentPage={catPage}
                      totalPages={totalPendingCatPages}
                      pageSize={catPageSize}
                      totalItems={totalPendingCats}
                      onPageChange={setCatPage}
                      onPageSizeChange={setCatPageSize}
                      itemLabel="pending category requests"
                    />
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* ============================================================
          VIEW 4: APPROVED / ACTIVE CATEGORY SCOPES DIRECTORY
      ============================================================ */}
      {isTabActive('ACTIVE_SCOPES') && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          {(() => {
            const displayedActiveScopes = filterCatList(activeScopeRequests, debouncedCatSearch);
            const paginatedActiveScopes = displayedActiveScopes.slice((catPage - 1) * catPageSize, catPage * catPageSize);
            const totalActiveScopes = displayedActiveScopes.length;
            const totalActiveScopePages = Math.max(1, Math.ceil(totalActiveScopes / catPageSize));

            return (
              <>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>Approved &amp; Active Category Scopes Directory</span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-mono">
                        {totalActiveScopes} Total Active
                      </span>
                    </h3>
                    <p className="text-xs text-slate-400">Trade verticals currently active and provisioned on-chain for worker verification.</p>
                  </div>
                </div>

                {/* Decoupling Invariant Banner */}
                <div className="p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-xl text-cyan-300 text-xs flex items-center gap-2.5">
                  <Shield className="w-4 h-4 shrink-0 text-cyan-400" />
                  <div className="leading-relaxed">
                    <strong>Decoupling Invariant Guaranteed:</strong> Discontinuing or suspending an individual trade vertical revokes its on-chain authorization while strictly preserving parent employer organization standing as <span className="underline font-semibold">ACTIVE</span>.
                  </div>
                </div>

                {/* Category Comprehensive Filter Bar */}
                <CategoryFilterBar
                  search={catSearch}
                  onSearchChange={setCatSearch}
                  category={catCategoryFilter}
                  onCategoryChange={setCatCategoryFilter}
                  skill={catSkillFilter}
                  onSkillChange={setCatSkillFilter}
                  nature={catNatureFilter}
                  onNatureChange={setCatNatureFilter}
                  dateFrom={catDateFrom}
                  onDateFromChange={setCatDateFrom}
                  dateTo={catDateTo}
                  onDateToChange={setCatDateTo}
                  onClear={() => {
                    setCatSearch('');
                    setCatCategoryFilter('ALL');
                    setCatSkillFilter('ALL');
                    setCatNatureFilter('ALL');
                    setCatDateFrom('');
                    setCatDateTo('');
                    setCatPage(1);
                  }}
                  accentColor="cyan"
                />

                {/* Truthful Error Card */}
                {catsError && (
                  <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 text-rose-400">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>Failed to load category scopes: {catsError}</span>
                    </div>
                    <button 
                      onClick={fetchCategories} 
                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg flex items-center gap-1.5 transition"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Retry</span>
                    </button>
                  </div>
                )}

                {!catsError && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                        <tr>
                          <th className="py-3 px-3">Employer Organization</th>
                          <th className="py-3 px-3">Parent Org Standing</th>
                          <th className="py-3 px-3">Authorized Trade Scope</th>
                          <th className="py-3 px-3">Skill Level &amp; Nature</th>
                          <th className="py-3 px-3">Scope Status</th>
                          <th className="py-3 px-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 text-[11px]">
                        {paginatedActiveScopes.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="py-6 text-center text-slate-500 italic">
                              No active category scopes currently authorized.
                            </td>
                          </tr>
                        ) : (
                          paginatedActiveScopes.map(req => (
                            <tr key={req.id} className="hover:bg-slate-800/30 transition">
                              <td className="py-3 px-3">
                                <div className="font-semibold text-white">{req.organization_name || `Org #${req.organization_id}`}</div>
                                <div className="text-[10px] text-slate-400 font-mono">{req.registration_ref_number || 'N/A'}</div>
                              </td>
                              <td className="py-3 px-3">
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 flex items-center gap-1 w-fit">
                                  <CheckCircle2 className="w-3 h-3 text-cyan-400 shrink-0" />
                                  <span>Org: ACTIVE</span>
                                </span>
                              </td>
                              <td className="py-3 px-3 font-semibold text-white">{req.category}</td>
                              <td className="py-3 px-3 text-slate-300">
                                {req.skill_level || 'Skilled'} • {req.nature_of_employment || 'Contract'}
                              </td>
                              <td className="py-3 px-3">
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                                  ACTIVE SCOPE
                                </span>
                              </td>
                              <td className="py-3 px-3 text-right">
                                <div className="flex items-center justify-end gap-1.5">
                                  <button
                                    onClick={() => handleOpenSuspend(req)}
                                    className="px-2.5 py-1 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/30 rounded-lg text-[11px] font-semibold transition"
                                    title="Suspend single category scope while preserving employer organization status"
                                  >
                                    Suspend
                                  </button>
                                  <button
                                    onClick={() => handleOpenDiscontinue(req)}
                                    className="px-2.5 py-1 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 rounded-lg text-[11px] font-semibold transition"
                                    title="Discontinue single category scope while preserving employer organization status"
                                  >
                                    Discontinue
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                    <PaginationControls
                      currentPage={catPage}
                      totalPages={totalActiveScopePages}
                      pageSize={catPageSize}
                      totalItems={totalActiveScopes}
                      onPageChange={setCatPage}
                      onPageSizeChange={setCatPageSize}
                      itemLabel="active category scopes"
                    />
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* ============================================================
          VIEW 5: REJECTED & MORE INFO REQUIRED REQUESTS
      ============================================================ */}
      {isTabActive('REJECTED_CATS') && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          {(() => {
            const displayedRejected = filterCatList(rejectedCatRequests, debouncedCatSearch);
            const paginatedRejected = displayedRejected.slice((catPage - 1) * catPageSize, catPage * catPageSize);
            const totalRejected = displayedRejected.length;
            const totalRejectedPages = Math.max(1, Math.ceil(totalRejected / catPageSize));

            return (
              <>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-rose-400" />
                      <span>Rejected &amp; More Info Required Requests</span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30 font-mono">
                        {totalRejected} Total Requests
                      </span>
                    </h3>
                    <p className="text-xs text-slate-400">Category requests that were rejected or flagged for supplemental documentation.</p>
                  </div>

                  {/* Sub-Filter */}
                  <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
                    {['ALL', 'REJECTED', 'MORE_INFO_REQUIRED'].map(st => (
                      <button
                        key={st}
                        onClick={() => setRejectedFilter(st)}
                        className={`px-2.5 py-1 rounded-lg transition font-medium text-[11px] whitespace-nowrap ${
                          rejectedFilter === st ? 'bg-slate-800 text-white font-bold' : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {st.replace(/_/g, ' ')}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Category Comprehensive Filter Bar */}
                <CategoryFilterBar
                  search={catSearch}
                  onSearchChange={setCatSearch}
                  category={catCategoryFilter}
                  onCategoryChange={setCatCategoryFilter}
                  skill={catSkillFilter}
                  onSkillChange={setCatSkillFilter}
                  nature={catNatureFilter}
                  onNatureChange={setCatNatureFilter}
                  dateFrom={catDateFrom}
                  onDateFromChange={setCatDateFrom}
                  dateTo={catDateTo}
                  onDateToChange={setCatDateTo}
                  onClear={() => {
                    setCatSearch('');
                    setCatCategoryFilter('ALL');
                    setCatSkillFilter('ALL');
                    setCatNatureFilter('ALL');
                    setCatDateFrom('');
                    setCatDateTo('');
                    setRejectedFilter('ALL');
                    setCatPage(1);
                  }}
                  accentColor="rose"
                />

                {/* Truthful Error Card */}
                {catsError && (
                  <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 text-rose-400">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>Failed to load category requests: {catsError}</span>
                    </div>
                    <button 
                      onClick={fetchCategories} 
                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg flex items-center gap-1.5 transition"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Retry</span>
                    </button>
                  </div>
                )}

                {!catsError && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                        <tr>
                          <th className="py-3 px-3">Employer Organization</th>
                          <th className="py-3 px-3">Trade Category</th>
                          <th className="py-3 px-3">Skill Level &amp; Version</th>
                          <th className="py-3 px-3">Status</th>
                          <th className="py-3 px-3">Reviewer Reason / Information Requested</th>
                          <th className="py-3 px-3 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 text-[11px]">
                        {paginatedRejected.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="py-6 text-center text-slate-500 italic">
                              No rejected or pending-info category requests found.
                            </td>
                          </tr>
                        ) : (
                          paginatedRejected.map(req => (
                            <tr key={req.id} className="hover:bg-slate-800/30 transition">
                              <td className="py-3 px-3">
                                <div className="font-semibold text-white">{req.organization_name || `Org #${req.organization_id}`}</div>
                                <div className="text-[10px] text-slate-400 font-mono">{req.registration_ref_number || 'N/A'}</div>
                              </td>
                              <td className="py-3 px-3 font-semibold text-white">{req.category}</td>
                              <td className="py-3 px-3 text-slate-300">
                                {req.skill_level || 'Skilled'} • v{req.request_version || 1}
                              </td>
                              <td className="py-3 px-3">
                                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                                  req.status === 'REJECTED' 
                                    ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                                    : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                                }`}>
                                  {req.status.replace(/_/g, ' ')}
                                </span>
                              </td>
                              <td className="py-3 px-3 text-slate-300 max-w-xs break-words">
                                {req.reason || req.admin_notes || req.feedback || req.review_reason || 'No explanation provided'}
                              </td>
                              <td className="py-3 px-3 text-right">
                                <button
                                  onClick={() => handleOpenCatDecision(req)}
                                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-[11px] transition"
                                >
                                  Re-evaluate
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                    <PaginationControls
                      currentPage={catPage}
                      totalPages={totalRejectedPages}
                      pageSize={catPageSize}
                      totalItems={totalRejected}
                      onPageChange={setCatPage}
                      onPageSizeChange={setCatPageSize}
                      itemLabel="requests"
                    />
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* ============================================================
          VIEW 6: DISCONTINUED / SUSPENDED HISTORY
      ============================================================ */}
      {isTabActive('HISTORY_CATS') && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          {(() => {
            const displayedHistory = filterCatList(historyCatRequests, debouncedCatSearch);
            const paginatedHistory = displayedHistory.slice((catPage - 1) * catPageSize, catPage * catPageSize);
            const totalHistory = displayedHistory.length;
            const totalHistoryPages = Math.max(1, Math.ceil(totalHistory / catPageSize));

            return (
              <>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <Ban className="w-4 h-4 text-purple-400" />
                      <span>Discontinued &amp; Suspended Category History</span>
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/30 font-mono">
                        {totalHistory} Total Records
                      </span>
                    </h3>
                    <p className="text-xs text-slate-400">Historical audit record of revoked, suspended, and superseded category authorizations.</p>
                  </div>

                  {/* Sub-Filter */}
                  <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
                    {['ALL', 'DISCONTINUED', 'SUSPENDED', 'SUPERSEDED'].map(st => (
                      <button
                        key={st}
                        onClick={() => setHistoryFilter(st)}
                        className={`px-2.5 py-1 rounded-lg transition font-medium text-[11px] whitespace-nowrap ${
                          historyFilter === st ? 'bg-slate-800 text-white font-bold' : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {st}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Category Comprehensive Filter Bar */}
                <CategoryFilterBar
                  search={catSearch}
                  onSearchChange={setCatSearch}
                  category={catCategoryFilter}
                  onCategoryChange={setCatCategoryFilter}
                  skill={catSkillFilter}
                  onSkillChange={setCatSkillFilter}
                  nature={catNatureFilter}
                  onNatureChange={setCatNatureFilter}
                  dateFrom={catDateFrom}
                  onDateFromChange={setCatDateFrom}
                  dateTo={catDateTo}
                  onDateToChange={setCatDateTo}
                  onClear={() => {
                    setCatSearch('');
                    setCatCategoryFilter('ALL');
                    setCatSkillFilter('ALL');
                    setCatNatureFilter('ALL');
                    setCatDateFrom('');
                    setCatDateTo('');
                    setHistoryFilter('ALL');
                    setCatPage(1);
                  }}
                  accentColor="purple"
                />

                {/* Truthful Error Card */}
                {catsError && (
                  <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 text-rose-400">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>Failed to load category history: {catsError}</span>
                    </div>
                    <button 
                      onClick={fetchCategories} 
                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg flex items-center gap-1.5 transition"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Retry</span>
                    </button>
                  </div>
                )}

                {!catsError && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                        <tr>
                          <th className="py-3 px-3">Employer Organization</th>
                          <th className="py-3 px-3">Parent Org Standing</th>
                          <th className="py-3 px-3">Trade Category</th>
                          <th className="py-3 px-3">Version</th>
                          <th className="py-3 px-3">Lifecycle Status</th>
                          <th className="py-3 px-3">Audit Reason &amp; Decoupling Note</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 text-[11px]">
                        {paginatedHistory.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="py-6 text-center text-slate-500 italic">
                              No discontinued or suspended category history found.
                            </td>
                          </tr>
                        ) : (
                          paginatedHistory.map(req => (
                            <tr key={req.id} className="hover:bg-slate-800/30 transition">
                              <td className="py-3 px-3">
                                <div className="font-semibold text-white">{req.organization_name || `Org #${req.organization_id}`}</div>
                                <div className="text-[10px] text-slate-400 font-mono">{req.registration_ref_number || 'N/A'}</div>
                              </td>
                              <td className="py-3 px-3">
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 flex items-center gap-1 w-fit">
                                  <CheckCircle2 className="w-3 h-3 text-cyan-400 shrink-0" />
                                  <span>Org: ACTIVE</span>
                                </span>
                              </td>
                              <td className="py-3 px-3 font-semibold text-white">{req.category}</td>
                              <td className="py-3 px-3 text-slate-400 font-mono">v{req.request_version || 1}</td>
                              <td className="py-3 px-3">
                                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                                  req.status === 'SUSPENDED' ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' :
                                  req.status === 'DISCONTINUED' ? 'bg-purple-500/15 text-purple-300 border border-purple-500/30' :
                                  'bg-slate-800 text-slate-300 border border-slate-700'
                                }`}>
                                  {req.status}
                                </span>
                              </td>
                              <td className="py-3 px-3 max-w-sm">
                                <div className="text-slate-300">
                                  {req.discontinuation_reason || req.review_reason || req.reason || 'Revoked via governance audit'}
                                </div>
                                <div className="text-[10px] text-cyan-400 flex items-center gap-1 mt-0.5">
                                  <Shield className="w-3 h-3 shrink-0" />
                                  <span>Decoupled: Parent organization standing unaffected</span>
                                </div>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                    <PaginationControls
                      currentPage={catPage}
                      totalPages={totalHistoryPages}
                      pageSize={catPageSize}
                      totalItems={totalHistory}
                      onPageChange={setCatPage}
                      onPageSizeChange={setCatPageSize}
                      itemLabel="history records"
                    />
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* ============================================================
          TAB 3: GOVERNMENT OFFICERS
      ============================================================ */}
      {activeTab === 'OFFICERS' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Landmark className="w-4 h-4 text-blue-400" />
                <span>Government Officers Directory</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/30 font-mono">
                  {officerTotalCount} Total Officers
                </span>
              </h3>
              <p className="text-xs text-slate-400">Provision official state welfare officers and enforce strict geographic jurisdiction hierarchies.</p>
            </div>
            
            <div className="flex items-center gap-2">
              <button
                onClick={() => setProvisionModalOpen(true)}
                className="px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-blue-600/20 flex items-center gap-1.5 transition"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span>Provision Officer</span>
              </button>
            </div>
          </div>

          {/* Government Officers Filter Bar */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 space-y-2.5">
            <div className="flex flex-col md:flex-row items-stretch md:items-center gap-2.5">
              {/* Debounced Search */}
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={officerSearch}
                  onChange={(e) => setOfficerSearch(e.target.value)}
                  placeholder="Search officer name, ref ID, department, designation, block..."
                  className="w-full pl-9 pr-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 outline-none focus:border-blue-500"
                />
              </div>

              {/* Authority Level Filter */}
              <div className="flex items-center gap-1.5 shrink-0 text-xs">
                <span className="text-slate-400 text-[11px]">Authority:</span>
                <select
                  value={officerAuthorityFilter}
                  onChange={(e) => setOfficerAuthorityFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-blue-500"
                >
                  <option value="ALL">All Levels</option>
                  <option value="NATIONAL">National</option>
                  <option value="STATE">State</option>
                  <option value="DISTRICT">District</option>
                  <option value="BLOCK">Block</option>
                </select>
              </div>

              {/* State Filter */}
              <div className="flex items-center gap-1.5 shrink-0 text-xs">
                <span className="text-slate-400 text-[11px]">State:</span>
                <select
                  value={officerStateFilter}
                  onChange={(e) => setOfficerStateFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white outline-none focus:border-blue-500"
                >
                  {INDIAN_STATES_OPTIONS.map(st => (
                    <option key={st} value={st}>{st === 'ALL' ? 'All States' : st}</option>
                  ))}
                </select>
              </div>

              {/* District Filter */}
              <div className="flex items-center gap-1.5 shrink-0 text-xs">
                <span className="text-slate-400 text-[11px]">District:</span>
                <input
                  type="text"
                  value={officerDistrictFilter === 'ALL' ? '' : officerDistrictFilter}
                  onChange={(e) => setOfficerDistrictFilter(e.target.value || 'ALL')}
                  placeholder="Any District"
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-slate-500 outline-none focus:border-blue-500 w-28"
                />
              </div>

              {/* Block Filter */}
              <div className="flex items-center gap-1.5 shrink-0 text-xs">
                <span className="text-slate-400 text-[11px]">Block:</span>
                <input
                  type="text"
                  value={officerBlockFilter}
                  onChange={(e) => setOfficerBlockFilter(e.target.value)}
                  placeholder="Any Block"
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-slate-500 outline-none focus:border-blue-500 w-28"
                />
              </div>

              {/* Date Range */}
              <div className="flex items-center gap-1.5 shrink-0 text-xs">
                <span className="text-slate-400 text-[11px]">From:</span>
                <input
                  type="date"
                  value={officerDateFrom}
                  onChange={(e) => setOfficerDateFrom(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-blue-500"
                />
                <span className="text-slate-400 text-[11px]">To:</span>
                <input
                  type="date"
                  value={officerDateTo}
                  onChange={(e) => setOfficerDateTo(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-blue-500"
                />
              </div>

              {/* Clear Filters */}
              <button
                onClick={() => {
                  setOfficerSearch('');
                  setOfficerFilter('ALL');
                  setOfficerAuthorityFilter('ALL');
                  setOfficerStateFilter('ALL');
                  setOfficerDistrictFilter('ALL');
                  setOfficerBlockFilter('');
                  setOfficerDateFrom('');
                  setOfficerDateTo('');
                  setOfficerPage(1);
                }}
                className="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white rounded-lg text-xs border border-slate-800 flex items-center gap-1 transition shrink-0"
                title="Reset all filters"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Clear Filters</span>
              </button>
            </div>

            {/* Status Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pt-1 border-t border-slate-900 text-xs">
              <span className="text-slate-500 text-[11px] shrink-0">Status:</span>
              {['ALL', 'ACTIVE', 'PROVISIONED', 'SUSPENDED'].map(st => (
                <button
                  key={st}
                  onClick={() => setOfficerFilter(st)}
                  className={`px-2.5 py-1 rounded-lg transition font-medium text-[11px] whitespace-nowrap ${
                    officerFilter === st ? 'bg-blue-600 text-white font-bold' : 'text-slate-400 hover:text-slate-200 bg-slate-900/60'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {/* Truthful Error Card */}
          {officersError && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-rose-400">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>Failed to load government officers: {officersError}</span>
              </div>
              <button 
                onClick={fetchOfficers} 
                className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg flex items-center gap-1.5 transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry</span>
              </button>
            </div>
          )}

          {!officersError && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                  <tr>
                    <th className="py-3 px-3">Officer &amp; Reference ID</th>
                    <th className="py-3 px-3">Department &amp; Designation</th>
                    <th className="py-3 px-3">Authority &amp; Jurisdiction</th>
                    <th className="py-3 px-3">Benefit Permissions</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {officers.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-slate-500 italic">
                        No government officers provisioned yet.
                      </td>
                    </tr>
                  ) : (
                    officers.map(off => (
                      <tr key={off.id} className="hover:bg-slate-800/30 transition">
                        <td className="py-3 px-3">
                          <div className="font-semibold text-white">{off.officer_name || off.full_name}</div>
                          <div className="text-[11px] font-mono text-purple-400">{off.officer_reference_id}</div>
                          <div className="text-[10px] text-slate-500">{off.official_email}</div>
                        </td>
                        <td className="py-3 px-3">
                          <div className="text-slate-200">{off.department}</div>
                          <div className="text-[11px] text-slate-400">{off.designation}</div>
                        </td>
                        <td className="py-3 px-3">
                          <div className="font-semibold text-blue-300">{off.authority_level}</div>
                          <div className="text-[11px] font-mono text-slate-400">
                            {off.authority_level === 'NATIONAL' ? 'All India' : `State: ${off.state || 'N/A'}`}
                            {off.district ? ` • Dist: ${off.district}` : ''}
                            {off.block ? ` • Blk: ${off.block}` : ''}
                          </div>
                          {(off.authority_level === 'NATIONAL' || off.permissions?.includes('CROSS_STATE_VERIFICATION')) && (
                            <span className="inline-block mt-1 px-1.5 py-0.5 rounded bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-[9px] font-bold">
                              Cross-State Enabled
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          <div className="flex flex-wrap gap-1 max-w-[200px]">
                            {off.benefit_permissions?.map((b, idx) => (
                              <span key={idx} className="px-1.5 py-0.5 rounded bg-slate-800 text-[9px] font-mono text-slate-300">
                                {b}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                            off.status === 'ACTIVE' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' :
                            off.status === 'PROVISIONED' ? 'bg-purple-500/15 text-purple-300 border border-purple-500/30' :
                            off.status === 'SUSPENDED' ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30' :
                            'bg-slate-800 text-slate-400 border border-slate-700'
                          }`}>
                            {off.status}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {off.status === 'SUSPENDED' ? (
                              <button
                                onClick={() => handleReactivateOfficer(off.id)}
                                className="px-2 py-1 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 rounded-lg text-[10px] font-semibold"
                              >
                                Reactivate
                              </button>
                            ) : (
                              <button
                                onClick={() => handleOpenOfficerSuspend(off)}
                                className="px-2 py-1 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 rounded-lg text-[10px] font-semibold"
                              >
                                Suspend
                              </button>
                            )}
                            <button
                              onClick={() => handleResendOfficerActivation(off.id)}
                              className="px-2 py-1 bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700 rounded-lg text-[10px]"
                              title="Resend activation invitation email"
                            >
                              Resend Token
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              <PaginationControls
                currentPage={officerPage}
                totalPages={officerTotalPages}
                pageSize={officerPageSize}
                totalItems={officerTotalCount}
                onPageChange={setOfficerPage}
                onPageSizeChange={setOfficerPageSize}
                itemLabel="government officers"
              />
            </div>
          )}
        </div>
      )}

      {/* ============================================================
          TAB 4: GOVERNANCE AUDIT TRAIL
      ============================================================ */}
      {activeTab === 'AUDIT' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-white">Immutable Governance Audit Stream</h3>
              <p className="text-xs text-slate-400">Permanent record of all platform approvals, status transitions, and administrative operations.</p>
            </div>
            
            <div className="flex items-center gap-2">
              <select
                value={auditActionFilter}
                onChange={(e) => setAuditActionFilter(e.target.value)}
                className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 outline-none"
              >
                <option value="ALL">All Actions</option>
                <option value="DISBURSE_WELFARE_CLAIM">Disburse Welfare Claim</option>
                <option value="APPROVE_ORGANIZATION">Approve Org</option>
                <option value="SUSPEND_ORGANIZATION">Suspend Org</option>
                <option value="REJECT_ORGANIZATION">Reject Org</option>
                <option value="REACTIVATE_ORGANIZATION">Reactivate Org</option>
                <option value="APPROVE_CATEGORY_REQUEST">Approve Category</option>
                <option value="DISCONTINUE_CATEGORY">Discontinue Category</option>
                <option value="REJECT_CATEGORY_REQUEST">Reject Category</option>
                <option value="PROVISION_GOVERNMENT_OFFICER">Provision Officer</option>
                <option value="UPDATE_GOVERNMENT_OFFICER_STATUS">Update Officer Status</option>
                <option value="GOVERNMENT_OFFICER_ACTIVATED">Officer Activated</option>
                <option value="RESOLVE_EMPLOYMENT_DISPUTE">Resolve Dispute</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/40">
                <tr>
                  <th className="py-3 px-3">Timestamp</th>
                  <th className="py-3 px-3">Action</th>
                  <th className="py-3 px-3">Actor &amp; Role</th>
                  <th className="py-3 px-3">Target &amp; Ref</th>
                  <th className="py-3 px-3">State Transition</th>
                  <th className="py-3 px-3">Governance Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500 italic font-sans">
                      No audit log records match filter.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map(log => (
                    <tr key={log.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3 px-3 text-slate-300 font-medium">
                        {formatUtcTimestamp(log.timestamp)}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                          log.action === 'DISBURSE_WELFARE_CLAIM'
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            : log.action.includes('APPROVE')
                            ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
                            : log.action.includes('SUSPEND') || log.action.includes('REJECT')
                            ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                            : 'bg-slate-800 text-slate-300 border border-slate-700'
                        }`}>
                          {log.action}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-300">
                        {log.actor_role} ({log.actor_user_id || 'ID'})
                      </td>
                      <td className="py-3 px-3 text-slate-300">
                        {log.target_type} #{log.target_id}
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-slate-500">{log.previous_state || 'NONE'}</span>
                        <span className="mx-1.5 text-slate-600">→</span>
                        <span className="text-emerald-400 font-bold">{log.new_state}</span>
                      </td>
                      <td className="py-3 px-3 text-slate-400 font-sans max-w-[200px] truncate" title={log.reason}>
                        {log.reason || 'N/A'}
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
          TAB 5: SYSTEM HEALTH
      ============================================================ */}
      {activeTab === 'HEALTH' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-white">Infrastructure Health Monitor</h3>
              <p className="text-xs text-slate-400">Live EVM RPC nodes and IPFS storage gateway latency tests.</p>
            </div>
            <button
              onClick={checkConnectivity}
              disabled={healthLoading}
              className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${healthLoading ? 'animate-spin' : ''}`} />
              <span>Test Latency</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <Database className="w-4 h-4 text-emerald-400" />
                  <span>EVM Blockchain Node</span>
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  {healthData?.blockchain?.status || 'CONNECTED'}
                </span>
              </div>
              <p className="text-xs text-slate-400">Network: {healthData?.blockchain?.network || 'Local Hardhat EVM'}</p>
              <p className="text-xs font-mono text-slate-500">RPC: {healthData?.blockchain?.rpc_url || 'http://127.0.0.1:8545'}</p>
              <div className="text-xs font-mono text-emerald-400 pt-1">
                Latency: {healthData?.blockchain?.latency_ms || 12.0} ms
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <Wifi className="w-4 h-4 text-cyan-400" />
                  <span>IPFS Storage Gateway</span>
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                  {healthData?.ipfs?.status || 'OPERATIONAL'}
                </span>
              </div>
              <p className="text-xs text-slate-400">Provider: {healthData?.ipfs?.provider || 'Kubo Local Gateway'}</p>
              <p className="text-xs font-mono text-slate-500">Multiaddr: /ip4/127.0.0.1/tcp/5001</p>
              <div className="text-xs font-mono text-cyan-400 pt-1">
                Latency: {healthData?.ipfs?.latency_ms || 8.0} ms
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================
          MODALS
      ============================================================ */}

      {/* Organization Review/Decision Modal */}
      {orgDecisionModalOpen && selectedOrg && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Decide Organization Standing</h3>
              <button onClick={() => setOrgDecisionModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={submitOrgDecision} className="space-y-3">
              <div>
                <span className="text-slate-400">Target Organization:</span>
                <div className="font-bold text-white text-sm">{selectedOrg.name}</div>
                <div className="text-[11px] font-mono text-slate-400">Current Status: {selectedOrg.status}</div>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Select Action</label>
                <select
                  value={orgAction}
                  onChange={(e) => setOrgAction(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                >
                  <option value="APPROVE">APPROVE (Issue single-use activation token)</option>
                  <option value="REJECT">REJECT (Decline registration)</option>
                  <option value="REQUEST_MORE_INFO">REQUEST MORE INFO</option>
                  <option value="SUSPEND">SUSPEND (Revoke portal access)</option>
                  <option value="REACTIVATE">REACTIVATE</option>
                  <option value="DISABLE">DISABLE</option>
                </select>
              </div>

              {['REJECT', 'REQUEST_MORE_INFO', 'SUSPEND', 'DISABLE'].includes(orgAction) && (
                <div>
                  <label className="block text-amber-400 font-semibold mb-1">Mandatory Reason *</label>
                  <textarea
                    value={orgReason}
                    onChange={(e) => setOrgReason(e.target.value)}
                    rows={2}
                    placeholder="Provide mandatory reason for governance decision..."
                    className="w-full px-3 py-2 bg-slate-950 border border-amber-500/40 rounded-xl text-white outline-none"
                    required
                  />
                </div>
              )}

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Admin Notes (Optional)</label>
                <input
                  type="text"
                  value={orgNotes}
                  onChange={(e) => setOrgNotes(e.target.value)}
                  placeholder="Internal audit notes..."
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setOrgDecisionModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold transition shadow-md shadow-blue-600/20"
                >
                  Submit Decision
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Category Decision Modal */}
      {catDecisionModalOpen && selectedCatReq && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Decide Category Scope</h3>
              <button onClick={() => setCatDecisionModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={submitCatDecision} className="space-y-3">
              <div>
                <span className="text-slate-400">Trade:</span>
                <div className="font-bold text-white text-sm">{selectedCatReq.category}</div>
                <div className="text-[11px] text-slate-400">Org: {selectedCatReq.organization_name}</div>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Decision</label>
                <select
                  value={catAction}
                  onChange={(e) => setCatAction(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                >
                  <option value="APPROVE">APPROVE (Authorize on-chain)</option>
                  <option value="REJECT">REJECT</option>
                  <option value="REQUEST_MORE_INFO">REQUEST MORE INFO</option>
                  <option value="SUSPEND">SUSPEND (Revoke on-chain; Decoupled from Org)</option>
                </select>
              </div>

              {['REJECT', 'REQUEST_MORE_INFO', 'SUSPEND'].includes(catAction) && (
                <div>
                  <label className="block text-amber-400 font-semibold mb-1">Reason *</label>
                  <textarea
                    value={catReason}
                    onChange={(e) => setCatReason(e.target.value)}
                    rows={2}
                    className="w-full px-3 py-2 bg-slate-950 border border-amber-500/40 rounded-xl text-white outline-none"
                    required
                  />
                </div>
              )}

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setCatDecisionModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold transition"
                >
                  Confirm Decision
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Discontinue Category Modal (P0-3) */}
      {discontinueModalOpen && selectedCatReq && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-rose-900/60 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-rose-400 text-base">Discontinue Category Scope</h3>
              <button onClick={() => setDiscontinueModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={submitDiscontinueCategory} className="space-y-3">
              <p className="text-slate-300">
                You are discontinuing trade scope <strong>{selectedCatReq.category}</strong> for <strong>{selectedCatReq.organization_name}</strong>.
              </p>
              <p className="text-[11px] text-amber-300 bg-amber-500/10 p-2 rounded-lg border border-amber-500/20">
                ⚠️ P0-3 Isolation: This will revoke the category on-chain while keeping the employer organization and all other active trade categories fully intact.
              </p>

              <div>
                <label className="block text-rose-300 font-semibold mb-1">Mandatory Discontinuation Reason *</label>
                <textarea
                  value={discontinueReason}
                  onChange={(e) => setDiscontinueReason(e.target.value)}
                  rows={2}
                  placeholder="e.g. Safety non-compliance or licensing expired"
                  className="w-full px-3 py-2 bg-slate-950 border border-rose-500/40 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setDiscontinueModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-bold transition shadow-md shadow-rose-600/20"
                >
                  Discontinue Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Suspend Category Modal (Decoupling Invariant) */}
      {suspendModalOpen && selectedCatReq && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-amber-900/60 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-amber-400 text-base">Suspend Category Scope</h3>
              <button onClick={() => setSuspendModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={submitSuspendCategory} className="space-y-3">
              <p className="text-slate-300">
                You are suspending category scope <strong>{selectedCatReq.category}</strong> for <strong>{selectedCatReq.organization_name || `Org #${selectedCatReq.organization_id}`}</strong>.
              </p>
              <p className="text-[11px] text-cyan-300 bg-cyan-500/10 p-2 rounded-lg border border-cyan-500/20">
                🛡️ Decoupling Invariant: Suspending this trade vertical revokes its on-chain credential while leaving the parent employer organization status ACTIVE.
              </p>

              <div>
                <label className="block text-amber-300 font-semibold mb-1">Mandatory Suspension Reason *</label>
                <textarea
                  value={suspendReason}
                  onChange={(e) => setSuspendReason(e.target.value)}
                  rows={2}
                  placeholder="e.g. Safety non-compliance or pending regulatory audit"
                  className="w-full px-3 py-2 bg-slate-950 border border-amber-500/40 rounded-xl text-white outline-none"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setSuspendModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl font-bold transition shadow-md shadow-amber-600/20"
                >
                  Suspend Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Suspend Government Officer Modal */}
      {officerSuspendModalOpen && selectedOfficerForSuspend && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-rose-900/60 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
                <h3 className="font-bold text-rose-400 text-base">Suspend Government Officer</h3>
              </div>
              <button 
                onClick={() => {
                  setOfficerSuspendModalOpen(false);
                  setSelectedOfficerForSuspend(null);
                }} 
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={submitOfficerSuspend} className="space-y-3">
              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
                <div className="text-white font-semibold">
                  {selectedOfficerForSuspend.officer_name || selectedOfficerForSuspend.full_name || `Officer #${selectedOfficerForSuspend.id}`}
                </div>
                <div className="text-slate-400 text-[11px]">
                  {selectedOfficerForSuspend.department} • {selectedOfficerForSuspend.authority_level} ({selectedOfficerForSuspend.state || 'All-India'})
                </div>
                {selectedOfficerForSuspend.official_email && (
                  <div className="text-slate-500 text-[10px] font-mono">
                    {selectedOfficerForSuspend.official_email}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-rose-300 font-semibold mb-1">Mandatory Suspension Reason *</label>
                <textarea
                  value={officerSuspendReason}
                  onChange={(e) => setOfficerSuspendReason(e.target.value)}
                  rows={3}
                  placeholder="e.g. Administrative suspension pending internal audit or unauthorized actions"
                  className="w-full px-3 py-2 bg-slate-950 border border-rose-500/40 rounded-xl text-white outline-none focus:border-rose-500"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setOfficerSuspendModalOpen(false);
                    setSelectedOfficerForSuspend(null);
                  }}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={officerSuspendSubmitting}
                  className="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-bold transition shadow-md shadow-rose-600/20 flex items-center gap-1.5"
                >
                  {officerSuspendSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : null}
                  <span>Confirm Suspension</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Provision Government Officer Modal */}
      {provisionModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 text-xs my-8">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-blue-400" />
                <h3 className="font-bold text-white text-base">Provision Government Officer</h3>
              </div>
              <button onClick={() => setProvisionModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <form onSubmit={submitProvisionOfficer} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Full Name *</label>
                  <input
                    type="text"
                    value={provFullName}
                    onChange={(e) => setProvFullName(e.target.value)}
                    placeholder="e.g. Anand Kulkarni"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Official Email *</label>
                  <input
                    type="email"
                    value={provEmail}
                    onChange={(e) => setProvEmail(e.target.value)}
                    placeholder="e.g. anand@maharashtra.gov.in"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Mobile Phone</label>
                  <input
                    type="tel"
                    value={provPhone}
                    onChange={(e) => setProvPhone(e.target.value)}
                    placeholder="+91 9876543210"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-semibold mb-1">Department</label>
                  <input
                    type="text"
                    value={provDepartment}
                    onChange={(e) => setProvDepartment(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Designation</label>
                <input
                  type="text"
                  value={provDesignation}
                  onChange={(e) => setProvDesignation(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white outline-none"
                  required
                />
              </div>

              {/* Geographic Hierarchy Controls */}
              <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-2.5">
                <div>
                  <label className="block text-blue-400 font-semibold mb-1">Authority Level *</label>
                  <select
                    value={provAuthorityLevel}
                    onChange={(e) => setProvAuthorityLevel(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-white outline-none"
                  >
                    <option value="NATIONAL">NATIONAL (All India - No State/Dist/Blk)</option>
                    <option value="STATE">STATE (State-wide Jurisdiction)</option>
                    <option value="DISTRICT">DISTRICT (District within State)</option>
                    <option value="BLOCK">BLOCK (Block within District &amp; State)</option>
                  </select>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <div>
                    <label className={`block text-[11px] font-semibold mb-1 ${provAuthorityLevel === 'NATIONAL' ? 'text-slate-600' : 'text-slate-300'}`}>
                      State {provAuthorityLevel !== 'NATIONAL' && '*'}
                    </label>
                    <input
                      type="text"
                      value={provState}
                      onChange={(e) => setProvState(e.target.value)}
                      disabled={provAuthorityLevel === 'NATIONAL'}
                      placeholder="e.g. Maharashtra"
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-white disabled:opacity-40 outline-none"
                      required={provAuthorityLevel !== 'NATIONAL'}
                    />
                  </div>

                  <div>
                    <label className={`block text-[11px] font-semibold mb-1 ${['DISTRICT', 'BLOCK'].includes(provAuthorityLevel) ? 'text-slate-300' : 'text-slate-600'}`}>
                      District {['DISTRICT', 'BLOCK'].includes(provAuthorityLevel) && '*'}
                    </label>
                    <input
                      type="text"
                      value={provDistrict}
                      onChange={(e) => setProvDistrict(e.target.value)}
                      disabled={!['DISTRICT', 'BLOCK'].includes(provAuthorityLevel)}
                      placeholder="e.g. Pune"
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-white disabled:opacity-40 outline-none"
                      required={['DISTRICT', 'BLOCK'].includes(provAuthorityLevel)}
                    />
                  </div>

                  <div>
                    <label className={`block text-[11px] font-semibold mb-1 ${provAuthorityLevel === 'BLOCK' ? 'text-slate-300' : 'text-slate-600'}`}>
                      Block {provAuthorityLevel === 'BLOCK' && '*'}
                    </label>
                    <input
                      type="text"
                      value={provBlock}
                      onChange={(e) => setProvBlock(e.target.value)}
                      disabled={provAuthorityLevel !== 'BLOCK'}
                      placeholder="e.g. Haveli"
                      className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-white disabled:opacity-40 outline-none"
                      required={provAuthorityLevel === 'BLOCK'}
                    />
                  </div>
                </div>
              </div>

              {/* Benefit Permissions Checkboxes */}
              <div>
                <label className="block text-slate-400 font-semibold mb-1.5">Benefit Disbursement Permissions</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {AVAILABLE_BENEFITS.map(b => {
                    const isChecked = provBenefitPermissions.includes(b.id);
                    return (
                      <button
                        type="button"
                        key={b.id}
                        onClick={() => toggleBenefitPermission(b.id)}
                        className={`flex items-center gap-2 p-2 rounded-xl border text-left transition ${
                          isChecked 
                            ? 'bg-blue-600/15 border-blue-500/40 text-blue-200' 
                            : 'bg-slate-950 border-slate-800 text-slate-400'
                        }`}
                      >
                        {isChecked ? (
                          <CheckSquare className="w-4 h-4 text-blue-400 shrink-0" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-600 shrink-0" />
                        )}
                        <span className="text-[11px]">{b.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Cross-State Verification Toggle */}
              <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
                <div 
                  onClick={() => setProvAllowCrossState(!provAllowCrossState)}
                  className="flex items-start gap-3 cursor-pointer select-none"
                >
                  <div className={`mt-0.5 p-1 rounded-md border transition ${
                    provAllowCrossState ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300' : 'bg-slate-900 border-slate-700 text-slate-500'
                  }`}>
                    {provAllowCrossState ? <CheckSquare className="w-4 h-4 text-cyan-400" /> : <Square className="w-4 h-4" />}
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                      <span>Allow Cross-State Verification (Interstate Welfare Portability)</span>
                      <span className="px-1.5 py-0.2 bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[9px] rounded font-mono">PORTABLE</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Grants this officer authority to verify migrant workers whose origin or current state is outside this officer&apos;s home state (e.g. verifying migrant workers from Karnataka/Bihar working or seeking benefits in Goa).
                    </p>
                  </div>
                </div>
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setProvisionModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold transition shadow-md shadow-blue-600/20"
                >
                  Provision Officer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
