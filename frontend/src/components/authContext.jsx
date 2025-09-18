import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

// const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://backend:8080';
const API_BASE_URL = '/api/backend';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

// Enhanced error handling for Axios responses
const handleAxiosError = (error) => {
  console.error("API Error:", error);

  if (error.response) {
    const { data, status } = error.response;
    
    if (data && typeof data === 'object') {
      // Handle FastAPI error structures
      if (data.detail) {
        if (Array.isArray(data.detail)) {
          return data.detail.map(d => d.msg || d.message || JSON.stringify(d)).join('; ');
        } else if (typeof data.detail === 'string') {
          return data.detail;
        } else if (typeof data.detail === 'object' && data.detail.msg) {
          return data.detail.msg;
        }
      }
      
      if (data.message) return data.message;
      if (data.error) return data.error;
    }
    
    return `Server error: ${status}`;
  } else if (error.request) {
    return "Network error: Unable to connect to server";
  } else {
    return error.message || "An unexpected error occurred";
  }
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Check authentication status on app load
  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const response = await api.post('/auth/refresh');
      setUser(response.data);
      setIsAuthenticated(true);
    } catch (error) {
      console.log("No valid session found");
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await api.post('/login', { email, password });
      setUser(response.data);
      setIsAuthenticated(true);
      return response.data;
    } catch (error) {
      const errorMessage = handleAxiosError(error);
      throw new Error(errorMessage);
    }
  };

  const signup = async (email, password, fullName) => {
    try {
      const response = await api.post('/signup', {
        email,
        password,
        full_name: fullName
      });
      return response.data;
    } catch (error) {
      const errorMessage = handleAxiosError(error);
      throw new Error(errorMessage);
    }
  };

  const logout = async () => {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  const value = {
    user,
    isAuthenticated,
    loading,
    login,
    signup,
    logout,
    checkAuthStatus
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}