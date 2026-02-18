import { useEffect, useState } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

const HeatmapLayer = ({ points }) => {
    const map = useMap();
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
        // Cargar leaflet-heat dinámicamente desde CDN si no existe
        if (L.heatLayer) {
            setLoaded(true);
            return;
        }

        const script = document.createElement('script');
        script.src = "https://cdn.jsdelivr.net/npm/leaflet.heat@0.2.0/dist/leaflet-heat.js";
        script.async = true;
        script.onload = () => {
            setLoaded(true);
        };
        document.body.appendChild(script);

        return () => {
            // No quitamos el script para que esté disponible si se vuelve a montar
        };
    }, []);

    useEffect(() => {
        if (!loaded || !points || points.length === 0 || !L.heatLayer) return;

        // Formatear puntos para leaflet.heat [lat, lng, intensidad]
        const heatPoints = points.map(p => [
            p.geometry.coordinates[1],
            p.geometry.coordinates[0],
            0.5 // Intensidad base
        ]);

        const layer = L.heatLayer(heatPoints, {
            radius: 30,
            blur: 20,
            maxZoom: 17,
            gradient: {
                0.4: 'blue',
                0.6: 'lime',
                0.8: 'yellow',
                1.0: 'red'
            }
        }).addTo(map);

        return () => {
            map.removeLayer(layer);
        };
    }, [map, points, loaded]);

    return null;
};

export default HeatmapLayer;
