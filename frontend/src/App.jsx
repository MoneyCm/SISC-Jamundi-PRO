import React, { useState, useEffect } from 'react';
import './index.css';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import MapPage from './pages/MapPage';
import ReportsPage from './pages/ReportsPage';
import DataPage from './pages/DataPage';
import PublicDashboard from './pages/PublicDashboard';
import LoginPage from './pages/LoginPage';
import CitizenPortalHub from './pages/CitizenPortalHub';
import VictimRoutes from './pages/VictimRoutes';
import SecureReporting from './pages/SecureReporting';
import CommunityParticipation from './pages/CommunityParticipation';
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

  // Si estamos en modo público y no hay una Layout aún (porque queremos una landing pura), 
  // podriamos manejar el Hub fuera de Layout o dentro. 
  // Segun el diseño, el Hub es una landing pura.
  if (isPublic && publicActivePage === 'hub') {
    return <CitizenPortalHub
      onNavigate={(page) => setPublicActivePage(page)}
      onLoginClick={() => setAppMode('login')}
    />;
  }

  const renderContent = () => {
    if (isPublic) {
      switch (publicActivePage) {
        case 'transparency':
          return <PublicDashboard onLoginClick={() => setAppMode('login')} />;
        case 'victim-support':
          return <VictimRoutes onBack={() => setPublicActivePage('hub')} />;
        case 'reporting':
          return <SecureReporting onBack={() => setPublicActivePage('hub')} />;
        case 'participation':
          return <CommunityParticipation onBack={() => setPublicActivePage('hub')} />;
        case 'educational':
          return <div className="p-20 text-center">Módulo Educativo en Desarrollo</div>;
        default:
          return <PublicDashboard onLoginClick={() => setAppMode('login')} />;
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
      default:
        return <Dashboard />;
    }
  };

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
