import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './authContext';
import '../App.css';

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await signup(email, password, fullName);
      navigate('/login');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-form-body">
      <div className="auth-form-container">
        <h2 className="auth-form-title">Sign Up</h2>
        {error && <p className="auth-form-error">{error}</p>}
        <form onSubmit={handleSubmit}>
          <label className="auth-form-label">
            Full Name
            <input
              type="text"
              className="auth-form-input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              disabled={isLoading}
            />
          </label>
          <label className="auth-form-label">
            Email
            <input
              type="email"
              className="auth-form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={isLoading}
            />
          </label>
          <label className="auth-form-label">
            Password
            <input
              type="password"
              className="auth-form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
            />
          </label>
          <button 
            type="submit" 
            className="auth-form-submit"
            disabled={isLoading}
          >
            {isLoading ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>
        <p className="auth-form-text">
          Already have an account? <a className="auth-form-link" href="/login">Log In</a>
        </p>
      </div>
    </div>
  );
}