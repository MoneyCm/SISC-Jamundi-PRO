import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

const Layout = ({ children, activePage, setActivePage }) => {
    return (
        <div className="flex h-screen bg-slate-50 overflow-hidden">
            <Sidebar activePage={activePage} setActivePage={setActivePage} />
            <div className="flex-1 flex flex-col min-w-0">
                <Header />
                <main className="flex-1 overflow-y-auto p-8">
                    {children}
                </main>
            </div>
        </div>
    );
};

export default Layout;
