import './index.css';
 
function App() {

  return (
<div className="dashboard-layout">
<aside className="sidebar">
<h2>CampusPulse</h2>
<nav style={{ marginTop: '2rem' }}>
<p style={{ padding: '10px 0', cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>📊 Dashboard</p>
<p style={{ padding: '10px 0', cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>📡 Live Events</p>
<p style={{ padding: '10px 0', cursor: 'pointer' }}>⚙️ Settings</p>
</nav>
</aside>
<main className="main-content">
<header style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '1rem', marginBottom: '2rem' }}>
<h1>Admin Overview</h1>
</header>
<section>
<div style={{ background: 'rgba(255,255,255,0.05)', padding: '20px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)' }}>
<h3 style={{ color: '#60a5fa' }}>Welcome to CampusPulse 2026</h3>
<p style={{ marginTop: '10px', color: '#a0aec0' }}>

              Real-time IoT data will appear here once the AWS backend is connected.
</p>
</div>
</section>
</main>
</div>

  );

}
 
export default App;