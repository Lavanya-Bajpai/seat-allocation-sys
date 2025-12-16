// Frontend/src/components/Header.jsx

import React, { useContext } from 'react';
import { ThemeContext } from '../App.jsx'; // Import context from parent App
import { FaMoon, FaSun } from 'react-icons/fa';

const Header = () => {
    // Consume the theme context
    const { theme, toggleTheme } = useContext(ThemeContext);

    const isDark = theme === 'dark';

    return (
        <header className="sticky top-0 z-20 p-4 shadow-md bg-white dark:bg-gray-900 transition-colors duration-300">
            <div className="max-w-6xl mx-auto flex justify-between items-center">
                <h2 className="text-xl font-bold text-indigo-600 dark:text-indigo-400">
                    Seating Plan Utility
                </h2>
                
                {/* Theme Toggle Button */}
                <button
                    onClick={toggleTheme}
                    className="p-2 rounded-full text-gray-700 dark:text-yellow-400 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                    aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}
                >
                    {isDark ? <FaSun className="text-lg" /> : <FaMoon className="text-lg" />}
                </button>
            </div>
        </header>
    );
};

export default Header;