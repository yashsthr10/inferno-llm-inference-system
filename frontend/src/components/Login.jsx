import React, { useState } from 'react';
import { useAuth } from './authContext';
import { useNavigate } from 'react-router-dom';
import '../App.css';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-form-body">
      <div className="auth-form-container">
        <h2 className="auth-form-title">Login</h2>
        {error && <p className="auth-form-error">{error}</p>}
        <form onSubmit={handleSubmit}>
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
            {isLoading ? 'Logging in...' : 'Log In'}
          </button>
        </form>
        <p className="auth-form-text">
          Don't have an account? <a className="auth-form-link" href="/signup">Sign Up</a>
        </p>
      </div>
    </div>
  );
}