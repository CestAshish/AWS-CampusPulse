import { useState, useEffect, useRef } from 'react';
import { getCurrentUser, fetchAuthSession } from 'aws-amplify/auth';
import Login from './Login.jsx';

const API_URL = "https://w1k2uj34k5.execute-api.eu-north-1.amazonaws.com/prod";
const BUILDINGS = ["BLDG-A", "BLDG-B", "LIBRARY", "GYM", "Engineering"];
const EVENT_TYPES = ["temperature", "occupancy", "energy"];

function Dashboard({ onLogout, userEmail }) {
  const [stats, setStats] = useState({});
  const [simulating, setSimulating] = useState(false);
  const [simLog, setSimLog] = useState("System Idle. Click 'Start Live Simulator' to begin.");
  const [jwtToken, setJwtToken] = useState(null);
  const [showSimPanel, setShowSimPanel] = useState(false);
  const simIntervalRef = useRef(null);

  // Fetch JWT Token on mount
  useEffect(() => {
    fetchAuthSession().then(session => {
      setJwtToken(session.tokens.idToken.toString());
    }).catch(err => console.error("Error getting session", err));
  }, []);

  // Fetch Stats Loop
  useEffect(() => {
    if (!jwtToken) return;

    const fetchAllStats = async () => {
      for (const bldg of BUILDINGS) {
        try {
          const res = await fetch(`${API_URL}/stats?building_id=${bldg}`, {
            headers: { 'Authorization': jwtToken }
          });
          if (!res.ok) continue;
          const data = await res.json();
          if (data.data && data.data.length > 0) {
            const sorted = data.data.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            setStats(prev => ({
              ...prev,
              [bldg]: {
                temp: sorted.find(e => e.event_type === 'temperature'),
                occ: sorted.find(e => e.event_type === 'occupancy'),
                nrg: sorted.find(e => e.event_type === 'energy'),
                lastUpdated: new Date().toLocaleTimeString()
              }
            }));
          }
        } catch (err) {
          console.error(`Failed to fetch stats for ${bldg}`, err);
        }
      }
    };

    fetchAllStats();
    const fetchInterval = setInterval(fetchAllStats, 5000);
    return () => clearInterval(fetchInterval);
  }, [jwtToken]);

  // Simulator Logic
  const toggleSimulator = () => {
    if (simulating) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
      setSimulating(false);
      setSimLog("Simulator Paused.");
    } else {
      setSimulating(true);
      injectRandomEvent();
      simIntervalRef.current = setInterval(injectRandomEvent, 2000);
    }
  };

  const injectRandomEvent = async () => {
    if (!jwtToken) return;
    const bldg = BUILDINGS[Math.floor(Math.random() * BUILDINGS.length)];
    const type = EVENT_TYPES[Math.floor(Math.random() * EVENT_TYPES.length)];
    
    const payload = {
      building_id: bldg,
      event_type: type,
      timestamp: new Date().toISOString()
    };

    if (type === 'temperature') {
      payload.temperature_c = (18 + Math.random() * 12).toFixed(1);
      payload.alert = payload.temperature_c > 28;
    } else if (type === 'occupancy') {
      payload.occupancy_count = Math.floor(Math.random() * 200);
    } else if (type === 'energy') {
      payload.energy_kwh = (50 + Math.random() * 100).toFixed(1);
    }

    setSimLog(`Transmitting: ${bldg} -> ${type}...`);

    try {
      await fetch(`${API_URL}/events`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': jwtToken
        },
        body: JSON.stringify(payload)
      });
      setSimLog(`Successfully transmitted ${type} data for ${bldg} to AWS DynamoDB.`);
    } catch (err) {
      setSimLog(`Error transmitting to AWS: ${err.message}`);
    }
  };

  // Cleanup simulator on unmount
  useEffect(() => {
    return () => {
      if (simIntervalRef.current) clearInterval(simIntervalRef.current);
    };
  }, []);

  return (
    <div className="full-layout">
      <header className="top-navbar">
        <h2 style={{ margin: 0, color: '#f1f5f9' }}>CampusPulse</h2>
        
        <div className="header-actions">
          <button 
            className="btn btn-sim-toggle" 
            onClick={() => setShowSimPanel(!showSimPanel)}
          >
            {showSimPanel ? 'Close Simulator' : 'IoT Simulator Tools'}
          </button>
          
          <span className="user-email">Welcome, <strong>{userEmail}</strong></span>
          <button onClick={onLogout} className="btn btn-stop">Sign Out</button>
        </div>
      </header>

      <main className="main-content-full">
        {showSimPanel && (
          <div className="simulator-dropdown">
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
              <button className={`btn ${simulating ? 'btn-stop' : ''}`} onClick={toggleSimulator}>
                {simulating ? 'Stop Simulator' : 'Start Live Simulator'}
              </button>
              <div className="sim-log" style={{ color: simulating ? '#10b981' : '#94a3b8' }}>
                {simLog}
              </div>
            </div>
          </div>
        )}

        <section>
          <div className="grid">
            {BUILDINGS.map(bldg => {
              const bldgStats = stats[bldg];
              const temp = bldgStats?.temp;
              const occ = bldgStats?.occ;
              const nrg = bldgStats?.nrg;

              return (
                <div className="tile" key={bldg}>
                  <h3>
                    {bldg} 
                    <span className="timestamp">
                      {bldgStats?.lastUpdated ? `Last updated: ${bldgStats.lastUpdated}` : 'Waiting for data...'}
                    </span>
                  </h3>
                  <div className="metric">
                    <span className="metric-title">Temperature</span>
                    <span className={`metric-val ${temp?.alert ? 'alert' : ''}`}>
                      {temp ? `${temp.temperature_c} C` : '--'}
                    </span>
                  </div>
                  <div className="metric">
                    <span className="metric-title">Occupancy</span>
                    <span className="metric-val">{occ ? occ.occupancy_count : '--'}</span>
                  </div>
                  <div className="metric">
                    <span className="metric-title">Energy (kWh)</span>
                    <span className="metric-val">{nrg ? nrg.energy_kwh : '--'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
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
        setUserEmail(user.username || user.signInDetails?.loginId || 'Admin');
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
      getCurrentUser().then(user => setUserEmail(user.username || user.signInDetails?.loginId || 'Admin'));
      setIsLoggedIn(true);
    }} />;
  }

  return <Dashboard onLogout={() => setIsLoggedIn(false)} userEmail={userEmail} />;
}

export default App;
