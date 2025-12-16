import React, { useState, useContext } from 'react';
// FIX: Import the custom hook useTheme from your context file
import { ThemeProvider, useTheme } from './context/ThemeContext'; 
import { AuthProvider } from './context/AuthContext';
// NOTE: Removed unused useEffect import.
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


// --- THEME TOGGLE COMPONENT (Standalone) ---
// This component assumes it is rendered inside a ThemeProvider.
function ThemeToggle() {
    const { theme, toggleTheme } = useTheme(); 

    return (
        <button
            onClick={toggleTheme}
            className="p-2 rounded-full text-white bg-gray-700 hover:bg-gray-600 transition duration-300 shadow-md"
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
            {theme === 'dark' ? <FaSun className="text-yellow-400" size={20} /> : <FaMoon size={20} />}
        </button>
    );
}


// --- 🆕 NEW WRAPPER COMPONENT ---
// This component is the actual App logic, now placed INSIDE the providers.
const AppContent = () => {
  // Now, useTheme() is called safely inside the ThemeProvider
  const { theme } = useTheme(); 

  // --- STATE AND HANDLERS (Moved from App) ---
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
      case 'template-editor': // The new page key
        // Pass showToast since TemplateEditor uses it
        return <TemplateEditor showToast={showToast} />; 
      default:
        return <LandingPage setCurrentPage={setCurrentPage} />;
    }
  };
    // --- END STATE AND HANDLERS ---


  return (
    <>
        {/* PatternBackground uses the theme variable */}
        <PatternBackground isDark={theme === 'dark'} /> 

        <div className="min-h-screen flex flex-col transition-colors duration-300"> 
          <Navbar currentPage={currentPage} setCurrentPage={setCurrentPage} />
          
          <main className="flex-1 z-10">
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
    </>
  );
};


// --- ORIGINAL APP COMPONENT (The Root Wrapper) ---
const App = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        {/* The entire application content that requires context lives here */}
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;