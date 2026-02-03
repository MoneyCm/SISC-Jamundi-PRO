export const kpiData = [
    { title: "Total Incidentes", value: "1,245", change: "+12%", trend: "up", icon: "AlertTriangle" },
    { title: "Homicidios", value: "12", change: "-5%", trend: "down", icon: "Skull" },
    { title: "Hurtos", value: "450", change: "+8%", trend: "up", icon: "Briefcase" },
    { title: "Violencia Intrafamiliar", value: "89", change: "+2%", trend: "up", icon: "Home" },
];

export const crimeTrendData = [
    { name: 'Ene', homicidios: 4, hurtos: 65, vif: 12 },
    { name: 'Feb', homicidios: 3, hurtos: 59, vif: 15 },
    { name: 'Mar', homicidios: 2, hurtos: 80, vif: 10 },
    { name: 'Abr', homicidios: 5, hurtos: 81, vif: 18 },
    { name: 'May', homicidios: 3, hurtos: 56, vif: 14 },
    { name: 'Jun', homicidios: 4, hurtos: 55, vif: 16 },
    { name: 'Jul', homicidios: 6, hurtos: 70, vif: 20 },
];

export const crimeDistributionData = [
    { name: 'Hurto Personas', value: 400 },
    { name: 'Hurto Vehículos', value: 150 },
    { name: 'Lesiones Personales', value: 300 },
    { name: 'Violencia Intrafamiliar', value: 200 },
    { name: 'Homicidios', value: 50 },
];

export const recentActivity = [
    { id: 1, type: "Hurto", location: "Barrio El Peñón", time: "Hace 2 horas", status: "Atendido" },
    { id: 2, type: "Riña", location: "Parque Principal", time: "Hace 4 horas", status: "En proceso" },
    { id: 3, type: "Violencia VIF", location: "Terranova", time: "Hace 5 horas", status: "Remitido" },
    { id: 4, type: "Hurto Moto", location: "Alfaguara", time: "Hace 8 horas", status: "Atendido" },
];
