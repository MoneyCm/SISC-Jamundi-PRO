import { format, parseISO, subMonths, isSameMonth } from 'date-fns';
import { es } from 'date-fns/locale';

export const transformDashboardData = (incidents) => {
    if (!incidents || incidents.length === 0) {
        return {
            kpiData: [],
            crimeTrendData: [],
            crimeDistributionData: [],
            recentActivity: []
        };
    }

    // 1. KPIs
    const totalIncidents = incidents.length;

    const homicidios = countByType('HOMICIDIO');
    const hurtos = countByType('HURTO A PERSONAS') + countByType('HURTO A COMERCIO');
    const vif = countByType('VIOLENCIA INTRAFAMILIAR');

    // Mocking trends for now as we might not have enough historical data in the MVP
    const kpiData = [
        { title: "Total Incidentes", value: totalIncidents.toString(), change: "+0%", trend: "neutral", icon: "AlertTriangle" },
        { title: "Homicidios", value: homicidios.toString(), change: "+0%", trend: "neutral", icon: "Skull" },
        { title: "Hurtos", value: hurtos.toString(), change: "+0%", trend: "neutral", icon: "Briefcase" },
        { title: "Violencia Intrafamiliar", value: vif.toString(), change: "+0%", trend: "neutral", icon: "Home" },
    ];

    // 2. Crime Trend (Last 6 months)
    const months = [];
    for (let i = 5; i >= 0; i--) {
        months.push(subMonths(new Date(), i));
    }

    const crimeTrendData = months.map(date => {
        const monthName = format(date, 'MMM', { locale: es });
        const monthIncidents = incidents.filter(i => {
            // Handle both ISO strings and YYYY-MM-DD strings
            const incidentDate = i.fecha.includes('T') ? parseISO(i.fecha) : parseISO(i.fecha + 'T00:00:00');
            return isSameMonth(incidentDate, date);
        });

        return {
            name: monthName.charAt(0).toUpperCase() + monthName.slice(1),
            homicidios: monthIncidents.filter(i => i.tipo === 'HOMICIDIO').length,
            hurtos: monthIncidents.filter(i => i.tipo.includes('HURTO')).length,
            vif: monthIncidents.filter(i => i.tipo === 'VIOLENCIA INTRAFAMILIAR').length
        };
    });

    // 3. Distribution
    const distribution = incidents.reduce((acc, curr) => {
        acc[curr.tipo] = (acc[curr.tipo] || 0) + 1;
        return acc;
    }, {});

    const crimeDistributionData = Object.keys(distribution).map(key => ({
        name: key,
        value: distribution[key]
    }));

    // 4. Recent Activity (Last 5)
    const recentActivity = incidents.slice(0, 5).map(i => ({
        id: i.id,
        type: i.tipo,
        location: i.barrio,
        time: i.fecha, // Could format this to "relative time" if needed
        status: i.estado
    }));

    return {
        kpiData,
        crimeTrendData,
        crimeDistributionData,
        recentActivity
    };
};
