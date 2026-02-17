import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

const Layout = ({ children, activePage, setActivePage, onLogout, isPublic }) => {
    const [sidebarOpen, setSidebarOpen] = React.useState(false);

    return (
        <div className="flex h-screen bg-slate-50 overflow-hidden relative">
            {/* Mobile Sidebar Overlay */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 bg-slate-900/50 z-20 md:hidden backdrop-blur-sm transition-opacity"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            <Sidebar
                activePage={activePage}
                setActivePage={setActivePage}
                isOpen={sidebarOpen}
                onClose={() => setSidebarOpen(false)}
                onLogout={onLogout}
                isPublic={isPublic}
            />

            <div className="flex-1 flex flex-col min-w-0 h-full">
                <Header onMenuClick={() => setSidebarOpen(true)} isPublic={isPublic} />
                <main className={`flex-1 overflow-y-auto ${isPublic ? 'p-0' : 'p-4 md:p-8'}`}>
                    {children}
                </main>
            </div>
        </div>
    );
};

export default Layout;
