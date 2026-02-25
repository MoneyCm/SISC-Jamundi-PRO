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

const App = () => {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [appMode, setAppMode] = useState(token ? 'authenticated' : 'public');
  const [activePage, setActivePage] = useState('dashboard');
  const [publicActivePage, setPublicActivePage] = useState('hub');
  const [isAuthenticated, setIsAuthenticated] = useState(false); // New state
  const [userRole, setUserRole] = useState(null); // New state
  const [isLoading, setIsLoading] = useState(true); // New state
  const [selectedReportId, setSelectedReportId] = useState(null); // State for sharing DQ reports
  const [selectedDataset, setSelectedDataset] = useState({ code: 'SECUESTRO', label: 'Secuestro' });

  const handleIngestDataset = (code, label) => {
    setSelectedDataset({ code, label });
    setActivePage('ingesta_universal');
  };

  // Verificación de token al montar app (Modified useEffect)
  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const role = localStorage.getItem('userRole');
    if (storedToken) {
      setIsAuthenticated(true);
      setUserRole(role);
      setToken(storedToken); // Keep existing token state
      setAppMode('authenticated'); // Keep existing appMode state
    }
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  const handleLoginSuccess = (newToken, role) => { // Modified to accept role
    setToken(newToken);
    localStorage.setItem('token', newToken); // Store token
    localStorage.setItem('userRole', role); // Store role
    setIsAuthenticated(true); // New state update
    setUserRole(role); // New state update
    setAppMode('authenticated');
    setActivePage('dashboard'); // Set active page after login
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userRole'); // Remove role
    setToken(null);
    setIsAuthenticated(false); // New state update
    setUserRole(null); // New state update
    setAppMode('public');
    setPublicActivePage('hub');
    setActivePage('dashboard'); // Reset active page on logout
  };

  const isPublic = appMode === 'public';

  if (isLoading) { // New loading state
    return (
      <div className="flex items-center justify-center h-screen bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-slate-500 font-medium">Cargando SISC Jamundí...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated && appMode === 'authenticated') { // Redirect to login if not authenticated but appMode is 'authenticated'
    setAppMode('login');
  }

  if (appMode === 'login') {
    return <LoginPage
      onLoginSuccess={handleLoginSuccess}
      onBackClick={() => setAppMode('public')}
    />;
  }

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
        return <Dashboard />;
      case 'map':
        return <MapPage />;
      case 'reports':
        return <ReportsPage />;
      case 'data':
        return <DataPage />;
      case 'monitoring': // Added new case for monitoring
        return <MindefensaMonitor onIngest={handleIngestDataset} />; // Render MindefensaMonitor component
      case 'intelligence':
        return <IntelligenceModule />;
      case 'dq':
        return <DataQuality initialReportId={selectedReportId} />;
      case 'ingesta_universal':
        return <UniversalIngesta
          setActivePage={setActivePage}
          setReportId={setSelectedReportId}
          datasetCode={selectedDataset?.code || "SECUESTRO"}
          label={selectedDataset?.label || "Secuestro"}
        />;
      case 'ingesta_secuestro':
        return <UniversalIngesta
          setActivePage={setActivePage}
          setReportId={setSelectedReportId}
          datasetCode="SECUESTRO"
          label="Secuestro"
        />;
      case 'ingesta_homicidio':
        return <UniversalIngesta
          setActivePage={setActivePage}
          setReportId={setSelectedReportId}
          datasetCode="HOMICIDIO_INTENCIONAL"
          label="Homicidios (Intencional)"
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
    >
      <div className="animate-fade-in h-full">
        {renderContent()}
      </div>
      {isPublic && <SiscAIChatbot />}
    </Layout>
  );
};

export default App;
