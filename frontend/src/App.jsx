import { useState, useEffect, useRef } from 'react';
import { getCurrentUser, fetchAuthSession, signOut } from 'aws-amplify/auth';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
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
            // Sort oldest to newest for the chart
            const sorted = data.data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            
            // Filter to last 2 minutes (120 seconds)
            const twoMinsAgo = new Date(Date.now() - 120 * 1000);
            const recentData = sorted.filter(e => new Date(e.timestamp) > twoMinsAgo);

            // Group by time interval (e.g. 10s buckets) to make a clean chart
            // For simplicity, we just map the raw events into a chartable array
            const chartData = [];
            let currentTemp = 0;
            let currentOcc = 0;
            let currentNrg = 0;

            recentData.forEach(item => {
              const time = new Date(item.timestamp).toLocaleTimeString([], { hour12: false, minute: '2-digit', second:'2-digit' });
              
              if (item.event_type === 'temperature') currentTemp = parseFloat(item.temperature_c);
              if (item.event_type === 'occupancy') currentOcc = parseInt(item.occupancy_count);
              if (item.event_type === 'energy') currentNrg = parseFloat(item.energy_kwh);

              chartData.push({
                time,
                temp: currentTemp || null,
                occ: currentOcc || null,
                nrg: currentNrg || null
              });
            });

            // Get latest values for the numeric display
            const latestReversed = [...sorted].reverse();
            
            setStats(prev => ({
              ...prev,
              [bldg]: {
                temp: latestReversed.find(e => e.event_type === 'temperature'),
                occ: latestReversed.find(e => e.event_type === 'occupancy'),
                nrg: latestReversed.find(e => e.event_type === 'energy'),
                chartData: chartData,
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
    const fetchInterval = setInterval(fetchAllStats, 10000); // Fetch every 10 seconds
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
      simIntervalRef.current = setInterval(injectRandomEvent, 2500); // inject randomly
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
              const chartData = bldgStats?.chartData || [];

              return (
                <div className="tile" key={bldg} style={{ gridColumn: 'span 1' }}>
                  <h3 style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    {bldg} 
                    <span className="timestamp" style={{ fontSize: '0.75rem', fontWeight: 'normal' }}>
                      {bldgStats?.lastUpdated ? `Live` : 'Waiting...'}
                    </span>
                  </h3>
                  
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
                    <div className="metric" style={{ flex: 1, padding: 0, border: 'none' }}>
                      <span className="metric-title" style={{ fontSize: '0.75rem' }}>Temp</span>
                      <span className={`metric-val ${temp?.alert ? 'alert' : ''}`} style={{ fontSize: '1.2rem' }}>
                        {temp ? `${temp.temperature_c} C` : '--'}
                      </span>
                    </div>
                    <div className="metric" style={{ flex: 1, padding: 0, border: 'none' }}>
                      <span className="metric-title" style={{ fontSize: '0.75rem' }}>Occupancy</span>
                      <span className="metric-val" style={{ fontSize: '1.2rem', color: '#60a5fa' }}>
                        {occ ? occ.occupancy_count : '--'}
                      </span>
                    </div>
                    <div className="metric" style={{ flex: 1, padding: 0, border: 'none' }}>
                      <span className="metric-title" style={{ fontSize: '0.75rem' }}>Energy</span>
                      <span className="metric-val" style={{ fontSize: '1.2rem', color: '#10b981' }}>
                        {nrg ? nrg.energy_kwh : '--'}
                      </span>
                    </div>
                  </div>

                  {/* The Live Chart */}
                  <div style={{ width: '100%', height: 180, marginTop: '10px' }}>
                    {chartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                          <XAxis dataKey="time" stroke="#94a3b8" fontSize={10} tick={{fill: '#94a3b8'}} />
                          <YAxis stroke="#94a3b8" fontSize={10} tick={{fill: '#94a3b8'}} width={30} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '4px', color: '#fff' }}
                            itemStyle={{ color: '#fff' }}
                          />
                          <Line type="monotone" dataKey="occ" name="Occupancy" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#475569' }}>
                        No data yet
                      </div>
                    )}
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
