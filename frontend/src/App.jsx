import React, { lazy, Suspense, useState, useEffect } from 'react';
import './index.css';
import Layout from './components/Layout';
import CitizenPortalHome from './pages/CitizenPortalHome';
import PublicPortalHeader from './components/public/PublicPortalHeader';
import SiscAIChatbot from './components/SiscAIChatbot';
import { loadPublicDashboard } from './utils/publicDashboardCache';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const MapPage = lazy(() => import('./pages/MapPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const DataPage = lazy(() => import('./pages/DataPage'));
const PublicDashboard = lazy(() => import('./pages/PublicDataExplorer'));
const PublicInformation = lazy(() => import('./pages/PublicInformation'));
const PublicMeasures = lazy(() => import('./pages/PublicMeasures'));
const PublicInspectionManagement = lazy(() => import('./pages/PublicInspectionManagement'));
const PublicFamilyProtection = lazy(() => import('./pages/PublicFamilyProtection'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const PQRPage = lazy(() => import('./pages/PQRPage'));
const VictimRoutes = lazy(() => import('./pages/VictimRoutes'));
const SecureReporting = lazy(() => import('./pages/SecureReporting'));
const CommunityParticipation = lazy(() => import('./pages/CommunityParticipation'));
const IntelligenceModule = lazy(() => import('./pages/IntelligenceModule'));
const DataQuality = lazy(() => import('./pages/DataQuality'));


const UniversalIngesta = lazy(() => import('./pages/UniversalIngesta'));
const InstitutionalAgents = lazy(() => import('./pages/InstitutionalAgents'));
const StatsModule = lazy(() => import('./pages/StatsModule'));
const SourceCenter = lazy(() => import('./pages/SourceCenter'));
const PoliceWeeklyExplorer = lazy(() => import('./pages/PoliceWeeklyExplorer'));
const SiscCifras = lazy(() => import('./pages/SiscCifras'));
const RegionalContext = lazy(() => import('./pages/RegionalContext'));
const RNMCModule = lazy(() => import('./pages/RNMCModule'));
const AlertsFeed = lazy(() => import('./pages/AlertsFeed'));
const UsersManagement = lazy(() => import('./pages/UsersManagement'));
const AccessRequests = lazy(() => import('./pages/AccessRequests'));
const AuditLog = lazy(() => import('./pages/AuditLog'));
const InspeccionesModule = lazy(() => import('./pages/InspeccionesModule'));
const PoliceIngestionAudit = lazy(() => import('./pages/PoliceIngestionAudit'));

const PageLoading = () => (
  <div className="flex min-h-[45vh] items-center justify-center bg-slate-50">
    <div className="text-center">
      <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-[#281FD0]" />
      <p className="text-[10px] font-black uppercase tracking-widest text-slate-500">Cargando contenido</p>
    </div>
  </div>
);

const PUBLIC_PAGE_META = {
  hub: ['SISC Jamundí | Seguridad y convivencia', 'Información oficial para entender la seguridad y convivencia en Jamundí.'],
  transparency: ['Explorar datos | SISC Jamundí', 'Consulta tendencias, comparaciones y datos territoriales agregados de Jamundí.'],
  'sisc-cifras': ['SISC en cifras | SISC Jamundí', 'Genera y descarga piezas visuales institucionales con cifras agregadas del periodo.'],
  'technical-bulletins': ['Boletines | SISC Jamundí', 'Consulta boletines técnicos públicos del SISC Jamundí.'],
  'open-data': ['Datos abiertos | SISC Jamundí', 'Descarga información pública agregada en formatos CSV, JSON y XLSX.'],
  'transparency-info': ['Metodología y fuentes | SISC Jamundí', 'Conoce las fuentes, fechas de corte, metodología y límites de las cifras públicas.'],
};

const App = () => {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [userRoles, setUserRoles] = useState([]);
  const [dataLevel, setDataLevel] = useState(1);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [appMode, setAppMode] = useState('loading'); // Nuevo estado inicial
  const [activePage, setActivePage] = useState('dashboard');
  const [publicActivePage, setPublicActivePage] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('page') || 'hub';
  });
  const [isLoading, setIsLoading] = useState(true);
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [selectedDataset, setSelectedDataset] = useState({ code: 'SECUESTRO', label: 'Secuestro' });
  const [rnmcFilters, setRnmcFilters] = useState(null);

  const navigatePublic = (page, options = {}) => {
    const nextPage = page || 'hub';
    const params = new URLSearchParams(window.location.search);
    if (nextPage === 'hub') params.delete('page');
    else params.set('page', nextPage);
    const query = params.toString();
    const hash = options.hash ? `#${options.hash}` : '';
    window.history.pushState({ page: nextPage }, '', `${window.location.pathname}${query ? `?${query}` : ''}${hash}`);
    setPublicActivePage(nextPage);
    window.setTimeout(() => {
      if (options.hash) document.getElementById(options.hash)?.scrollIntoView({ block: 'start' });
      else window.scrollTo({ top: 0, behavior: 'auto' });
    }, 0);
  };

  const handleIngestDataset = (code, label) => {
    setSelectedDataset({ code, label });
    setActivePage('ingesta_universal');
  };

  useEffect(() => {
    const initApp = () => {
      const storedToken = localStorage.getItem('token');
      if (storedToken) {
        try {
          const roles = JSON.parse(localStorage.getItem('userRoles') || '[]');
          const dl = parseInt(localStorage.getItem('dataLevel') || '1');
          setToken(storedToken);
          setUserRoles(roles);
          setDataLevel(dl);
          setIsAuthenticated(true);
          setAppMode('authenticated');
        } catch (e) {
          localStorage.clear();
          setAppMode('public');
        }
      } else {
        setAppMode('public');
      }
      setIsLoading(false);
    };
    initApp();
  }, []);

  useEffect(() => {
    if (appMode !== 'public' || publicActivePage !== 'hub') return;
    loadPublicDashboard({ minLocationCount: 3, includeMap: false }).catch(() => {});
  }, [appMode, publicActivePage]);

  useEffect(() => {
    const onPopState = () => {
      const params = new URLSearchParams(window.location.search);
      setPublicActivePage(params.get('page') || 'hub');
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    if (appMode !== 'public') return;
    const [title, description] = PUBLIC_PAGE_META[publicActivePage] || PUBLIC_PAGE_META.hub;
    document.title = title;
    const setContent = (selector, value) => document.querySelector(selector)?.setAttribute('content', value);
    setContent('meta[name="description"]', description);
    setContent('meta[property="og:title"]', title);
    setContent('meta[property="og:description"]', description);
    setContent('meta[property="og:url"]', window.location.href);
    setContent('meta[name="twitter:title"]', title);
    setContent('meta[name="twitter:description"]', description);
    const canonicalUrl = new URL(window.location.pathname, window.location.origin);
    if (publicActivePage !== 'hub') canonicalUrl.searchParams.set('page', publicActivePage);
    document.querySelector('link[rel="canonical"]')?.setAttribute('href', canonicalUrl.toString());
  }, [appMode, publicActivePage]);

  const handleLoginSuccess = (newToken, roles, dl) => {
    setToken(newToken);
    setUserRoles(roles || []);
    setDataLevel(dl || 1);
    setIsAuthenticated(true);
    setAppMode('authenticated');
    setActivePage('dashboard');
    localStorage.setItem('token', newToken);
    localStorage.setItem('userRoles', JSON.stringify(roles || []));
    localStorage.setItem('dataLevel', (dl || 1).toString());
  };

  const handleLogout = () => {
    localStorage.clear();
    setToken(null);
    setIsAuthenticated(false);
    setUserRoles([]);
    setAppMode('public');
    navigatePublic('hub');
    setActivePage('dashboard');
  };

  if (isLoading || appMode === 'loading') {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-slate-500 font-medium font-display uppercase tracking-widest text-[10px]">Iniciando SISC Jamundí...</p>
        </div>
      </div>
    );
  }

  if (appMode === 'login') {
    return (
      <Suspense fallback={<PageLoading />}>
        <LoginPage
          onLoginSuccess={handleLoginSuccess}
          onBackClick={() => setAppMode('public')}
        />
      </Suspense>
    );
  }

  const isPublic = appMode === 'public';
  const showCitizenAssistant = isPublic;

  const renderContent = () => {
    if (isPublic) {
      switch (publicActivePage) {
        case 'hub':
          return <CitizenPortalHome
            onNavigate={navigatePublic}
            onLoginClick={() => setAppMode('login')}
          />;
        case 'transparency':
          return <PublicDashboard
            onLoginClick={() => setAppMode('login')}
            onBack={() => navigatePublic('hub')}
            onNavigate={navigatePublic}
          />;
        case 'transparency-info':
        case 'open-data':
        case 'technical-bulletins':
        case 'accountability':
          return <PublicInformation
            initialSection={publicActivePage}
            onBack={() => navigatePublic('hub')}
            onNavigate={navigatePublic}
            onLoginClick={() => setAppMode('login')}
          />;
        case 'sisc-cifras':
          return <>
            <PublicPortalHeader currentPage="sisc-cifras" onNavigate={navigatePublic} onLoginClick={() => setAppMode('login')} />
            <SiscCifras publicMode />
          </>;
        case 'public-measures':
          return <PublicMeasures onBack={() => navigatePublic('hub')} />;
        case 'public-inspections':
          return <PublicInspectionManagement onBack={() => navigatePublic('hub')} onNavigate={navigatePublic} />;
        case 'public-family-protection':
          return <PublicFamilyProtection onBack={() => navigatePublic('hub')} />;
        case 'victim-support':
          return <VictimRoutes onBack={() => navigatePublic('hub')} />;
        case 'reporting':
          return <SecureReporting onBack={() => navigatePublic('hub')} />;
        case 'participation':
          return <CommunityParticipation onBack={() => navigatePublic('hub')} />;
        case 'educational':
          return <div className="p-20 text-center">Módulo Educativo en Desarrollo</div>;
        case 'pqr':
          return <PQRPage onBack={() => navigatePublic('hub')} />;
        default:
          return <CitizenPortalHome
            onNavigate={navigatePublic}
            onLoginClick={() => setAppMode('login')}
          />;
      }
    }

    switch (activePage) {
      case 'dashboard':
        return <Dashboard userRoles={userRoles} dataLevel={dataLevel} onNavigate={setActivePage} />;
      case 'users':
        return <UsersManagement />;
      case 'access_requests':
        return <AccessRequests userRoles={userRoles} />;
      case 'audit':
        return <AuditLog />;
      case 'map':
        return <MapPage />;
      case 'reports':
        return <ReportsPage />;
      case 'data':
        return <DataPage userRoles={userRoles} />;
      case 'sources':
      case 'monitoring':
      case 'police_monitor':
        return <SourceCenter onIngest={handleIngestDataset} userRoles={userRoles} />;
      case 'police_explorer':
        return <PoliceWeeklyExplorer />;
      case 'sisc_cifras':
        return <SiscCifras />;

      case 'intelligence':
        return <IntelligenceModule />;
      case 'regional_context':
        return <RegionalContext />;
      case 'stats':
        return <StatsModule userRoles={userRoles} dataLevel={dataLevel} />;
      case 'alerts':
        return <AlertsFeed onPageChange={setActivePage} setExternalFilters={setRnmcFilters} />;
      case 'rnmc':
        return <RNMCModule externalFilters={rnmcFilters} clearExternalFilters={() => setRnmcFilters(null)} />;
      case 'dq':
        return <DataQuality initialReportId={selectedReportId} />;
      case 'inspecciones':
        return <InspeccionesModule />;
      case 'police_audit':
        return <PoliceIngestionAudit runId={selectedReportId} onBack={() => setActivePage('ingesta_universal')} />;
      case 'institutional_agents':
        return <InstitutionalAgents />;
      case 'ingesta_universal':
        return <UniversalIngesta
          setActivePage={setActivePage}
          setReportId={setSelectedReportId}
          datasetCode={selectedDataset?.code || "SECUESTRO"}
          label={selectedDataset?.label || "Secuestro"}
        />;
      default:
        return <Dashboard />;
    }
  };

  if (isPublic) {
    return (
      <>
        <div className="min-h-screen animate-fade-in">
          <Suspense fallback={<PageLoading />}>{renderContent()}</Suspense>
        </div>
        {showCitizenAssistant && (
          <Suspense fallback={null}>
            <SiscAIChatbot />
          </Suspense>
        )}
      </>
    );
  }

  return (
    <Layout
      activePage={activePage}
      setActivePage={setActivePage}
      onLogout={handleLogout}
      isPublic={isPublic}
      userRoles={userRoles}
      dataLevel={dataLevel}
    >
      <div className="animate-fade-in h-full">
        <Suspense fallback={<PageLoading />}>{renderContent()}</Suspense>
      </div>
    </Layout>
  );
};

export default App;




