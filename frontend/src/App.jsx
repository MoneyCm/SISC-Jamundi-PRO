import React, { lazy, Suspense, useState, useEffect } from 'react';
import './index.css';
import Layout from './components/Layout';
import CitizenPortalHub from './pages/CitizenPortalHub';
import SiscAIChatbot from './components/SiscAIChatbot';
import { loadPublicDashboard } from './utils/publicDashboardCache';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const MapPage = lazy(() => import('./pages/MapPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const DataPage = lazy(() => import('./pages/DataPage'));
const PublicDashboard = lazy(() => import('./pages/PublicDashboard'));
const PublicInformation = lazy(() => import('./pages/PublicInformation'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const PQRPage = lazy(() => import('./pages/PQRPage'));
const VictimRoutes = lazy(() => import('./pages/VictimRoutes'));
const SecureReporting = lazy(() => import('./pages/SecureReporting'));
const CommunityParticipation = lazy(() => import('./pages/CommunityParticipation'));
const IntelligenceModule = lazy(() => import('./pages/IntelligenceModule'));
const DataQuality = lazy(() => import('./pages/DataQuality'));


const UniversalIngesta = lazy(() => import('./pages/UniversalIngesta'));
const StatsModule = lazy(() => import('./pages/StatsModule'));
const MindefensaMonitor = lazy(() => import('./pages/MindefensaMonitor'));
const PoliceMonitor = lazy(() => import('./pages/PoliceMonitor'));
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
    if (appMode !== 'public' || !['hub', 'transparency'].includes(publicActivePage)) return;
    loadPublicDashboard({ minLocationCount: 1 }).catch(() => {});
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
    setPublicActivePage('hub');
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
          return <CitizenPortalHub
            onNavigate={(page) => setPublicActivePage(page)}
            onLoginClick={() => setAppMode('login')}
          />;
        case 'transparency':
          return <PublicDashboard
            onLoginClick={() => setAppMode('login')}
            onBack={() => setPublicActivePage('hub')}
          />;
        case 'transparency-info':
        case 'open-data':
        case 'technical-bulletins':
        case 'accountability':
          return <PublicInformation
            initialSection={publicActivePage}
            onBack={() => setPublicActivePage('hub')}
            onNavigate={(page) => setPublicActivePage(page)}
          />;
        case 'victim-support':
          return <VictimRoutes onBack={() => setPublicActivePage('hub')} />;
        case 'reporting':
          return <SecureReporting onBack={() => setPublicActivePage('hub')} />;
        case 'participation':
          return <CommunityParticipation onBack={() => setPublicActivePage('hub')} />;
        case 'intelligence':
          return <IntelligenceModule />;
        case 'educational':
          return <div className="p-20 text-center">Módulo Educativo en Desarrollo</div>;
        case 'pqr':
          return <PQRPage onBack={() => setPublicActivePage('hub')} />;
        default:
          return <CitizenPortalHub
            onNavigate={(page) => setPublicActivePage(page)}
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
        return <DataPage />;
      case 'monitoring': // Added new case for monitoring (MinDefensa)
        return <MindefensaMonitor onIngest={handleIngestDataset} />;
      case 'police_monitor': // New case for Police assets monitor
        return <PoliceMonitor onIngest={handleIngestDataset} />;

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


