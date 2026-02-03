import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.heat';

const HeatmapLayer = ({ points }) => {
    const map = useMap();

    useEffect(() => {
        if (!points || points.length === 0) return;

        // Formatear puntos para leaflet.heat [lat, lng, intensidad]
        const heatPoints = points.map(p => [
            p.geometry.coordinates[1],
            p.geometry.coordinates[0],
            0.5 // Intensidad base
        ]);

        const layer = L.heatLayer(heatPoints, {
            radius: 25,
            blur: 15,
            maxZoom: 17,
            gradient: {
                0.4: 'blue',
                0.6: 'cyan',
                0.7: 'lime',
                0.8: 'yellow',
                1.0: 'red'
            }
        }).addTo(map);

        return () => {
            map.removeLayer(layer);
        };
    }, [map, points]);

    return null;
};

export default HeatmapLayer;
