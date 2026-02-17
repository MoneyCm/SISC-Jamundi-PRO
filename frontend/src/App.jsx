import React, { useState, useEffect } from 'react';
import './index.css';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import MapPage from './pages/MapPage';
import ReportsPage from './pages/ReportsPage';
import DataPage from './pages/DataPage';
import PublicDashboard from './pages/PublicDashboard';
import LoginPage from './pages/LoginPage';

const App = () => {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [appMode, setAppMode] = useState(token ? 'authenticated' : 'public');
  const [activePage, setActivePage] = useState('dashboard');

  const handleLoginSuccess = (newToken) => {
    setToken(newToken);
    setAppMode('authenticated');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setAppMode('public');
  };

  // Public Mode Wrapper
  if (appMode === 'public') {
    return <PublicDashboard onLoginClick={() => setAppMode('login')} />;
  }

  if (appMode === 'login') {
    return <LoginPage
      onLoginSuccess={handleLoginSuccess}
      onBackClick={() => setAppMode('public')}
    />;
  }

  const renderContent = () => {
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
    <Layout activePage={activePage} setActivePage={setActivePage} onLogout={handleLogout}>
      <div className="animate-fade-in h-full">
        {renderContent()}
      </div>
    </Layout>
  );
};

export default App;
