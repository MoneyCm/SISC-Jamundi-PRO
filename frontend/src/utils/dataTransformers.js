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

    // Helper para contar con lógica flexible (maneja siglas como H. o V.)
    const matchesType = (itemTipo, target) => {
        const t = (itemTipo || '').toString().toUpperCase();
        if (target === 'HURTO') return t.includes('HURTO') || t.startsWith('H.');
        if (target === 'VIF') return t.includes('VIOLENCIA') || t.includes('VIF') || t.startsWith('V.');
        if (target === 'HOMICIDIO') return t.includes('HOMICI');
        return t === target.toUpperCase();
    };

    const totalIncidents = incidents.length;
    const homocidios = incidents.filter(i => matchesType(i.tipo, 'HOMICIDIO')).length;
    const hurtos = incidents.filter(i => matchesType(i.tipo, 'HURTO')).length;
    const vif = incidents.filter(i => matchesType(i.tipo, 'VIF')).length;

    // 1. KPIs
    const kpiData = [
        { title: "Total Incidentes", value: totalIncidents.toString(), change: "+0%", trend: "neutral", icon: "AlertTriangle" },
        { title: "Homicidios", value: homocidios.toString(), change: "+0%", trend: "neutral", icon: "Skull" },
        { title: "Hurtos", value: hurtos.toString(), change: "+0%", trend: "neutral", icon: "Briefcase" },
        { title: "Violencia Intrafamiliar", value: vif.toString(), change: "+0%", trend: "neutral", icon: "Home" },
    ];

    // 2. Crime Trend (Last 6 months based on data max date)
    const maxDate = incidents.reduce((max, i) => {
        const d = i.fecha.includes('T') ? parseISO(i.fecha) : parseISO(i.fecha + 'T00:00:00');
        return d > max ? d : max;
    }, new Date(0));

    const referenceDate = maxDate.getTime() > 0 ? maxDate : new Date();

    const months = [];
    for (let i = 5; i >= 0; i--) {
        months.push(subMonths(referenceDate, i));
    }

    const crimeTrendData = months.map(date => {
        const monthName = format(date, 'MMM', { locale: es });
        const monthIncidents = incidents.filter(i => {
            const incidentDate = i.fecha.includes('T') ? parseISO(i.fecha) : parseISO(i.fecha + 'T00:00:00');
            return isSameMonth(incidentDate, date);
        });

        return {
            name: monthName.charAt(0).toUpperCase() + monthName.slice(1),
            year: format(date, 'yyyy'),
            homicidios: monthIncidents.filter(i => matchesType(i.tipo, 'HOMICIDIO')).length,
            hurtos: monthIncidents.filter(i => matchesType(i.tipo, 'HURTO')).length,
            vif: monthIncidents.filter(i => matchesType(i.tipo, 'VIF')).length
        };
    });

    // 3. Distribution - Limpiar nombres para el gráfico de torta
    const distribution = incidents.reduce((acc, curr) => {
        let label = (curr.tipo || 'OTRO').toString().toUpperCase();
        if (label.startsWith('H.')) label = label.replace('H.', 'HURTO ');
        if (label.startsWith('V.')) label = label.replace('V.', 'VIOLENCIA ');

        acc[label] = (acc[label] || 0) + 1;
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
        time: i.fecha,
        status: i.estado
    }));

    return {
        kpiData,
        crimeTrendData,
        crimeDistributionData,
        recentActivity
    };
};
