# --- INSTANT VISUAL FEEDBACK ---
# We put this before the heavy imports so the terminal doesn't look frozen!
print("⏳ Starting up... Loading heavy AI libraries (this takes a few seconds)...")

from flask import Flask, jsonify, request, render_template_string
import pandas as pd
from sklearn.ensemble import IsolationForest
import warnings
import datetime
import math
import random

# Ignore minor background warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)

# --- GLOBAL STATE & AI MODEL ---
df = None
doctor_model = None
current_row_idx = 0

print("📊 Loading CSV dataset into memory...")
try:
    # Load the new long-format CSV
    df = pd.read_csv('synthetic_plant_data.csv')
    
    print(f"🧠 Training AI Brain on {min(10000, len(df))} random rows so it boots fast...")
    
    # Train the IsolationForest for anomaly detection
    train_data = df.sample(min(10000, len(df)))
    X = train_data[['value1']].fillna(0)
    
    doctor_model = IsolationForest(contamination=0.05, random_state=42)
    doctor_model.fit(X)
    print("✅ AI Model successfully trained and active!")
    print("🚀 Server is ready! Hold CTRL and click this link to open the dashboard: http://127.0.0.1:5000")
except Exception as e:
    print(f"⚠️ Warning: Could not train AI. Ensure 'synthetic_plant_data.csv' exists. Error: {e}")

# --- MOCK DATABASE ---
users_db = {
    "admin": {"password": "password", "role": "Plant Manager (Admin)", "status": "approved"},
    "worker1": {"password": "password", "role": "Water Chemistry Engineer", "status": "approved"},
    "worker2": {"password": "password", "role": "Boiler & Draft Engineer", "status": "approved"},
    "worker3": {"password": "password", "role": "Turbine & Load Engineer", "status": "approved"}
}

# --- ROLE-BASED ACCESS CONTROL (RBAC) VISIBILITY ---
sector_mapping = {
    'Water Chemistry Engineer': ['pH', 'Conductivity', 'CCW', 'Feed water', 'Water'],
    'Boiler & Draft Engineer': ['Eco', 'Separator', 'Oxygen', 'Boiler', 'Furnace', 'Draft'],
    'Turbine & Load Engineer': ['Load', 'HRH', 'Main steam', 'Turbine', 'Generator', 'Vacuum'],
}

# --- API ENDPOINTS ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = users_db.get(data.get('username'))
    if user and user['password'] == data.get('password'):
        return jsonify({"success": True, "user": {"username": data.get('username'), "role": user['role'], "status": user['status']}})
    return jsonify({"error": "Invalid secure credentials"}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    if username in users_db:
        return jsonify({"error": "User already exists"}), 400
    
    status = "approved" if data.get('role') == 'Plant Manager (Admin)' else "pending"
    users_db[username] = {"password": data.get('password'), "role": data.get('role'), "status": status}
    
    return jsonify({"success": True, "user": {"username": username, "role": data.get('role'), "status": status}})

@app.route('/api/telemetry', methods=['GET'])
def get_telemetry():
    global current_row_idx, df, doctor_model
    user_role = request.args.get('role', 'Plant Manager (Admin)')
    
    if df is None or doctor_model is None:
        return jsonify({"error": "Data or AI not loaded"}), 500

    # ⏩ FAST-FORWARD: Jump ahead by 25-50 rows to skip long "normal" periods
    current_row_idx += random.randint(25, 50)
    if current_row_idx >= len(df):
        current_row_idx = 0 
        
    row = df.iloc[current_row_idx]
    
    sensor_name = str(row.get('maindes', 'Unknown Sensor'))
    val = float(row.get('value1', 0.0))
    min_val = float(row.get('minval', 0.0))
    max_val = float(row.get('maxval', 0.0))
    
    # 🛑 DEMO MODE: Force a random fault ~10% of the time so you aren't waiting forever
    if random.random() < 0.10:
        if not math.isnan(max_val) and max_val != 0:
            val = max_val * 1.15  # Spike it 15% over the max limit!
        else:
            val = val * 5.0 # Massive spike for sensors without hard limits

    fault_code = 0
    diagnosis = "System Normal"
    
    # 1. Hardware Limit Check (Takes Priority)
    if not math.isnan(min_val) and val < min_val:
        fault_code = 1
        diagnosis = "Limit Exceeded (Low)"
    elif not math.isnan(max_val) and val > max_val:
        fault_code = 1
        diagnosis = "Limit Exceeded (High)"
    else:
        # 2. AI Anomaly Check
        try:
            df_live = pd.DataFrame([[val]], columns=['value1'])
            pred = int(doctor_model.predict(df_live)[0])
            if pred == -1:
                fault_code = 2
                diagnosis = "AI Anomaly Detected"
        except Exception:
            pass

    # --- RBAC FILTERING LOGIC ---
    if user_role in sector_mapping:
        allowed_keywords = sector_mapping[user_role]
        has_access = any(keyword.lower() in sensor_name.lower() for keyword in allowed_keywords)
        
        if not has_access:
            fault_code = 0
            diagnosis = "System Normal"

    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    
    payload = {
        "timestamp": timestamp,
        "station": sensor_name,
        "value": round(val, 4),
        "limit": f"Min: {min_val} | Max: {max_val}",
        "fault_code": fault_code,
        "diagnosis": diagnosis
    }
    
    return jsonify(payload)

# --- FRONTEND UI (React embedded in HTML) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NTPC</title>
    <!-- React & ReactDOM -->
    <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
    <!-- Babel for JSX -->
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>
    
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        dark: { 900: '#0f172a', 950: '#020617' },
                        brand: { 400: '#facc15', 500: '#eab308', 600: '#ca8a04' } // NTPC Gold/Yellow
                    }
                }
            }
        }
    </script>
    <style>
        body { background-color: #020617; color: #f8fafc; font-family: 'Inter', sans-serif; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #0f172a; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
    </style>
</head>
<body>
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useEffect, useRef } = React;

        function App() {
            // --- STATE ---
            const [user, setUser] = useState(null);
            const [authMode, setAuthMode] = useState('login');
            const [creds, setCreds] = useState({ username: '', password: '', role: 'Water Chemistry Engineer' });
            
            // Dashboard State
            const [stream, setStream] = useState([]);
            const [isStreaming, setIsStreaming] = useState(false);
            const [showFaultLog, setShowFaultLog] = useState(false);
            
            // --- AUTH LOGIC ---
            const handleAuth = async (e) => {
                e.preventDefault();
                const endpoint = authMode === 'login' ? '/api/login' : '/api/register';
                try {
                    const res = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(creds)
                    });
                    const data = await res.json();
                    
                    if (res.ok) {
                        setUser(data.user);
                        setIsStreaming(true);
                    } else {
                        alert(data.error);
                    }
                } catch (err) {
                    console.error(err);
                }
            };

            useEffect(() => {
                let interval;
                if (user && user.status === 'approved' && isStreaming) {
                    interval = setInterval(async () => {
                        try {
                            const res = await fetch(`/api/telemetry?role=${user.role}`);
                            const data = await res.json();
                            
                            if (res.ok) {
                                setStream(prev => [data, ...prev].slice(0, 100)); // Keep last 100 rows
                            }
                        } catch (err) {
                            console.error("Telemetry fetch error:", err);
                        }
                    }, 1500); // Poll every 1.5 seconds
                }
                return () => clearInterval(interval);
            }, [user, isStreaming]);

            useEffect(() => {
                lucide.createIcons();
            });

            if (!user) {
                return (
                    <div className="min-h-screen flex items-center justify-center p-4 bg-dark-950">
                        <div className="bg-dark-900 border border-slate-800 p-8 rounded-2xl max-w-md w-full shadow-2xl">
                            <div className="flex justify-center mb-6">
                                <i data-lucide="zap" className="text-brand-500 w-12 h-12"></i>
                            </div>
                            <h1 className="text-4xl font-bold text-center mb-6 tracking-widest text-brand-500">NTPC</h1>
                            
                            <form onSubmit={handleAuth} className="space-y-4">
                                <input required className="w-full bg-dark-950 border border-slate-800 p-3 rounded-lg text-sm text-white focus:border-brand-500 focus:outline-none transition-colors" type="text" placeholder="Worker ID" onChange={e => setCreds({...creds, username: e.target.value})} />
                                <input required className="w-full bg-dark-950 border border-slate-800 p-3 rounded-lg text-sm text-white focus:border-brand-500 focus:outline-none transition-colors" type="password" placeholder="Access Code" onChange={e => setCreds({...creds, password: e.target.value})} />
                                {authMode === 'register' && 
                                    <select className="w-full bg-dark-950 border border-slate-800 p-3 rounded-lg text-sm text-white focus:border-brand-500 focus:outline-none" onChange={e => setCreds({...creds, role: e.target.value})}>
                                        <option>Plant Manager (Admin)</option>
                                        <option>Water Chemistry Engineer</option>
                                        <option>Boiler & Draft Engineer</option>
                                        <option>Turbine & Load Engineer</option>
                                    </select>
                                }
                                <button className="w-full bg-brand-500 hover:bg-brand-400 text-dark-950 py-3 rounded-lg text-sm font-bold transition-colors mt-2">
                                    {authMode === 'login' ? 'Initialize Session' : 'Request Clearance'}
                                </button>
                            </form>
                            
                            <button className="w-full text-slate-500 hover:text-brand-500 text-sm mt-6 transition-colors" onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>
                                {authMode === 'login' ? 'Register New Personnel' : 'Back to Login'}
                            </button>
                        </div>
                    </div>
                );
            }

            if (user.status === 'pending') {
                return (
                    <div className="min-h-screen flex items-center justify-center p-4">
                        <div className="text-center">
                            <i data-lucide="lock" className="w-16 h-16 text-brand-500 mx-auto mb-4"></i>
                            <h2 className="text-2xl font-bold mb-2 text-white">Clearance Pending</h2>
                            <p className="text-slate-400 mb-6">Awaiting Plant Manager approval.</p>
                            <button onClick={() => setUser(null)} className="text-brand-500 hover:text-brand-400">Sign Out</button>
                        </div>
                    </div>
                );
            }

            const faults = stream.filter(s => s.fault_code > 0);
            const latestTick = stream[0] || { value: '--', limit: '--' };

            return (
                <div className="min-h-screen flex flex-col">
                    {/* Navigation Bar */}
                    <nav className="bg-dark-900 border-b border-slate-800 p-4 flex justify-between items-center z-10 shadow-md">
                        <div className="flex items-center gap-3">
                            <i data-lucide="zap" className="text-brand-500"></i>
                            <span className="font-bold text-2xl tracking-widest text-brand-500">NTPC</span>
                        </div>
                        <div className="flex items-center gap-4">
                            {/* Fault Log Button */}
                            <button 
                                onClick={() => setShowFaultLog(true)}
                                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold border transition-colors ${faults.length > 0 ? 'bg-red-500/10 border-red-500/50 text-red-500 hover:bg-red-500/20' : 'bg-slate-800/50 border-slate-700 text-slate-500 cursor-not-allowed'}`}
                            >
                                <i data-lucide="alert-triangle" className="w-4 h-4"></i>
                                Fault Log {faults.length > 0 && `(${faults.length})`}
                            </button>
                            
                            <div className="text-right hidden sm:block border-l border-slate-700 pl-4 ml-2">
                                <div className="text-sm font-bold text-white">{user.username}</div>
                                <div className="text-xs text-brand-500">{user.role}</div>
                            </div>
                            <button onClick={() => setUser(null)} className="bg-dark-950 p-2 rounded hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-white transition-colors ml-2">
                                <i data-lucide="log-out" className="w-4 h-4"></i>
                            </button>
                        </div>
                    </nav>

                    {/* Main Content Area */}
                    <main className="flex-1 p-4 md:p-6 max-w-7xl mx-auto w-full space-y-6">
                        
                        {/* Top Metrics Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <div className="bg-dark-900 p-6 rounded-xl border border-slate-800 shadow-md flex items-center justify-between">
                                <div>
                                    <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1">System Status</p>
                                    <p className="text-2xl font-bold text-emerald-500 flex items-center gap-2">
                                        <span className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></span> Active
                                    </p>
                                </div>
                                <i data-lucide="power" className="text-slate-700 w-10 h-10"></i>
                            </div>
                            
                            <div className="bg-dark-900 p-6 rounded-xl border border-slate-800 shadow-md flex items-center justify-between">
                                <div>
                                    <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1">Latest Reading</p>
                                    <p className="text-2xl font-bold font-mono text-white">{latestTick.value}</p>
                                </div>
                                <i data-lucide="gauge" className="text-slate-700 w-10 h-10"></i>
                            </div>
                            
                            <div className="bg-dark-900 p-6 rounded-xl border border-slate-800 shadow-md flex items-center justify-between">
                                <div>
                                    <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1">Hardware Limits</p>
                                    <p className="text-sm font-bold font-mono text-slate-300">{latestTick.limit}</p>
                                </div>
                                <i data-lucide="sliders" className="text-slate-700 w-10 h-10"></i>
                            </div>
                        </div>

                        {}
                        {/* Live Telemetry Feed */}
                        <div className="bg-dark-900 rounded-xl border border-slate-800 shadow-lg overflow-hidden flex flex-col h-[500px]">
                            <div className="p-5 border-b border-slate-800 flex justify-between items-center bg-dark-950">
                                <h2 className="font-semibold text-lg text-white flex items-center gap-2">
                                    <i data-lucide="radio" className="w-5 h-5 text-brand-500"></i> Live Telemetry Feed
                                </h2>
                                <button onClick={() => setIsStreaming(!isStreaming)} className={`text-xs font-bold px-4 py-1.5 rounded-full border transition-colors ${isStreaming ? 'border-brand-500/50 text-brand-400 bg-brand-500/10 hover:bg-brand-500/20' : 'border-slate-700 text-slate-400 bg-slate-800 hover:bg-slate-700'}`}>
                                    {isStreaming ? 'PAUSE FEED' : 'RESUME FEED'}
                                </button>
                            </div>
                            
                            <div className="overflow-auto custom-scrollbar flex-1">
                                <table className="w-full text-left text-sm text-slate-300">
                                    <thead className="bg-dark-950/80 sticky top-0 backdrop-blur-md z-10 shadow-sm">
                                        <tr>
                                            <th className="p-4 font-semibold text-slate-400 uppercase text-xs tracking-wider">Time</th>
                                            <th className="p-4 font-semibold text-slate-400 uppercase text-xs tracking-wider">Station</th>
                                            <th className="p-4 font-semibold text-slate-400 uppercase text-xs tracking-wider">Value</th>
                                            <th className="p-4 font-semibold text-slate-400 uppercase text-xs tracking-wider">AI Diagnosis</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {stream.length === 0 && (
                                            <tr>
                                                <td colSpan="4" className="p-12 text-center text-slate-500 font-medium">Initializing connection to sensors...</td>
                                            </tr>
                                        )}
                                        {stream.map((row, idx) => (
                                            <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/40 transition-colors">
                                                <td className="p-4 text-slate-500">{row.timestamp}</td>
                                                <td className="p-4 font-medium text-white">{row.station}</td>
                                                <td className="p-4 font-mono text-slate-300">{row.value}</td>
                                                <td className="p-4 font-medium">
                                                    {row.fault_code === 0 ? (
                                                        <span className="flex items-center gap-2 text-emerald-500"><i data-lucide="check-circle" className="w-4 h-4"></i> Normal</span>
                                                    ) : row.fault_code === 1 ? (
                                                        <span className="flex items-center gap-2 text-yellow-500"><i data-lucide="alert-triangle" className="w-4 h-4"></i> {row.diagnosis}</span>
                                                    ) : (
                                                        <span className="flex items-center gap-2 text-red-500"><i data-lucide="shield-alert" className="w-4 h-4"></i> {row.diagnosis}</span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </main>

                    {}
                    {/* Fault Log Modal Window */}
                    {showFaultLog && (
                        <div className="fixed inset-0 bg-dark-950/90 backdrop-blur-sm flex items-center justify-center p-4 z-50">
                            <div className="bg-dark-900 border border-brand-500/30 rounded-xl max-w-4xl w-full flex flex-col h-[600px] shadow-2xl overflow-hidden">
                                <div className="p-5 border-b border-slate-800 flex justify-between items-center bg-dark-950">
                                    <h2 className="font-semibold text-xl text-white flex items-center gap-2">
                                        <i data-lucide="alert-triangle" className="w-6 h-6 text-brand-500"></i> Fault Log
                                    </h2>
                                    <button onClick={() => setShowFaultLog(false)} className="text-slate-400 hover:text-white p-2 bg-slate-800 rounded-lg transition-colors">
                                        <i data-lucide="x" className="w-5 h-5"></i>
                                    </button>
                                </div>
                                
                                <div className="overflow-auto custom-scrollbar flex-1 p-2 bg-dark-900">
                                    {faults.length === 0 ? (
                                        <div className="h-full flex flex-col items-center justify-center text-slate-500">
                                            <i data-lucide="check-circle" className="w-16 h-16 mb-4 text-emerald-500/50"></i>
                                            <p className="text-lg">No critical faults detected in your sector.</p>
                                        </div>
                                    ) : (
                                        <table className="w-full text-left text-sm text-slate-300">
                                            <thead className="bg-slate-800/80 sticky top-0 backdrop-blur-md z-10">
                                                <tr>
                                                    <th className="p-4 font-semibold text-slate-300 uppercase text-xs tracking-wider rounded-tl-lg">Time</th>
                                                    <th className="p-4 font-semibold text-slate-300 uppercase text-xs tracking-wider">Station</th>
                                                    <th className="p-4 font-semibold text-slate-300 uppercase text-xs tracking-wider">Value (Limit)</th>
                                                    <th className="p-4 font-semibold text-slate-300 uppercase text-xs tracking-wider rounded-tr-lg">Diagnosis</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {faults.map((row, idx) => (
                                                    <tr key={idx} className="border-b border-slate-800 hover:bg-slate-800/50">
                                                        <td className="p-4 text-slate-400">{row.timestamp}</td>
                                                        <td className="p-4 font-medium text-white">{row.station}</td>
                                                        <td className="p-4 font-mono text-red-400">{row.value} <span className="text-xs text-slate-500 ml-1">({row.limit})</span></td>
                                                        <td className="p-4 font-medium text-red-400 flex items-center gap-2">
                                                            <i data-lucide={row.fault_code === 1 ? "alert-triangle" : "shield-alert"} className="w-4 h-4"></i> {row.diagnosis}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
        }

        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(<App />);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(debug=True, port=5000)