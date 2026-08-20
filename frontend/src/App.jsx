import { useState, useEffect, useRef } from 'react';
import { getCurrentUser, fetchAuthSession, signOut } from 'aws-amplify/auth';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
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

  useEffect(() => {
    fetchAuthSession().then(session => {
      setJwtToken(session.tokens.idToken.toString());
    }).catch(err => console.error("Error getting session", err));
  }, []);

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
            const sorted = data.data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            const recentData = sorted.slice(-40);

            const grouped = {};
            recentData.forEach(item => {
              const time = new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
              if (!grouped[time]) {
                grouped[time] = { time, Temperature: null, Occupancy: null, Energy: null };
              }
              if (item.event_type === 'temperature') grouped[time].Temperature = parseFloat(item.temperature_c);
              if (item.event_type === 'occupancy') grouped[time].Occupancy = parseInt(item.occupancy_count);
              if (item.event_type === 'energy') grouped[time].Energy = parseFloat(item.energy_kwh);
            });
            const chartData = Object.values(grouped);

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
    const fetchInterval = setInterval(fetchAllStats, 3000); 
    return () => clearInterval(fetchInterval);
  }, [jwtToken]);

  const toggleSimulator = () => {
    if (simulating) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
      setSimulating(false);
      setSimLog("Simulator Paused.");
    } else {
      setSimulating(true);
      injectAllEvents();
      // Blast all 15 every 4 seconds
      simIntervalRef.current = setInterval(injectAllEvents, 3000); 
    }
  };

  const injectAllEvents = async () => {
    if (!jwtToken) return;
    
    setSimLog(`Transmitting data for all 15 sensors simultaneously...`);
    const promises = [];

    for (const bldg of BUILDINGS) {
      for (const type of EVENT_TYPES) {
        // slight jitter so they don't hit the exact millisecond
        const delay = Math.random() * 500;
        const p = new Promise(resolve => {
          setTimeout(async () => {
            const payload = {
              building_id: bldg,
              event_type: type,
              timestamp: new Date().toISOString()
            };

            if (type === 'temperature') {
              payload.temperature_c = (18 + Math.random() * 12).toFixed(1);
              payload.alert = payload.temperature_c > 28;
            } else if (type === 'occupancy') {
              // Create a smooth varying graph
              payload.occupancy_count = Math.floor(Math.random() * 150) + 10;
            } else if (type === 'energy') {
              payload.energy_kwh = (50 + Math.random() * 100).toFixed(1);
            }

            try {
              await fetch(`${API_URL}/events`, {
                method: 'POST',
                headers: { 
                  'Content-Type': 'application/json',
                  'Authorization': jwtToken
                },
                body: JSON.stringify(payload)
              });
              resolve();
            } catch (err) {
              resolve();
            }
          }, delay);
        });
        promises.push(p);
      }
    }

    await Promise.all(promises);
    setSimLog(`Successfully transmitted 15 events to AWS DynamoDB.`);
  };

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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
            {BUILDINGS.map(bldg => {
              const bldgStats = stats[bldg];
              const chartData = bldgStats?.chartData || [];
              const lastTemp = bldgStats?.temp?.temperature_c || '--';
              const lastOcc = bldgStats?.occ?.occupancy_count || '--';
              const lastNrg = bldgStats?.nrg?.energy_kwh || '--';

              return (
                <div key={bldg} style={{ background: 'rgba(255,255,255,0.03)', padding: '25px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)' }}>
                  <h2 style={{ margin: '0 0 20px 0', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '10px', display: 'flex', justifyContent: 'space-between' }}>
                    {bldg}
                    <span style={{ fontSize: '14px', color: '#94a3b8', fontWeight: 'normal' }}>
                      {bldgStats?.lastUpdated ? `Live - Last 40 events` : 'Waiting for telemetry...'}
                    </span>
                  </h2>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
                    
                    {/* Temperature Chart */}
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '15px', borderRadius: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                        <span style={{ color: '#fbbf24', fontWeight: 'bold' }}>Temperature</span>
                        <span style={{ color: '#f8fafc', fontSize: '1.2rem' }}>{lastTemp} °C</span>
                      </div>
                      <div style={{ width: '100%', height: 180 }}>
                        <ResponsiveContainer>
                          <LineChart data={chartData}>
                            <XAxis dataKey="time" hide={true} />
                            <YAxis domain={['dataMin - 2', 'dataMax + 2']} hide={true} />
                            <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', padding: '12px 18px', fontSize: '1.1rem', borderRadius: '8px' }} />
                            <ReferenceLine y={28} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'top', value: 'Alert > 28°C', fill: '#ef4444', fontSize: 10 }} />
                            <Line type="monotone" dataKey="Temperature" stroke="#fbbf24" strokeWidth={3} dot={{r: 3, fill: "#fbbf24", stroke: "none"}} activeDot={{r: 6}} connectNulls={true} isAnimationActive={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Occupancy Chart */}
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '15px', borderRadius: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                        <span style={{ color: '#60a5fa', fontWeight: 'bold' }}>Occupancy</span>
                        <span style={{ color: '#f8fafc', fontSize: '1.2rem' }}>{lastOcc} People</span>
                      </div>
                      <div style={{ width: '100%', height: 180 }}>
                        <ResponsiveContainer>
                          <LineChart data={chartData}>
                            <XAxis dataKey="time" hide={true} />
                            <YAxis domain={[0, 220]} hide={true} />
                            <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', padding: '12px 18px', fontSize: '1.1rem', borderRadius: '8px' }} />
                            <ReferenceLine y={150} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'top', value: 'Capacity > 150', fill: '#ef4444', fontSize: 10 }} />
                            <Line type="monotone" dataKey="Occupancy" stroke="#60a5fa" strokeWidth={3} dot={{r: 3, fill: "#60a5fa", stroke: "none"}} activeDot={{r: 6}} connectNulls={true} isAnimationActive={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Energy Chart */}
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '15px', borderRadius: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                        <span style={{ color: '#10b981', fontWeight: 'bold' }}>Energy</span>
                        <span style={{ color: '#f8fafc', fontSize: '1.2rem' }}>{lastNrg} kWh</span>
                      </div>
                      <div style={{ width: '100%', height: 180 }}>
                        <ResponsiveContainer>
                          <LineChart data={chartData}>
                            <XAxis dataKey="time" hide={true} />
                            <YAxis domain={['dataMin - 10', 'dataMax + 10']} hide={true} />
                            <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', padding: '12px 18px', fontSize: '1.1rem', borderRadius: '8px' }} />
                            <ReferenceLine y={120} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'top', value: 'High > 120 kWh', fill: '#ef4444', fontSize: 10 }} />
                            <Line type="monotone" dataKey="Energy" stroke="#10b981" strokeWidth={3} dot={{r: 3, fill: "#10b981", stroke: "none"}} activeDot={{r: 6}} connectNulls={true} isAnimationActive={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

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
