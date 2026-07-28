import React, { useState, useEffect } from 'react';
import '../styles/panels.css';

function SummaryPanel({ userEmail, apiUrl }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [dateMode, setDateMode] = useState('all'); // all, specific, range

  useEffect(() => {
    // Load default (today's data)
    const today = new Date();
    loadSummary(
      today.toISOString().split('T')[0],
      today.toISOString().split('T')[0]
    );
  }, []);

  const loadSummary = async (start, end) => {
    setLoading(true);
    setError('');

    try {
      const params = new URLSearchParams();
      if (start) params.append('startDate', start);
      if (end) params.append('endDate', end);

      const response = await fetch(
        `${apiUrl}/emails/summary`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: userEmail,
            startDate: start,
            endDate: end,
          }),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to load summary');
      }

      const result = await response.json();
      setData(result.summary);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadToday = () => {
    const today = new Date();
    const dateStr = today.toISOString().split('T')[0];
    loadSummary(dateStr, dateStr);
    setDateMode('specific');
  };

  const handleLoadRange = () => {
    if (startDate && endDate) {
      loadSummary(startDate, endDate);
    } else {
      setError('Please select both start and end dates');
    }
  };

  const handleLoadAll = () => {
    loadSummary(null, null);
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

  return (
    <div className="panel-container">
      <div className="panel-header">
        <h2>📊 Email Summary</h2>
        <p className="subtitle">Top 3 emails and meetings</p>
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
        <div className="loading">Loading emails...</div>
      ) : data ? (
        <>
          {/* Stats */}
          <div className="stats-section">
            <div className="stat-card">
              <span className="stat-number">{data.total_emails}</span>
              <span className="stat-label">Total Emails</span>
            </div>
            <div className="stat-card">
              <span className="stat-number">{data.top_emails.length}</span>
              <span className="stat-label">Regular Emails</span>
            </div>
            <div className="stat-card">
              <span className="stat-number">{data.top_meetings.length}</span>
              <span className="stat-label">Meetings</span>
            </div>
          </div>

          {/* Top Emails */}
          <section className="email-section">
            <h3 className="section-title">📧 Top Emails</h3>
            {data.top_emails.length > 0 ? (
              <div className="email-list">
                {data.top_emails.map((email) => (
                  <div key={email.id} className="email-card">
                    <div className="email-header">
                      <h4 className="email-subject">{email.subject}</h4>
                      <span className="email-time">
                        {formatDate(email.received_at)}
                      </span>
                    </div>
                    <p className="email-from">{email.from_email}</p>
                    <p className="email-preview">{email.preview}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-state">No emails found</p>
            )}
          </section>

          {/* Top Meetings */}
          <section className="email-section">
            <h3 className="section-title">📅 Top Meetings</h3>
            {data.top_meetings.length > 0 ? (
              <div className="email-list">
                {data.top_meetings.map((meeting) => (
                  <div key={meeting.id} className="email-card meeting-card">
                    <div className="email-header">
                      <h4 className="email-subject">{meeting.subject}</h4>
                      <span className="email-time">
                        {formatDate(meeting.received_at)}
                      </span>
                    </div>
                    <p className="email-from">{meeting.from_email}</p>
                    <p className="email-preview">{meeting.preview}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-state">No meetings found</p>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}

export default SummaryPanel;
