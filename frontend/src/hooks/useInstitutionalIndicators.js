import { useEffect, useState } from 'react';
import { API_BASE_URL } from '../utils/apiConfig';

export const useInstitutionalIndicators = (program) => {
  const [records, setRecords] = useState([]);
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    const controller = new AbortController();
    const url = API_BASE_URL + '/institutional-indicators/public?program=' + encodeURIComponent(program);

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('No fue posible consultar los indicadores');
        return response.json();
      })
      .then((data) => {
        setRecords(Array.isArray(data.records) ? data.records : []);
        setStatus('ready');
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setStatus('fallback');
      });

    return () => controller.abort();
  }, [program]);

  return { records, status };
};