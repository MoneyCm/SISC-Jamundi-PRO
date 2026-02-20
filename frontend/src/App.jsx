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
import SiscAIChatbot from './components/SiscAIChatbot';

const App = () => {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [appMode, setAppMode] = useState(token ? 'authenticated' : 'public');
  const [activePage, setActivePage] = useState('dashboard');
  const [publicActivePage, setPublicActivePage] = useState('hub');

  const handleLoginSuccess = (newToken) => {
    setToken(newToken);
    setAppMode('authenticated');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setAppMode('public');
    setPublicActivePage('hub');
  };

  const isPublic = appMode === 'public';

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
      case 'intelligence':
        return <IntelligenceModule />;
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
