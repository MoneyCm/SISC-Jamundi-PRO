import React, { useState } from 'react';
import './index.css';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import MapPage from './pages/MapPage';
import ReportsPage from './pages/ReportsPage';
import DataPage from './pages/DataPage';

const App = () => {
  const [activePage, setActivePage] = useState('dashboard');

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
    <Layout activePage={activePage} setActivePage={setActivePage}>
      <div className="animate-fade-in h-full">
        {renderContent()}
      </div>
    </Layout>
  );
};

export default App;
