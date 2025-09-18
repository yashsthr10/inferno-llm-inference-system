import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from './authContext';
import GeneratedKeyModal from './GeneratedKeyModal';
import '../App.css';
import Navbar from './Navbar';

// for local setup
// const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080';

// for production 
// const protocol = window.location.protocol === "https:" ? "https://" : "http://";
// const API_BASE_URL = `${protocol}${window.location.host}`;
const API_BASE_URL = '/api/backend'; 

export default function Api() {
  const { isAuthenticated, user } = useAuth();
  const [tokens, setTokens] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [newKey, setNewKey] = useState(null);
  const [showKeyModal, setShowKeyModal] = useState(false);

  // Enhanced error extraction for fetch responses
  const extractError = async (res) => {
    let payload;
    try {
      payload = await res.json();
    } catch (e) {
      return res.statusText || `HTTP Error: ${res.status}`;
    }

    if (typeof payload === 'string') {
      return payload;
    }

    if (payload && typeof payload === 'object') {
      const { detail, error, message } = payload;

      if (Array.isArray(detail)) {
        return detail.map(d => d.msg || d.message || JSON.stringify(d)).join('; ');
      } else if (typeof detail === 'string') {
        return detail;
      } else if (typeof detail === 'object' && detail?.msg) {
        return detail.msg;
      } else if (typeof error === 'string') {
        return error;
      } else if (typeof message === 'string') {
        return message;
      }
    }

    return res.statusText || `Server error: ${res.status}`;
  };

  // Fetch user's tokens
  const fetchTokens = useCallback(async () => {
    if (!isAuthenticated) return;
    
    setIsLoading(true);
    setMessage('Loading tokens...');
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/tokens`, {
        credentials: 'include'
      });

      if (!res.ok) {
        const errorMsg = await extractError(res);
        if (res.status === 401) {
          setMessage('Error: Please log in again.');
          return;
        }
        throw new Error(errorMsg);
      }

      const data = await res.json();
      setTokens(data.tokens || []);
      setMessage('');
    } catch (err) {
      setMessage(`Error: ${err.message}`);
      console.error("Error fetching tokens:", err);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  // Create new token
  const createToken = async (name = 'Default Key') => {
    setIsLoading(true);
    setMessage('');
    
    try {
      const res = await fetch(`${API_BASE_URL}/generate-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ name })
      });

      if (!res.ok) {
        const errorMsg = await extractError(res);
        if (res.status === 401) {
          setMessage('Error: Please log in again.');
          return;
        }
        throw new Error(errorMsg);
      }

      const data = await res.json();
      setNewKey(data.token);
      setShowKeyModal(true);
      await fetchTokens(); // Refresh token list
    } catch (err) {
      setMessage(`Error: ${err.message}`);
      console.error("Error creating token:", err);
    } finally {
      setIsLoading(false);
    }
  };

  // Delete token
  const deleteToken = async (id) => {
    if (!window.confirm('Are you sure you want to delete this API key?')) return;
    
    setIsLoading(true);
    setMessage('');
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/tokens/${id}`, {
        method: 'DELETE',
        credentials: 'include'
      });

      if (!res.ok) {
        const errorMsg = await extractError(res);
        if (res.status === 401) {
          setMessage('Error: Please log in again.');
          return;
        }
        throw new Error(errorMsg);
      }

      // Remove token from UI
      setTokens(prev => prev.filter(t => t.id !== id));
      setMessage('Token deleted successfully.');
      setTimeout(() => setMessage(''), 2000);
    } catch (err) {
      setMessage(`Error: ${err.message}`);
      console.error("Error deleting token:", err);
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch tokens when component mounts or authentication status changes
  useEffect(() => {
    if (isAuthenticated) {
      fetchTokens();
    } else {
      setTokens([]);
      setMessage('Please log in to manage API tokens.');
    }
  }, [isAuthenticated, fetchTokens]);

  if (!isAuthenticated) {
    return (
      <div className="chat-board">
        <div className="token-section">
          <h2>API Token Management</h2>
          <p className="no-tokens-text">Please log in to manage your API keys.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-board">
      <Navbar/>
      <div className="token-section">
        <h2>API Token Management</h2>

        {message && (
          <div className={message.startsWith('Error') ? 'auth-form-error info-message' : 'info-message'}>
            {message}
          </div>
        )}

        <div className="gen-token-container">
          <div className="gen-token-title">
            <h3>
              API Keys
            </h3>
            <p>Manage your API keys. Remember to keep your API keys safe to prevent unauthorized access.</p>
          </div>
          <button
            onClick={() => createToken()}
            disabled={isLoading}
            className="generate-button"
          >
            {isLoading ? 'Generating...' : 'Create API Key'}
          </button>
        </div>

        <div className="available-tokens-container">
          {isLoading && tokens.length === 0 ? (
            <p className="loading-text">Loading...</p>
          ) : tokens.length === 0 ? (
            <p className="no-tokens-text">No API keys found. Create your first one above.</p>
          ) : (
            <ul className="token-list">
              {tokens.map(token => (
                <li key={token.id} className="token-item">
                  <span className="token-name">{token.name}</span>
                  <span className="token-value">••••••••••{token.token.slice(-8)}</span>
                  <button 
                    onClick={() => deleteToken(token.id)} 
                    className="action-button delete-button"
                    disabled={isLoading}
                  >
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <GeneratedKeyModal
        isOpen={showKeyModal}
        apiKey={newKey}
        onClose={() => setShowKeyModal(false)}
      />
    </div>
  );
}