import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'; 
import UserForm from './components/UserForm';
import ChatBot from './components/ChatBot';
import Signin from './components/Signin';
import Signup from './components/Signup';


function App() {
  const [isSignedIn, setIsSignedIn] = useState(false);

  // 💡 Improvement: Check localStorage for user_id on mount
  useEffect(() => {
    if (localStorage.getItem("user_id")) {
      setIsSignedIn(true);
    }
  }, []); 

  // Create a Protected Route component or logic
  const ProtectedRoute = ({ element }) => {
    return isSignedIn ? element : <Navigate to="/signin" />;
  };

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/signin" />} />
        <Route path="/signin" element={<Signin setIsSignedIn={setIsSignedIn} />} />
        <Route path="/signup" element={<Signup setIsSignedIn={setIsSignedIn} />} />
        {/* Use ProtectedRoute for restricted pages */}
        <Route path="/userform" element={<ProtectedRoute element={<UserForm />} />} />
        <Route path="/chatbot" element={<ProtectedRoute element={<ChatBot />} />} />
      </Routes>
    </Router>
  );
}

export default App;