import React, { useState, useEffect } from 'react';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { FaSun, FaMoon } from 'react-icons/fa';

// --- Components ---
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Toast from './components/Toast';
import PatternBackground from './components/Template/PatternBackground';

// --- Pages ---
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ProfilePage from './pages/ProfilePage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import LayoutPage from './pages/LayoutPage';
import Allocation from './pages/Allocation';
import FeedbackPage from './pages/FeedbackPage';
import AboutusPage from './pages/AboutusPage';
import TemplateEditor from './pages/TemplateEditor';
import AttendancePage from './pages/AttendencePage';

// -------------------------------------------------------------------
// THEME TOGGLE (optional, kept for completeness)
// -------------------------------------------------------------------
function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="p-2 rounded-full text-white bg-gray-700 hover:bg-gray-600 transition duration-300 shadow-md"
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? (
        <FaSun className="text-yellow-400" size={20} />
      ) : (
        <FaMoon size={20} />
      )}
    </button>
  );
}

// -------------------------------------------------------------------
// APP CONTENT (inside providers)
// -------------------------------------------------------------------
const AppContent = () => {
  const { theme } = useTheme();
  const { user, loading } = useAuth();

  // 🔒 Restore last page from localStorage
  const [currentPage, setCurrentPage] = useState(() => {
    return localStorage.getItem('currentPage') || 'landing';
  });

  const [toast, setToast] = useState(null);

  // --------------------------------------------------
  // SAVE CURRENT PAGE (persist across refresh)
  // --------------------------------------------------
  useEffect(() => {
    if (currentPage) {
      localStorage.setItem('currentPage', currentPage);
    }
  }, [currentPage]);

  // --------------------------------------------------
  // AUTH GUARD + INITIAL ROUTE RESOLUTION
  // --------------------------------------------------
  useEffect(() => {
    if (loading) return; // ⛔ WAIT for auth to finish

    const protectedPages = [
      'dashboard',
      'profile',
      'upload',
      'allocation',
      'layout',
      'template-editor',
      'attendence',
    ];

    if (!user && protectedPages.includes(currentPage)) {
      setCurrentPage('login');
      localStorage.removeItem('currentPage');
      return;
    }

    // Logged in but on auth pages → redirect to dashboard
    if (user && ['login', 'signup', 'landing'].includes(currentPage)) {
      setCurrentPage('dashboard');
    }
  }, [user, loading, currentPage]);

  // --------------------------------------------------
  // TOAST HELPERS
  // --------------------------------------------------
  const showToast = (message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const closeToast = () => setToast(null);

  // --------------------------------------------------
  // LOADING SCREEN (NO PAGE FLASH)
  // --------------------------------------------------
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 font-medium">
            Loading your session…
          </p>
        </div>
      </div>
    );
  }

  // --------------------------------------------------
  // PAGE RENDERER
  // --------------------------------------------------
  const renderPage = () => {
    switch (currentPage) {
      case 'landing':
        return <LandingPage setCurrentPage={setCurrentPage} />;
      case 'login':
        return <LoginPage setCurrentPage={setCurrentPage} showToast={showToast} />;
      case 'signup':
        return <SignupPage setCurrentPage={setCurrentPage} showToast={showToast} />;
      case 'profile':
        return <ProfilePage showToast={showToast} setCurrentPage={setCurrentPage} />;
      case 'dashboard':
        return <DashboardPage setCurrentPage={setCurrentPage} />;
      case 'upload':
        return <UploadPage showToast={showToast} />;
      case 'allocation':
        return <Allocation showToast={showToast} />;
      case 'layout':
        return <LayoutPage showToast={showToast} />;
      case 'feedback':
        return <FeedbackPage showToast={showToast} />;
      case 'aboutus':
        return <AboutusPage showToast={showToast} />;
      case 'template-editor':
        return <TemplateEditor showToast={showToast} />;
      case 'attendence':
        return <AttendancePage showToast={showToast} />;
      default:
        return <LandingPage setCurrentPage={setCurrentPage} />;
    }
  };

  // --------------------------------------------------
  // MAIN LAYOUT
  // --------------------------------------------------
  return (
    <>
      <PatternBackground isDark={theme === 'dark'} />

      <div className="min-h-screen flex flex-col transition-colors duration-300 relative z-10">
        <Navbar currentPage={currentPage} setCurrentPage={setCurrentPage} />

        <main className="flex-1">{renderPage()}</main>

        <Footer />

        {toast && (
          <Toast
            message={toast.message}
            type={toast.type}
            onClose={closeToast}
          />
        )}
      </div>
    </>
  );
};

// -------------------------------------------------------------------
// ROOT APP
// -------------------------------------------------------------------
const App = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
