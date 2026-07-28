import React, { useState } from 'react';
import './App.css';
import SummaryPanel from './components/SummaryPanel';
import PriorityPanel from './components/PriorityPanel';

function App() {
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('summary');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const API_URL = 'http://localhost:5000/api';

  // Registration handler
  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const formData = new FormData(e.target);
    const name = formData.get('name');
    const email = formData.get('email');

    try {
      const response = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email }),
      });

      if (!response.ok) {
        throw new Error('Registration failed');
      }

      const data = await response.json();
      setUser({ name, email });
      setActiveTab('summary');
    } catch (err) {
      setError(err.message || 'Failed to register');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setUser(null);
    setActiveTab('summary');
    setError('');
  };

  if (!user) {
    return (
      <div className="login-container">
        <div className="login-card">
          <h1>Email Manager</h1>
          <p className="subtitle">Manage, summarize, and prioritize your emails</p>

          <form onSubmit={handleRegister} className="login-form">
            <div className="form-group">
              <label htmlFor="name">Full Name</label>
              <input
                id="name"
                name="name"
                type="text"
                placeholder="John Doe"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input
                id="email"
                name="email"
                type="email"
                placeholder="john@example.com"
                required
              />
            </div>

            {error && <div className="error-message">{error}</div>}

            <button type="submit" disabled={loading} className="btn-primary">
              {loading ? 'Loading...' : 'Get Started'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <h1>Email Manager</h1>
          <div className="header-info">
            <span>{user.name}</span>
            <span className="email-badge">{user.email}</span>
            <button onClick={handleLogout} className="btn-logout">
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="app-body">
        {/* Side Navigation */}
        <aside className="sidebar">
          <nav className="nav-menu">
            <button
              className={`nav-item ${activeTab === 'summary' ? 'active' : ''}`}
              onClick={() => setActiveTab('summary')}
            >
              <span className="icon">📊</span>
              <span>Summary</span>
            </button>
            <button
              className={`nav-item ${activeTab === 'priority' ? 'active' : ''}`}
              onClick={() => setActiveTab('priority')}
            >
              <span className="icon">⚡</span>
              <span>Priority</span>
            </button>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="main-content">
          {error && <div className="error-message">{error}</div>}

          {activeTab === 'summary' && (
            <SummaryPanel userEmail={user.email} apiUrl={API_URL} />
          )}

          {activeTab === 'priority' && (
            <PriorityPanel userEmail={user.email} apiUrl={API_URL} />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
