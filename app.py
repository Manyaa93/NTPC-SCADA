from flask import Flask, request, jsonify, render_template_string
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import random
from datetime import datetime
import time
import re

app = Flask(__name__)

# ==========================================
# 1. AI MODEL INITIALIZATION
# ==========================================
print("Booting Server and Training AI...")
try:
    df = pd.read_csv('synthetic_plant_data.csv')
    X = df[['Fuel_Input_Energy_GJ_per_hr', 'Steam_Temperature_C', 'Steam_Pressure_bar', 'Condenser_Pressure_bar']]
    y = df['Fault_Code']
    model = RandomForestClassifier(random_state=42).fit(X, y)
    print("✅ AI Model successfully trained and active!")
except Exception as e:
    print(f"⚠️ Warning: Could not train AI. {e}")
    model = None

# ==========================================
# 2. USER ACCESS DATABASE
# ==========================================
# We create a "Root Admin" that comes pre-installed in the system.
# Note: The password must meet your new security requirements!
users_db = {
    "admin": {"password": "Admin@123!", "role": "Plant Manager (Admin)", "status": "approved"}
}

# ==========================================
# 3. AUTHENTICATION ENDPOINTS
# ==========================================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password', '')
    
    if username in users_db: return jsonify({"error": "User ID already active"}), 400
    
    # --- SECURITY PROTOCOL: Password Complexity Enforcement ---
    if len(password) < 8:
        return jsonify({"error": "Clearance denied: Password must be at least 8 characters."}), 400
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return jsonify({"error": "Clearance denied: Password requires at least 1 special character."}), 400
    if not re.search(r"\d", password) or not re.search(r"[A-Z]", password):
        return jsonify({"error": "Clearance denied: Password requires a number and an uppercase letter."}), 400
    
    # EVERYONE is 'pending' upon registration. Only an existing Admin can approve them.
    status = 'pending'
    users_db[username] = {"password": password, "role": data.get('role'), "status": status}
    return jsonify({"success": True, "user": {"username": username, "role": data.get('role'), "status": status}})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = users_db.get(data.get('username'))
    if user and user['password'] == data.get('password'):
        return jsonify({"success": True, "user": {"username": data.get('username'), "role": user['role'], "status": user['status']}})
    return jsonify({"error": "Invalid secure credentials"}), 401

@app.route('/api/admin/users', methods=['GET'])
def get_users():
    return jsonify([{"username": k, "role": v['role'], "status": v['status']} for k, v in users_db.items()])

@app.route('/api/admin/approve', methods=['POST'])
def approve_user():
    username = request.json.get('username')
    if username in users_db:
        users_db[username]['status'] = 'approved'
        return jsonify({"success": True})
    return jsonify({"error": "User not found"}), 404

# ==========================================
# 4. REAL-TIME TELEMETRY STREAM
# ==========================================
@app.route('/api/telemetry', methods=['GET'])
def get_telemetry():
    """Returns a single live 'tick' of sensor data and the AI's instant prediction."""
    if model is None: 
        return jsonify({"error": "AI Model offline"}), 500
        
    role = request.args.get('role', 'Admin')
    
    # 1. Simulate current physical sensor readings
    # 85% normal, 7.5% boiler leak, 7.5% condenser fouling
    state = random.choices([0, 1, 2], weights=[0.85, 0.075, 0.075])[0]
    
    f = random.uniform(100, 120)
    t = random.uniform(500, 520)
    p = random.uniform(140, 160)
    c = random.uniform(0.04, 0.08)
    
    if state == 1: # Boiler Leak signature
        f, t, p = random.uniform(140, 180), random.uniform(490, 520), random.uniform(90, 120)
    elif state == 2: # Condenser Fouling signature
        c = random.uniform(0.15, 0.25)

    # 2. Feed live data into AI Model
    df_live = pd.DataFrame([[f, t, p, c]], columns=['Fuel_Input_Energy_GJ_per_hr', 'Steam_Temperature_C', 'Steam_Pressure_bar', 'Condenser_Pressure_bar'])
    prediction = int(model.predict(df_live)[0])
    
    # 3. Format the diagnostic payload
    payload = {
        "id": str(int(time.time() * 1000)), # Unique ID for React rendering
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "fuel": round(f, 2),
        "temp": round(t, 2),
        "pressure": round(p, 2),
        "condenser": round(c, 3),
        "alert_level": "normal",
        "diagnosis": "System Optimal",
        "location": "All Sectors"
    }

    # --- ROLE-BASED ACCESS CONTROL (RBAC) VISIBILITY ---
    if role in ['Plant Manager (Admin)', 'Control Room Engineer']:
        # Command level sees everything across all sectors
        if prediction == 1:
            payload["alert_level"] = "critical"
            payload["diagnosis"] = "Boiler Tube Leak Detected"
            payload["location"] = "Boiler Sub-System"
        elif prediction == 2:
            payload["alert_level"] = "warning"
            payload["diagnosis"] = "Condenser Fouling Detected"
            payload["location"] = "Cooling Sub-System"
            
    elif role == 'Boiler Operator':
        # Boiler Operators ONLY see Boiler faults. Everything else shows as Normal.
        payload["location"] = "Boiler Sub-System"
        if prediction == 1:
            payload["alert_level"] = "critical"
            payload["diagnosis"] = "Boiler Tube Leak Detected"
        else:
            payload["diagnosis"] = "Boiler Operations Normal"
            
    elif role == 'Cooling Engineer':
        # Cooling Engineers ONLY see Condenser faults. Everything else shows as Normal.
        payload["location"] = "Cooling Sub-System"
        if prediction == 2:
            payload["alert_level"] = "warning"
            payload["diagnosis"] = "Condenser Fouling Detected"
        else:
            payload["diagnosis"] = "Cooling Operations Normal"
            
    else:
        # Map the new specialized operators to their respective plant sectors
        sector_mapping = {
            'Turbine Operator': 'Turbine & Generator Sector',
            'Fuel/Coal Handling Plant (CHP) Operator': 'CHP Sector',
            'Ash Handling Operator': 'Ash Plant Sector',
            'Water Treatment/DM Plant Operator': 'DM Plant Sector',
            'Electrical/Switchyard Operator': 'Switchyard Sector'
        }
        
        # Since the current AI model only predicts Boiler/Condenser faults,
        # these future-proofed sectors will default to Normal operations.
        sector_name = sector_mapping.get(role, f"{role} Sector")
        payload["location"] = sector_name
        payload["diagnosis"] = f"{sector_name.replace(' Sector', '')} Operations Normal"

    return jsonify(payload)

# ==========================================
# 5. ENTERPRISE FRONTEND (React)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MTPC Command Center</title>
    <script src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: { 500: '#3b82f6', 600: '#2563eb', 900: '#1e3a8a' },
                        dark: { 800: '#111827', 900: '#0f172a', 950: '#020617' }
                    },
                    fontFamily: { mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'] }
                }
            }
        }
    </script>
    <style>
        body { background-color: #020617; color: #f8fafc; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
        .blink { animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0.3; } }
    </style>
</head>
<body>
    <div id="root"></div>
    <script type="text/babel">
        const { useState, useEffect, useRef } = React;

        // --- ICONS ---
        const IconServer = () => <svg className="w-5 h-5 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" /></svg>;
        const IconActivity = () => <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>;

        function App() {
            // --- STATE ---
            const [user, setUser] = useState(null);
            const [authMode, setAuthMode] = useState('login');
            const [creds, setCreds] = useState({ username: '', password: '', role: 'Boiler Operator' });
            
            // Admin State
            const [usersList, setUsersList] = useState([]);
            
            // Live Data State
            const [stream, setStream] = useState([]); // Array of recent ticks
            const [currentTick, setCurrentTick] = useState(null);

            // --- AUTH LOGIC ---
            const handleAuth = async (e) => {
                e.preventDefault();
                const res = await fetch(authMode === 'login' ? '/api/login' : '/api/register', {
                    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(creds)
                });
                const data = await res.json();
                if(data.success) setUser(data.user);
                else alert(data.error);
            };

            // --- ADMIN POLLING ---
            useEffect(() => {
                if (user?.role === 'Plant Manager (Admin)') {
                    const fetchUsers = async () => {
                        const res = await fetch('/api/admin/users');
                        setUsersList(await res.json());
                    };
                    fetchUsers();
                    const int = setInterval(fetchUsers, 3000);
                    return () => clearInterval(int);
                }
            }, [user]);

            const approveUser = async (username) => {
                await fetch('/api/admin/approve', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username}) });
            };

            // --- REAL-TIME POLLING ENGINE ---
            useEffect(() => {
                let interval;
                if (user && user.status === 'approved') {
                    interval = setInterval(async () => {
                        try {
                            const res = await fetch(`/api/telemetry?role=${user.role}`);
                            const newTick = await res.json();
                            
                            // Update current readings
                            setCurrentTick(newTick);
                            
                            // Prepend to history log (keep last 40)
                            setStream(prev => [newTick, ...prev].slice(0, 40));
                        } catch (err) {
                            console.error("Stream interrupted", err);
                        }
                    }, 1500); // Fetch new data every 1.5 seconds
                }
                return () => clearInterval(interval);
            }, [user]);


            // ==========================================
            // SCREEN 1: LOGIN
            // ==========================================
            if (!user) return (
                <div className="min-h-screen flex items-center justify-center p-4 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] bg-dark-950">
                    <form onSubmit={handleAuth} className="w-full max-w-sm bg-dark-900/80 backdrop-blur-md p-8 rounded-2xl border border-slate-800 shadow-2xl">
                        <div className="flex justify-center mb-6"><IconServer /></div>
                        <h1 className="text-xl font-bold mb-2 text-white text-center tracking-tight">MTPC COMMAND CENTER</h1>
                        <p className="text-slate-400 text-xs text-center mb-8 uppercase tracking-widest">Secure Gateway</p>
                        
                        <div className="space-y-4">
                            <input required className="w-full bg-dark-950 border border-slate-800 p-3 rounded-lg text-sm text-white focus:border-brand-500 focus:outline-none transition-colors" placeholder="Operator ID" onChange={e => setCreds({...creds, username: e.target.value})} />
                            <input required className="w-full bg-dark-950 border border-slate-800 p-3 rounded-lg text-sm text-white focus:border-brand-500 focus:outline-none transition-colors" type="password" placeholder="Access Code" onChange={e => setCreds({...creds, password: e.target.value})} />
                            {authMode === 'register' && 
                                <select className="w-full bg-dark-950 border border-slate-800 p-3 rounded-lg text-sm text-white focus:border-brand-500 focus:outline-none" onChange={e => setCreds({...creds, role: e.target.value})}>
                                    <option>Plant Manager (Admin)</option>
                                    <option>Control Room Engineer</option>
                                    <option>Boiler Operator</option>
                                    <option>Cooling Engineer</option>
                                    <option>Turbine Operator</option>
                                    <option>Fuel/Coal Handling Plant (CHP) Operator</option>
                                    <option>Ash Handling Operator</option>
                                    <option>Water Treatment/DM Plant Operator</option>
                                    <option>Electrical/Switchyard Operator</option>
                                </select>
                            }
                            <button className="w-full bg-brand-600 hover:bg-brand-500 text-white py-3 rounded-lg text-sm font-semibold transition-colors mt-2">
                                {authMode === 'login' ? 'INITIALIZE SESSION' : 'REQUEST CLEARANCE'}
                            </button>
                        </div>
                        <p className="text-center mt-6 text-xs cursor-pointer text-slate-500 hover:text-white transition-colors" onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>
                            {authMode === 'login' ? 'REGISTER NEW PERSONNEL' : 'RETURN TO LOGIN'}
                        </p>
                    </form>
                </div>
            );

            // ==========================================
            // SCREEN 2: PENDING
            // ==========================================
            if (user.status === 'pending') return (
                <div className="min-h-screen flex items-center justify-center bg-dark-950">
                    <div className="text-center border border-amber-500/30 bg-amber-500/10 p-8 rounded-xl">
                        <div className="w-12 h-12 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <h2 className="text-amber-500 font-bold tracking-widest uppercase">Clearance Pending</h2>
                        <p className="text-amber-200/50 text-sm mt-2">Awaiting Plant Manager authorization.</p>
                    </div>
                </div>
            );

            // ==========================================
            // SCREEN 3: LIVE DASHBOARD
            // ==========================================
            return (
                <div className="min-h-screen bg-dark-950 p-4 md:p-8">
                    
                    {/* Top Navigation */}
                    <div className="flex justify-between items-center mb-8 border-b border-slate-800 pb-4">
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
                                MTPC <span className="text-slate-500 font-light">|</span> Command Center
                            </h1>
                            <p className="text-xs text-slate-400 mt-1 uppercase tracking-widest font-mono">Role: {user.role}</p>
                        </div>
                        
                        <div className="flex items-center gap-4">
                            {/* Live Feed Indicator */}
                            <div className="flex items-center gap-2 px-4 py-2 rounded-md font-bold text-[10px] uppercase tracking-widest bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                                <span className="w-2 h-2 rounded-full bg-emerald-500 blink"></span>
                                System Active
                            </div>
                            <button onClick={() => {setUser(null); setStream([]);}} className="text-slate-500 hover:text-white text-sm transition-colors">Logout</button>
                        </div>
                    </div>

                    {/* Admin Panel */}
                    {user.role === 'Plant Manager (Admin)' && (
                        <div className="mb-8 bg-dark-900 border border-brand-500/30 rounded-xl p-4">
                            <h2 className="text-brand-500 text-xs font-bold uppercase tracking-widest mb-3">Personnel Access Management</h2>
                            {usersList.filter(u => u.status === 'pending').length === 0 ? (
                                <p className="text-slate-500 text-sm italic">No pending authorization requests.</p>
                            ) : (
                                <div className="space-y-2">
                                    {usersList.filter(u => u.status === 'pending').map(u => (
                                        <div key={u.username} className="flex justify-between items-center bg-dark-950 p-3 rounded-lg border border-slate-800">
                                            <span className="text-sm">{u.username} <span className="text-slate-500">({u.role})</span></span>
                                            <button onClick={() => approveUser(u.username)} className="bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 px-3 py-1 rounded text-xs font-bold transition-colors">Authorize</button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Live Metrics Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                        <MetricCard title="Steam Temp" value={currentTick ? currentTick.temp : '--'} unit="°C" status={currentTick?.alert_level} />
                        <MetricCard title="Steam Press" value={currentTick ? currentTick.pressure : '--'} unit="bar" status={currentTick?.alert_level} />
                        <MetricCard title="Condenser" value={currentTick ? currentTick.condenser : '--'} unit="bar" status={currentTick?.alert_level} />
                        <MetricCard title="Fuel Input" value={currentTick ? currentTick.fuel : '--'} unit="GJ/hr" status={currentTick?.alert_level} />
                    </div>

                    {/* Rolling Event Log */}
                    <div className="bg-dark-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col h-[500px]">
                        <div className="px-6 py-4 border-b border-slate-800 bg-dark-950/50 flex justify-between items-center">
                            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest">Diagnostic Event Log</h2>
                            <span className="text-xs font-mono text-slate-500">{stream.length} packets buffered</span>
                        </div>
                        
                        <div className="flex-1 overflow-auto bg-dark-900">
                            <table className="w-full text-left text-sm whitespace-nowrap">
                                <thead className="bg-dark-950/80 text-xs uppercase text-slate-500 sticky top-0 backdrop-blur-sm">
                                    <tr>
                                        <th className="px-6 py-3 font-medium">Timestamp</th>
                                        <th className="px-6 py-3 font-medium">Sector</th>
                                        <th className="px-6 py-3 font-medium">AI Diagnosis</th>
                                        <th className="px-6 py-3 font-medium text-right">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800/50">
                                    {stream.length === 0 && (
                                        <tr><td colSpan="4" className="px-6 py-10 text-center text-slate-500 italic">Awaiting data stream...</td></tr>
                                    )}
                                    {stream.map((row) => (
                                        <tr key={row.id} className={`transition-colors font-mono text-xs ${row.alert_level === 'critical' ? 'bg-rose-500/10' : row.alert_level === 'warning' ? 'bg-amber-500/10' : 'hover:bg-dark-800'}`}>
                                            <td className="px-6 py-3 text-slate-400">{row.timestamp}</td>
                                            <td className={`px-6 py-3 ${row.alert_level !== 'normal' ? 'font-bold text-white' : 'text-slate-300'}`}>{row.location}</td>
                                            <td className={`px-6 py-3 ${row.alert_level === 'critical' ? 'text-rose-400 font-bold' : row.alert_level === 'warning' ? 'text-amber-400 font-bold' : 'text-slate-400'}`}>
                                                {row.diagnosis}
                                            </td>
                                            <td className="px-6 py-3 text-right">
                                                <span className={`inline-block px-2 py-1 rounded-sm text-[10px] uppercase tracking-widest font-bold ${
                                                    row.alert_level === 'critical' ? 'bg-rose-500 text-white' : 
                                                    row.alert_level === 'warning' ? 'bg-amber-500 text-white' : 
                                                    'bg-emerald-500/20 text-emerald-400'
                                                }`}>
                                                    {row.alert_level}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            );
        }

        // Helper Component for Metrics
        function MetricCard({ title, value, unit, status }) {
            const isDanger = status === 'critical' || status === 'warning';
            return (
                <div className={`p-4 rounded-xl border transition-colors ${isDanger ? 'bg-rose-500/5 border-rose-500/30' : 'bg-dark-900 border-slate-800'}`}>
                    <h3 className="text-slate-500 text-xs uppercase tracking-widest font-semibold mb-1">{title}</h3>
                    <div className="flex items-baseline gap-1">
                        <span className={`text-2xl font-mono tracking-tight font-bold ${isDanger ? 'text-rose-400' : 'text-white'}`}>{value}</span>
                        <span className="text-slate-500 text-xs font-mono">{unit}</span>
                    </div>
                </div>
            );
        }

        ReactDOM.createRoot(document.getElementById('root')).render(<App />);
    </script>
</body>
</html>
"""

@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(debug=True, port=5000)