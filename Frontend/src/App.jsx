import React, { useState } from 'react';
import { AuthProvider } from './context/AuthContext';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Toast from './components/Toast';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ProfilePage from './pages/ProfilePage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import LayoutPage from './pages/LayoutPage';

const App = () => {
  const [currentPage, setCurrentPage] = useState('landing');
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'info') => {
    setToast({ message, type });
  };

  const closeToast = () => {
    setToast(null);
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'landing':
        return <LandingPage setCurrentPage={setCurrentPage} />;
      case 'login':
        return <LoginPage setCurrentPage={setCurrentPage} showToast={showToast} />;
      case 'signup':
        return <SignupPage setCurrentPage={setCurrentPage} showToast={showToast} />;
      case 'profile':
        return <ProfilePage showToast={showToast} />;
      case 'dashboard':
        return <DashboardPage setCurrentPage={setCurrentPage} />;
      case 'upload':
        return <UploadPage showToast={showToast} />;
      case 'layout':
        return <LayoutPage showToast={showToast} />;
      default:
        return <LandingPage setCurrentPage={setCurrentPage} />;
    }
  };

  return (
    <AuthProvider>
      <div className="min-h-screen flex flex-col">
        <Navbar currentPage={currentPage} setCurrentPage={setCurrentPage} />
        <main className="flex-1">
          {renderPage()}
        </main>
        <Footer />
        {toast && <Toast message={toast.message} type={toast.type} onClose={closeToast} />}
      </div>
      <style>{`
        @keyframes slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        .animate-slide-in {
          animation: slide-in 0.3s ease-out;
        }
      `}</style>
    </AuthProvider>
  );
};

export default App;