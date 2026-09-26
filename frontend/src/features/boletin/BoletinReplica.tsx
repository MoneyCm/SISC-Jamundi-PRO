import React, { useEffect } from 'react';
import Dashboard from './components/Dashboard';
import './boletin.css';

export default function BoletinReplica({ onOpenArchive }: { onOpenArchive: () => void }) {
  useEffect(() => {
    document.body.classList.add('printing-boletin-replica');
    return () => document.body.classList.remove('printing-boletin-replica');
  }, []);
  return <div className="boletin-replica">
    <div className="hide-on-print border-b border-white/15 px-4 py-3 text-sm text-white">
      <strong>Boletín institucional</strong>
      <p className="mt-1 text-ui-text-secondary">Los indicadores sin fuente verificada se muestran pendientes.</p>
    </div>
    <Dashboard onOpenArchive={onOpenArchive} />
  </div>;
}
