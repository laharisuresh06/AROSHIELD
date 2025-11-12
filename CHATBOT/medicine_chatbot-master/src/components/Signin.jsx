import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

function Signin({ setIsSignedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(""); // State for error messages
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSignin = async (e) => {
    e.preventDefault();
    setError(""); // Clear previous errors
    setLoading(true);

    if (!email || !password) {
      setError("Please fill all fields.");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch("http://localhost:8000/signin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();
      
      // Check response status first
      if (!res.ok) {
        setError(data.detail || "Sign-in failed. Please check your email and password.");
        return; 
      }

      // Only save user ID and redirect on success
      localStorage.setItem("user_id", data.user_id);
      setIsSignedIn(true);
      navigate("/userform");
    } catch (err) {
      console.error("Sign-in network error:", err);
      setError("A network error occurred. Please check the server connection.");
    } finally {
        setLoading(false);
    }
  };


  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 p-6">
      <form onSubmit={handleSignin} className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-xl w-full max-w-sm space-y-5">
        <h2 className="text-3xl font-bold text-center text-indigo-600 dark:text-indigo-400">Sign In</h2>

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full px-4 py-3 rounded-lg bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
          required
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-4 py-3 rounded-lg bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
          required
        />
        
        {/* Display error message in the UI */}
        {error && (
            <div className="p-3 text-sm text-red-700 bg-red-100 rounded-lg border border-red-200">
                {error}
            </div>
        )}

        <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-indigo-600 text-white font-semibold py-3 rounded-lg hover:bg-indigo-700 transition duration-200 disabled:opacity-50"
        >
            {loading ? 'Signing In...' : 'Sign In'}
        </button>

        <p className="text-center text-sm text-gray-600 dark:text-gray-400">
          Don’t have an account? <Link to="/signup" className="text-indigo-500 hover:text-indigo-400 font-medium">Sign Up</Link>
        </p>
      </form>
    </div>
  );
}

export default Signin;