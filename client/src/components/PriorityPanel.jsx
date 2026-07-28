import React, { useState, useEffect } from 'react';
import '../styles/panels.css';

function PriorityPanel({ userEmail, apiUrl }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [dateMode, setDateMode] = useState('all');

  useEffect(() => {
    // Load default (today's data)
    const today = new Date();
    loadPriorities(
      today.toISOString().split('T')[0],
      today.toISOString().split('T')[0]
    );
  }, []);

  const loadPriorities = async (start, end) => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${apiUrl}/emails/priorities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: userEmail,
          startDate: start,
          endDate: end,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to load priorities');
      }

      const result = await response.json();
      setData(result.priorities);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadToday = () => {
    const today = new Date();
    const dateStr = today.toISOString().split('T')[0];
    loadPriorities(dateStr, dateStr);
    setDateMode('specific');
  };

  const handleLoadRange = () => {
    if (startDate && endDate) {
      loadPriorities(startDate, endDate);
    } else {
      setError('Please select both start and end dates');
    }
  };

  const handleLoadAll = () => {
    loadPriorities(null, null);
    setDateMode('all');
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high':
        return '#ef4444'; // Red
      case 'medium':
        return '#f59e0b'; // Amber
      case 'low':
        return '#10b981'; // Green
      default:
        return '#6b7280'; // Gray
    }
  };

  const getPriorityIcon = (priority) => {
    switch (priority) {
      case 'high':
        return '🔴';
      case 'medium':
        return '🟡';
      case 'low':
        return '🟢';
      default:
        return '⚪';
    }
  };

  return (
    <div className="panel-container">
      <div className="panel-header">
        <h2>⚡ Priority Management</h2>
        <p className="subtitle">Emails organized by priority level</p>
      </div>

      {/* Date Filter Controls */}
      <div className="filter-section">
        <div className="filter-buttons">
          <button
            className={`filter-btn ${dateMode === 'all' ? 'active' : ''}`}
            onClick={handleLoadAll}
          >
            All Time
          </button>
          <button
            className={`filter-btn ${dateMode === 'specific' ? 'active' : ''}`}
            onClick={handleLoadToday}
          >
            Today
          </button>
          <button
            className={`filter-btn ${dateMode === 'range' ? 'active' : ''}`}
            onClick={() => setDateMode('range')}
          >
            Date Range
          </button>
        </div>

        {dateMode === 'range' && (
          <div className="date-range-selector">
            <div className="date-input-group">
              <label>From</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="date-input-group">
              <label>To</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
            <button
              onClick={handleLoadRange}
              className="btn-primary"
              disabled={!startDate || !endDate}
            >
              Load
            </button>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading ? (
        <div className="loading">Loading priorities...</div>
      ) : data ? (
        <>
          {/* Priority Stats */}
          <div className="stats-section">
            <div className="stat-card high-priority">
              <span className="stat-number">{data.high_priority.length}</span>
              <span className="stat-label">High Priority</span>
            </div>
            <div className="stat-card medium-priority">
              <span className="stat-number">{data.medium_priority.length}</span>
              <span className="stat-label">Medium Priority</span>
            </div>
            <div className="stat-card low-priority">
              <span className="stat-number">{data.low_priority.length}</span>
              <span className="stat-label">Low Priority</span>
            </div>
          </div>

          {/* High Priority */}
          <section className="priority-section high">
            <h3 className="section-title">
              {getPriorityIcon('high')} High Priority - Requires Immediate Attention
            </h3>
            {data.high_priority.length > 0 ? (
              <div className="priority-list">
                {data.high_priority.map((email) => (
                  <div
                    key={email.id}
                    className="priority-card"
                    style={{ borderLeftColor: getPriorityColor('high') }}
                  >
                    <div className="priority-header">
                      <div className="priority-title">
                        <span className="priority-icon">
                          {getPriorityIcon('high')}
                        </span>
                        <h4>{email.subject}</h4>
                      </div>
                      <span className="email-time">
                        {formatDate(email.received_at)}
                      </span>
                    </div>
                    <p className="email-from">{email.from_email}</p>
                    <p className="priority-reason">
                      <strong>Reason:</strong> {email.reason}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-state">No high priority emails</p>
            )}
          </section>

          {/* Medium Priority */}
          <section className="priority-section medium">
            <h3 className="section-title">
              {getPriorityIcon('medium')} Medium Priority - Review Soon
            </h3>
            {data.medium_priority.length > 0 ? (
              <div className="priority-list">
                {data.medium_priority.map((email) => (
                  <div
                    key={email.id}
                    className="priority-card"
                    style={{ borderLeftColor: getPriorityColor('medium') }}
                  >
                    <div className="priority-header">
                      <div className="priority-title">
                        <span className="priority-icon">
                          {getPriorityIcon('medium')}
                        </span>
                        <h4>{email.subject}</h4>
                      </div>
                      <span className="email-time">
                        {formatDate(email.received_at)}
                      </span>
                    </div>
                    <p className="email-from">{email.from_email}</p>
                    <p className="priority-reason">
                      <strong>Reason:</strong> {email.reason}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-state">No medium priority emails</p>
            )}
          </section>

          {/* Low Priority */}
          <section className="priority-section low">
            <h3 className="section-title">
              {getPriorityIcon('low')} Low Priority - Can Be Reviewed Later
            </h3>
            {data.low_priority.length > 0 ? (
              <div className="priority-list">
                {data.low_priority.map((email) => (
                  <div
                    key={email.id}
                    className="priority-card"
                    style={{ borderLeftColor: getPriorityColor('low') }}
                  >
                    <div className="priority-header">
                      <div className="priority-title">
                        <span className="priority-icon">
                          {getPriorityIcon('low')}
                        </span>
                        <h4>{email.subject}</h4>
                      </div>
                      <span className="email-time">
                        {formatDate(email.received_at)}
                      </span>
                    </div>
                    <p className="email-from">{email.from_email}</p>
                    <p className="priority-reason">
                      <strong>Reason:</strong> {email.reason}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-state">No low priority emails</p>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}

export default PriorityPanel;
