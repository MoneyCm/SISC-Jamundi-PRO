import React from 'react';
import PublicPortalHeader from '../components/public/PublicPortalHeader';
import ObservatoryBulletins from '../components/ObservatoryBulletins';

const ObservatoryBulletinsPage = ({ onNavigate, onLoginClick }) => {
    return (
        <>
            <PublicPortalHeader
                currentPage="technical-bulletins"
                onNavigate={onNavigate}
                onLoginClick={onLoginClick}
            />
            <main className="max-w-6xl mx-auto px-4 py-8">
                <ObservatoryBulletins />
            </main>
        </>
    );
};

export default ObservatoryBulletinsPage;
