  import React, { useState } from "react";
  import { useNavigate, Link } from "react-router-dom";

  function Signup({ setIsSignedIn }) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const navigate = useNavigate();

    const handleSignup = async (e) => {
    e.preventDefault();
    if (!email || !password) return alert("Please fill all fields");

    try {
      const res = await fetch("http://localhost:8000/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();
      localStorage.setItem("user_id", data.user_id);
      console.log("Signup response:", res.status, data);

      if (!res.ok) throw new Error(data.detail || "Signup failed");
      
      setIsSignedIn(true);
      navigate("/userform");
    } catch (err) {
      alert("Signup error: " + err.message);  // now shows "Email already registered"
    }
  };




    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 p-6">
        <form onSubmit={handleSignup} className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md w-full max-w-sm space-y-4">
          <h2 className="text-2xl font-semibold text-center text-gray-800 dark:text-white">Sign Up</h2>

          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-2 rounded-lg bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white"
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-2 rounded-lg bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white"
          />

          <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded-lg">Sign Up</button>

          <p className="text-center text-sm text-gray-600 dark:text-gray-400">
            Already have an account? <Link to="/signin" className="text-blue-500">Sign In</Link>
          </p>
        </form>
      </div>
    );
  }

  export default Signup;
