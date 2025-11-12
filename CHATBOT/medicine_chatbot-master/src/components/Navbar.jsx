import React, { useState } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';

function Navbar() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const toggleMenu = () => setOpen(!open);

  // In Navbar.jsx
const handleSignOut = () => {
    localStorage.removeItem("user_id"); // 💡 Important: Clear the ID
    // You'd ideally also call a global setIsSignedIn(false) here,
    // but based on your current setup, clearing the ID is the minimum.
    navigate("/signin");
};
  const linkClasses = (path) =>
    `block p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-600 ${
      location.pathname === path ? ' dark:bg-blue-800 font-semibold' : ''
    }`;

  return (
    <div className="fixed top-4 right-4 z-50">
      <button
        onClick={toggleMenu}
        className="w-14 h-14 bg-blue-600 text-white rounded-full shadow-lg flex items-center justify-center text-2xl"
      >
        {open ? <X /> : <Menu />}
      </button>

      {open && (
        <div className="absolute top-16 right-0 bg-white dark:bg-gray-700 shadow-lg rounded-lg p-4 space-y-2 text-black dark:text-white w-48">
          <Link to="/userform" className={linkClasses('/userform')}>
            User Form
          </Link>
          <Link to="/chatbot" className={linkClasses('/chatbot')}>
            Chatbot
          </Link>
          <button
            onClick={handleSignOut}
            className="w-full text-left hover:bg-gray-100 dark:hover:bg-gray-600 p-2 rounded"
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}

export default Navbar;
