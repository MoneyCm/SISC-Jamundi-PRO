import React, { useState, useEffect } from 'react';
import './index.css';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import MapPage from './pages/MapPage';
import ReportsPage from './pages/ReportsPage';
import DataPage from './pages/DataPage';
import PublicDashboard from './pages/PublicDashboard';
import LoginPage from './pages/LoginPage';
import PQRPage from './pages/PQRPage';
import CitizenPortalHub from './pages/CitizenPortalHub';
import VictimRoutes from './pages/VictimRoutes';
import SecureReporting from './pages/SecureReporting';
import CommunityParticipation from './pages/CommunityParticipation';
import IntelligenceModule from './pages/IntelligenceModule';
import DataQuality from './pages/DataQuality';
import SiscAIChatbot from './components/SiscAIChatbot';
import UniversalIngesta from './pages/UniversalIngesta';
import MindefensaMonitor from './pages/MindefensaMonitor';
import PoliceMonitor from './pages/PoliceMonitor';
import RegionalContext from './pages/RegionalContext';
import RNMCModule from './pages/RNMCModule';
import AlertsFeed from './pages/AlertsFeed';
import UsersManagement from './pages/UsersManagement';
import AccessRequests from './pages/AccessRequests';
import AuditLog from './pages/AuditLog';

const App = () => {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [userRoles, setUserRoles] = useState([]);
  const [dataLevel, setDataLevel] = useState(1);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [appMode, setAppMode] = useState('loading'); // Nuevo estado inicial
  const [activePage, setActivePage] = useState('dashboard');
  const [publicActivePage, setPublicActivePage] = useState('hub');
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
      setTimeout(() => setIsLoading(false), 500);
    };
    initApp();
  }, []);

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
    return <LoginPage
      onLoginSuccess={handleLoginSuccess}
      onBackClick={() => setAppMode('public')}
    />;
  }

  const isPublic = appMode === 'public';

  const renderContent = () => {
    if (isPublic) {
      switch (publicActivePage) {
        case 'hub':
          return <CitizenPortalHub
            onNavigate={(page) => setPublicActivePage(page)}
            onLoginClick={() => setAppMode('login')}
          />;
        case 'transparency':
          return <PublicDashboard onLoginClick={() => setAppMode('login')} />;
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
        return <Dashboard userRoles={userRoles} dataLevel={dataLevel} />;
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
      case 'alerts':
        return <AlertsFeed onPageChange={setActivePage} setExternalFilters={setRnmcFilters} />;
      case 'rnmc':
        return <RNMCModule externalFilters={rnmcFilters} clearExternalFilters={() => setRnmcFilters(null)} />;
      case 'dq':
        return <DataQuality initialReportId={selectedReportId} />;
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

  // Para que el Chatbot se vea en TODAS las páginas públicas, 
  // incluída la Hub, usamos la Layout común.
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
        {renderContent()}
      </div>
      {isPublic && <SiscAIChatbot />}
    </Layout>
  );
};

export default App;
