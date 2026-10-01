// Quién puede publicar boletines en la web: el permiso "Publica boletines" (la Secretaria) y la administración.
// El servidor lo vuelve a comprobar; aquí solo se evita mostrar un botón que va a fallar.
export const ROLES_PUBLICAN = ['PUBLICATION_APPROVER', 'FUNC_ADMIN', 'TI_ADMIN'];

export const rolesGuardados = () => {
    try {
        return JSON.parse(localStorage.getItem('userRoles') || '[]');
    } catch {
        return [];
    }
};

export const puedePublicar = (roles = rolesGuardados()) => roles.some((rol) => ROLES_PUBLICAN.includes(rol));

// Seguimiento de compromisos (editar estados, intervenciones, informes): analistas, directivos y administración.
export const ROLES_SEGUIMIENTO = ['ANALYST', 'DIRECTIVE', 'FUNC_ADMIN', 'TI_ADMIN'];
export const puedeHacerSeguimiento = (roles = rolesGuardados()) => roles.some((rol) => ROLES_SEGUIMIENTO.includes(rol));
// Subir y archivar actas: además, el gestor de actas.
export const puedeGestionarActas = (roles = rolesGuardados()) => puedeHacerSeguimiento(roles) || roles.includes('ACTAS_OPERATOR');

export const MENSAJE_NO_PUBLICA = 'Solo la Secretaria de Seguridad y la administración del SISC publican boletines.';
