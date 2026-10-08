import { useState, useEffect, useRef, useCallback } from 'react';
import { getCurrentUser, fetchAuthSession, signOut } from 'aws-amplify/auth';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import Login from './Login.jsx';

const API_URL = "https://w1k2uj34k5.execute-api.eu-north-1.amazonaws.com/prod";
const BUILDINGS = ["BLDG-A", "BLDG-B", "LIBRARY", "GYM", "Engineering"];
const POLL_MS = 5000;

// Must match EVENT_TYPES in backend/src/common.py and the CloudWatch alarms.
const METRICS = {
  temperature: { label: 'Temperature', field: 'temperature_c', unit: '°C', color: '#fbbf24', threshold: 28, thresholdLabel: 'Alert > 28°C', domain: ['dataMin - 2', 'dataMax + 2'] },
  occupancy: { label: 'Occupancy', field: 'occupancy_count', unit: 'people', color: '#60a5fa', threshold: 150, thresholdLabel: 'Capacity > 150', domain: [0, 220] },
  energy: { label: 'Energy', field: 'energy_kwh', unit: 'kWh', color: '#10b981', threshold: 120, thresholdLabel: 'Surge > 120 kWh', domain: ['dataMin - 10', 'dataMax + 10'] },
};

// Always ask Amplify for the session: it refreshes the ID token when it expires.
async function getSession() {
  const session = await fetchAuthSession();
  const token = session.tokens?.idToken;
  return { token: token?.toString(), groups: token?.payload?.['cognito:groups'] || [] };
}

async function api(path, params) {
  const { token } = await getSession();
  const query = params ? `?${new URLSearchParams(params)}` : '';
  const res = await fetch(`${API_URL}${path}${query}`, { headers: { Authorization: token } });
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

function randomReading(type) {
  // Roughly 1 in 8 readings crosses a threshold so the alert pipeline is visible.
  if (type === 'temperature') return +(19 + Math.random() * 10.5).toFixed(1);
  if (type === 'occupancy') return Math.floor(20 + Math.random() * 150);
  return +(40 + Math.random() * 90).toFixed(1);
}

function toChartData(events) {
  const grouped = {};
  events.forEach(item => {
    const time = new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
    grouped[time] ??= { time };
    const metric = METRICS[item.event_type];
    if (metric && item[metric.field] !== undefined) grouped[time][metric.label] = parseFloat(item[metric.field]);
  });
  return Object.values(grouped);
}

function MetricChart({ type, chartData, summary }) {
  const m = METRICS[type];
  const latest = summary?.latest;
  const over = latest !== undefined && latest > m.threshold;
  return (
    <div className="chart-card">
      <div className="chart-head">
        <span style={{ color: m.color, fontWeight: 'bold' }}>{m.label}</span>
        <span className={over ? 'value over' : 'value'}>{latest ?? '--'} {m.unit}</span>
      </div>
      <div className="chart-sub">
        {summary ? `avg ${summary.avg} · min ${summary.min} · max ${summary.max} · ${summary.anomalies} anomalies / ${summary.count}` : 'no readings yet'}
      </div>
      <div style={{ width: '100%', height: 170 }}>
        <ResponsiveContainer>
          <LineChart data={chartData}>
            <XAxis dataKey="time" hide={true} />
            <YAxis domain={m.domain} hide={true} />
            <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', padding: '12px 18px', fontSize: '1.1rem', borderRadius: '8px' }} />
            <ReferenceLine y={m.threshold} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'top', value: m.thresholdLabel, fill: '#ef4444', fontSize: 10 }} />
            <Line type="monotone" dataKey={m.label} stroke={m.color} strokeWidth={3} dot={{ r: 3, fill: m.color, stroke: "none" }} activeDot={{ r: 6 }} connectNulls={true} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function CampusOverview({ campus, alerts }) {
  const ranking = campus?.energy_ranking || [];
  const overloaded = campus?.overloaded || [];
  const maxEnergy = Math.max(1, ...ranking.map(r => r.avg_energy_kwh));
  return (
    <section className="overview-grid">
      <div className="panel">
        <h3>Energy ranking <span className="muted">avg kWh, recent readings</span></h3>
        {ranking.length === 0 && <p className="muted">Waiting for telemetry...</p>}
        {ranking.map(r => (
          <div key={r.building_id} className="bar-row">
            <span className="bar-label">{r.building_id}</span>
            <div className="bar-track"><div className="bar-fill" style={{ width: `${(r.avg_energy_kwh / maxEnergy) * 100}%` }} /></div>
            <span className="bar-value">{r.avg_energy_kwh}</span>
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>Occupancy status <span className="muted">capacity 150</span></h3>
        {overloaded.length === 0
          ? <p className="ok">All buildings within capacity</p>
          : overloaded.map(o => <p key={o.building_id} className="danger">{o.building_id}: {o.occupancy} people (overloaded)</p>)}
      </div>

      <div className="panel">
        <h3>Latest alerts <span className="muted">server-side anomaly detection</span></h3>
        {alerts.length === 0 && <p className="muted">No anomalies detected</p>}
        <div className="alert-list">
          {alerts.slice(0, 8).map(a => {
            const m = METRICS[a.event_type];
            return (
              <div key={`${a.building_id}-${a.timestamp}`} className="alert-row">
                <span className="danger">●</span>
                <span>{new Date(a.timestamp).toLocaleTimeString()}</span>
                <strong>{a.building_id}</strong>
                <span>{m ? `${m.label} ${a[m.field]} ${m.unit}` : a.event_type}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function Dashboard({ onLogout, userEmail }) {
  const [stats, setStats] = useState({});
  const [campus, setCampus] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [groups, setGroups] = useState(null);
  const [error, setError] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [simLog, setSimLog] = useState("System Idle. Click 'Start Live Simulator' to begin.");
  const [showSimPanel, setShowSimPanel] = useState(false);
  const simIntervalRef = useRef(null);

  const isAdmin = groups?.includes('Admin');
  const canRead = groups?.includes('Admin') || groups?.includes('Staff');
  const role = isAdmin ? 'Admin' : groups?.includes('Staff') ? 'Staff (read-only)' : 'No role';

  useEffect(() => {
    getSession().then(s => setGroups(s.groups)).catch(err => console.error("Error getting session", err));
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [overview, alertData, ...buildings] = await Promise.all([
        api('/stats'),
        api('/alerts', { limit: 20 }),
        ...BUILDINGS.map(b => api('/stats', { building_id: b })),
      ]);
      setCampus(overview);
      setAlerts(alertData.alerts || []);
      const next = {};
      buildings.forEach(b => {
        next[b.building_id] = { summary: b.summary, chartData: toChartData(b.data || []), total: b.total_events };
      });
      setStats(next);
      setError('');
    } catch (err) {
      console.error(err);
      setError(`Could not refresh data (${err.message})`);
    }
  }, []);

  useEffect(() => {
    if (!canRead) return;
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [canRead, refresh]);

  const injectAllEvents = async () => {
    setSimLog('Transmitting 15 sensor readings (5 buildings x 3 sensors)...');
    const { token } = await getSession();
    const results = await Promise.all(BUILDINGS.flatMap(bldg => Object.entries(METRICS).map(([type, m]) =>
      // Spread the burst over 2.5s so it looks like independent devices.
      new Promise(resolve => setTimeout(async () => {
        try {
          const res = await fetch(`${API_URL}/events`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': token },
            body: JSON.stringify({ building_id: bldg, event_type: type, timestamp: new Date().toISOString(), [m.field]: randomReading(type) }),
          });
          resolve(res.ok ? (await res.json()).severity : 'failed');
        } catch {
          resolve('failed');
        }
      }, Math.random() * 2500))
    )));
    const anomalies = results.filter(r => r === 'critical').length;
    const failed = results.filter(r => r === 'failed').length;
    setSimLog(`Sent ${results.length - failed}/15 events · ${anomalies} anomalies detected by the API${failed ? ` · ${failed} failed` : ''}`);
  };

  const toggleSimulator = () => {
    if (simulating) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
      setSimulating(false);
      setSimLog("Simulator Paused.");
    } else {
      setSimulating(true);
      injectAllEvents();
      simIntervalRef.current = setInterval(injectAllEvents, 3000);
    }
  };

  useEffect(() => () => clearInterval(simIntervalRef.current), []);

  return (
    <div className="full-layout">
      <header className="top-navbar">
        <h2 style={{ margin: 0, color: '#f1f5f9' }}>CampusPulse</h2>

        <div className="header-actions">
          {isAdmin && (
            <button className="btn btn-sim-toggle" onClick={() => setShowSimPanel(!showSimPanel)}>
              {showSimPanel ? 'Close Simulator' : 'IoT Simulator Tools'}
            </button>
          )}
          <span className="role-badge">{role}</span>
          <span className="user-email">Welcome, <strong>{userEmail}</strong></span>
          <button onClick={onLogout} className="btn btn-stop">Sign Out</button>
        </div>
      </header>

      <main className="main-content-full">
        {showSimPanel && isAdmin && (
          <div className="simulator-dropdown">
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
              <button className={`btn ${simulating ? 'btn-stop' : ''}`} onClick={toggleSimulator}>
                {simulating ? 'Stop Simulator' : 'Start Live Simulator'}
              </button>
              <div className="sim-log" style={{ color: simulating ? '#10b981' : '#94a3b8' }}>{simLog}</div>
            </div>
          </div>
        )}

        {groups && !canRead && (
          <div className="panel">
            <h3>No dashboard access</h3>
            <p className="muted">Your account is not in the Admin or Staff group. Ask an administrator to assign a role.</p>
          </div>
        )}

        {error && <p className="danger">{error}</p>}

        {canRead && <CampusOverview campus={campus} alerts={alerts} />}

        {canRead && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
            {BUILDINGS.map(bldg => {
              const b = stats[bldg];
              return (
                <div key={bldg} className="building-card">
                  <h2 className="building-head">
                    {bldg}
                    <span className="muted" style={{ fontSize: '14px', fontWeight: 'normal' }}>
                      {b?.total ? `Live · aggregates over last ${b.total} events` : 'Waiting for telemetry...'}
                    </span>
                  </h2>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
                    {Object.keys(METRICS).map(type => (
                      <MetricChart key={type} type={type} chartData={b?.chartData || []} summary={b?.summary?.[type]} />
                    ))}
                  </div>
                </div>
              );
            })}
          </section>
        )}
      </main>
    </div>
  );
}

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [userEmail, setUserEmail] = useState('');

  useEffect(() => {
    const checkUser = async () => {
      try {
        const user = await getCurrentUser();
        setIsLoggedIn(true);
        setUserEmail(user.signInDetails?.loginId || user.username || 'User');
      } catch {
        setIsLoggedIn(false);
      } finally {
        setCheckingAuth(false);
      }
    };
    checkUser();
  }, []);

  if (checkingAuth) {
    return <div className="login-page"><p>Loading...</p></div>;
  }

  if (!isLoggedIn) {
    return <Login onLogin={() => {
      getCurrentUser().then(user => setUserEmail(user.signInDetails?.loginId || user.username || 'User'));
      setIsLoggedIn(true);
    }} />;
  }

  return <Dashboard onLogout={async () => {
    try {
      await signOut();
      setIsLoggedIn(false);
    } catch (error) {
      console.error('Error signing out:', error);
    }
  }} userEmail={userEmail} />;
}

export default App;
