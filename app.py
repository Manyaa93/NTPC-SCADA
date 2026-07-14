from flask import Flask, request, jsonify, render_template_string
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__)

# ==========================================
# 1. TRAIN THE AI ON STARTUP
# ==========================================
print("Booting Server and Training AI...")
try:
    df = pd.read_csv('synthetic_plant_data.csv')
    X = df[['Fuel_Input_Energy_GJ_per_hr', 'Steam_Temperature_C', 'Steam_Pressure_bar', 'Condenser_Pressure_bar']]
    y = df['Fault_Code']
    model = RandomForestClassifier(random_state=42)
    model.fit(X, y)
    print("✅ AI Model successfully trained and ready!")
except Exception as e:
    print(f"⚠️ Warning: Could not train AI. Is synthetic_plant_data.csv in the folder? Error: {e}")
    model = None


# ==========================================
# 2. THE BACKEND CONTROL CENTER (DATABASE)
# ==========================================
users_db = {
    "admin": {"password": "admin", "role": "Plant Manager (Admin)", "status": "approved"}
}

# ==========================================
# 3. THE API ENDPOINTS
# ==========================================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    if username in users_db:
        return jsonify({"error": "Username already exists!"}), 400
    
    status = 'approved' if data.get('role') == 'Plant Manager (Admin)' else 'pending'
    users_db[username] = {"password": data.get('password'), "role": data.get('role'), "status": status}
    return jsonify({"success": True, "user": {"username": username, "role": data.get('role'), "status": status}})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    user = users_db.get(username)
    if user and user['password'] == data.get('password'):
        return jsonify({"success": True, "user": {"username": username, "role": user['role'], "status": user['status']}})
    return jsonify({"error": "Invalid username or password"}), 401

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

# --- THE NEW AI SCANNING ENDPOINT ---
@app.route('/api/scan', methods=['POST'])
def scan_csv():
    if model is None:
        return jsonify({"error": "AI Model is offline. Training data missing."}), 500
        
    data = request.json
    user_role = data.get('role')
    
    # Read the local CSV directly from the server folder instead of requiring an upload
    try:
        upload_df = pd.read_csv('synthetic_plant_data.csv')
    except Exception as e:
        return jsonify({"error": "Could not locate synthetic_plant_data.csv on server."}), 500
    
    # Predict using the AI
    X_live = upload_df[['Fuel_Input_Energy_GJ_per_hr', 'Steam_Temperature_C', 'Steam_Pressure_bar', 'Condenser_Pressure_bar']]
    upload_df['Fault_Code'] = model.predict(X_live)
    
    # Translate codes to text
    def map_fault(code):
        if code == 1: return "Boiler Tube Leak"
        if code == 2: return "Condenser Fouling"
        return "Normal"
        
    def map_location(code):
        if code == 1: return "Boiler Sub-System"
        if code == 2: return "Cooling Sub-System"
        return "N/A"
        
    upload_df['Diagnosis'] = upload_df['Fault_Code'].apply(map_fault)
    upload_df['Location'] = upload_df['Fault_Code'].apply(map_location)
    
    # ROLE-BASED FILTERING
    if user_role == 'Boiler Operator':
        filtered_df = upload_df[upload_df['Fault_Code'] == 1]
    elif user_role == 'Cooling Engineer':
        filtered_df = upload_df[upload_df['Fault_Code'] == 2]
    else: # Admin sees all faults
        filtered_df = upload_df[upload_df['Fault_Code'] != 0]
        
    # Send results to frontend
    results = []
    for index, row in filtered_df.iterrows():
        results.append({
            "row": index + 1,
            "location": row['Location'],
            "pressure": round(row['Steam_Pressure_bar'], 2),
            "condenser": round(row['Condenser_Pressure_bar'], 3),
            "fuel": round(row['Fuel_Input_Energy_GJ_per_hr'], 2),
            "diagnosis": row['Diagnosis']
        })
        
    return jsonify(results)

# ==========================================
# 4. THE FRONTEND UI (REACT HTML)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thermal Plant MTPC Auth</title>
    <script src="https://unpkg.com/react@18/umd/react.development.js" crossorigin></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js" crossorigin></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #09090b; }
        ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #3f3f46; }
    </style>
</head>
<body class="bg-[#09090b] text-zinc-300 font-sans antialiased min-h-screen selection:bg-indigo-500/30">
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useEffect } = React;

        // --- Clean Minimalist SVGs ---
        const ShieldIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="w-10 h-10 text-indigo-500 mb-6 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12z" /></svg>;
        const LockIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="w-12 h-12 text-amber-500 mb-6 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" /></svg>;
        const ActivityIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M3 13h2.243a2 2 0 011.897 1.368l1.267 3.8a2 2 0 003.786 0l2.52-7.56a2 2 0 013.786 0l1.267 3.8A2 2 0 0021.657 16H23" /></svg>;
        const DatabaseIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8 text-zinc-500 mb-3 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0v3.75C20.25 20.393 16.556 22.25 12 22.25s-8.25-1.847-8.25-4.125v-3.75" /></svg>;
        const AlertIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-rose-500 inline mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>;
        const MapPinIcon = () => <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-zinc-500 inline mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" /></svg>;

        function App() {
            // UI State
            const [user, setUser] = useState(null); 
            const [authMode, setAuthMode] = useState('login'); 
            const [formData, setFormData] = useState({ username: '', password: '', role: 'Boiler Operator' });
            const [errorMsg, setErrorMsg] = useState('');
            const [isLoading, setIsLoading] = useState(false);
            
            // Admin State
            const [usersList, setUsersList] = useState([]);
            
            // Scanner State
            const [csvData, setCsvData] = useState([]);
            const [isScanning, setIsScanning] = useState(false);

            const fetchUsers = async () => {
                try {
                    const res = await fetch('/api/admin/users');
                    const data = await res.json();
                    setUsersList(data);
                } catch (e) { console.error("Could not fetch users", e); }
            };

            // Auto-refresh admin panel
            useEffect(() => {
                if (user && user.role === 'Plant Manager (Admin)') {
                    fetchUsers();
                    const interval = setInterval(fetchUsers, 3000);
                    return () => clearInterval(interval);
                }
            }, [user]);

            const handleApprove = async (username) => {
                await fetch('/api/admin/approve', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username })
                });
                fetchUsers();
            };

            const handleAuth = async (e) => {
                e.preventDefault();
                setErrorMsg('');
                setIsLoading(true);
                
                const endpoint = authMode === 'login' ? '/api/login' : '/api/register';
                
                try {
                    const res = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(formData)
                    });
                    const data = await res.json();
                    
                    if (data.success) {
                        setUser(data.user);
                    } else {
                        setErrorMsg(data.error); 
                    }
                } catch (err) {
                    setErrorMsg("Connection to server failed.");
                }
                setIsLoading(false);
            };

            // --- AI SCANNER FUNCTION ---
            const handleScanDatabase = async () => {
                setIsScanning(true);
                setCsvData([]); // Clear old data

                try {
                    const res = await fetch('/api/scan', { 
                        method: 'POST', 
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ role: user.role }) 
                    });
                    
                    const anomalies = await res.json();
                    if(anomalies.error) {
                        alert(anomalies.error);
                    } else {
                        setCsvData(anomalies);
                    }
                } catch (err) {
                    alert("Error communicating with scanner.");
                }
                setIsScanning(false);
            };

            // ----------------------------------------------------
            // SCREEN 1: APPROVED DASHBOARD (Admin & Operators)
            // ----------------------------------------------------
            if (user && user.status === 'approved') {
                return (
                    <div className="min-h-screen bg-[#09090b]">
                        {/* Clean Navbar */}
                        <nav className="bg-[#09090b] border-b border-zinc-800 px-6 py-4 flex justify-between items-center sticky top-0 z-50">
                            <div className="flex items-center gap-3">
                                <div className="p-1.5 bg-zinc-900 border border-zinc-800 rounded-md">
                                    <ActivityIcon />
                                </div>
                                <span className="text-lg font-semibold text-zinc-100 tracking-tight">MTPC Portal</span>
                            </div>
                            <div className="flex items-center gap-6">
                                <div className="text-right hidden sm:block">
                                    <div className="text-sm font-medium text-zinc-200">{user.username}</div>
                                    <div className="text-xs text-zinc-500">{user.role}</div>
                                </div>
                                <button 
                                    onClick={() => {setUser(null); setCsvData([]);}} 
                                    className="text-zinc-400 hover:text-zinc-100 px-3 py-1.5 rounded-md text-sm font-medium transition-colors border border-transparent hover:border-zinc-800 hover:bg-zinc-900">
                                    Sign Out
                                </button>
                            </div>
                        </nav>

                        <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
                            
                            {/* Header Section */}
                            <div className="flex flex-col md:flex-row justify-between items-start md:items-center pb-4 border-b border-zinc-800/50">
                                <div>
                                    <h1 className="text-2xl font-semibold text-zinc-100 mb-1">System Diagnostics</h1>
                                    <p className="text-sm text-zinc-500">Authorized as <span className="text-zinc-300 font-medium">{user.role}</span></p>
                                </div>
                                {csvData.length > 0 && (
                                    <div className="mt-4 md:mt-0 text-right bg-rose-500/10 border border-rose-500/20 px-4 py-2 rounded-lg">
                                        <div className="text-2xl font-semibold text-rose-500 leading-none">{csvData.length}</div>
                                        <div className="text-[10px] text-rose-400 uppercase tracking-widest font-semibold mt-1">Faults Detected</div>
                                    </div>
                                )}
                            </div>

                            {/* --- ADMIN ONLY PANEL --- */}
                            {user.role === 'Plant Manager (Admin)' && (
                                <div className="bg-[#09090b] rounded-xl border border-zinc-800 overflow-hidden">
                                    <div className="px-6 py-4 border-b border-zinc-800 bg-zinc-900/30 flex justify-between items-center">
                                        <h2 className="text-sm font-medium text-zinc-200">Access Management</h2>
                                    </div>
                                    
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-left text-sm">
                                            <thead className="bg-zinc-900/50 text-xs text-zinc-500 uppercase tracking-wider">
                                                <tr>
                                                    <th className="px-6 py-3 font-medium">User ID</th>
                                                    <th className="px-6 py-3 font-medium">Role</th>
                                                    <th className="px-6 py-3 font-medium">Status</th>
                                                    <th className="px-6 py-3 font-medium text-right">Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-zinc-800">
                                                {usersList.map(u => (
                                                    <tr key={u.username} className="hover:bg-zinc-900/30 transition-colors">
                                                        <td className="px-6 py-4 font-medium text-zinc-300">{u.username}</td>
                                                        <td className="px-6 py-4 text-zinc-400">{u.role}</td>
                                                        <td className="px-6 py-4">
                                                            {u.status === 'pending' ? (
                                                                <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-amber-500/10 text-amber-500 border border-amber-500/20">
                                                                    Pending
                                                                </span>
                                                            ) : (
                                                                <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                                                                    Approved
                                                                </span>
                                                            )}
                                                        </td>
                                                        <td className="px-6 py-4 text-right">
                                                            {u.status === 'pending' ? (
                                                                <button onClick={() => handleApprove(u.username)} className="bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-md text-xs font-medium transition-colors">
                                                                    Approve
                                                                </button>
                                                            ) : (
                                                                <span className="text-zinc-600 text-xs">Granted</span>
                                                            )}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}

                            {/* --- AI DATA SCAN & RESULTS AREA --- */}
                            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                                
                                {/* Scan Action Box */}
                                <div className="lg:col-span-1">
                                    <div className="bg-[#09090b] rounded-xl border border-zinc-800 p-6 h-full flex flex-col items-center justify-center text-center">
                                        <DatabaseIcon />
                                        <h2 className="text-sm font-medium text-zinc-200 mb-2">Plant Database</h2>
                                        <p className="text-xs text-zinc-500 mb-6">Connected to historical telemetry data.</p>
                                        <button 
                                            onClick={handleScanDatabase} 
                                            disabled={isScanning}
                                            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-2.5 rounded-md text-sm font-semibold transition-colors disabled:opacity-50 flex items-center justify-center h-10">
                                            {isScanning ? (
                                                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                            ) : 'Run Diagnostics Scan'}
                                        </button>
                                    </div>
                                </div>

                                {/* Results Table */}
                                <div className="lg:col-span-2">
                                    <div className="bg-[#09090b] rounded-xl border border-zinc-800 flex flex-col h-[400px] overflow-hidden">
                                        <div className="px-6 py-4 border-b border-zinc-800 bg-zinc-900/30 flex justify-between items-center">
                                            <h2 className="text-sm font-medium text-zinc-200">Analysis Results</h2>
                                            <span className="text-xs text-zinc-500 font-medium">Filter: {user.role}</span>
                                        </div>

                                        {isScanning ? (
                                            <div className="flex-1 flex flex-col items-center justify-center">
                                                <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                                                <p className="text-sm text-zinc-400">Processing records...</p>
                                            </div>
                                        ) : csvData.length === 0 ? (
                                            <div className="flex-1 flex flex-col items-center justify-center bg-zinc-900/10">
                                                <p className="text-sm text-zinc-500">Awaiting diagnostic execution.</p>
                                            </div>
                                        ) : (
                                            <div className="flex-1 overflow-auto">
                                                <table className="w-full text-left text-sm whitespace-nowrap">
                                                    <thead className="bg-[#09090b] text-xs uppercase text-zinc-500 sticky top-0 border-b border-zinc-800">
                                                        <tr>
                                                            <th className="px-6 py-3 font-medium">Row</th>
                                                            <th className="px-6 py-3 font-medium">Location</th>
                                                            <th className="px-6 py-3 font-medium">Steam Press.</th>
                                                            <th className="px-6 py-3 font-medium">Fuel Input</th>
                                                            <th className="px-6 py-3 font-medium">Diagnosis</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody className="divide-y divide-zinc-800">
                                                        {csvData.map(row => (
                                                            <tr key={row.row} className="hover:bg-zinc-900/50 transition-colors">
                                                                <td className="px-6 py-3 text-zinc-400">#{row.row}</td>
                                                                <td className="px-6 py-3 font-medium text-zinc-300">
                                                                    <div className="flex items-center">
                                                                        <MapPinIcon />
                                                                        {row.location}
                                                                    </div>
                                                                </td>
                                                                <td className="px-6 py-3 font-mono text-zinc-300">{row.pressure} <span className="text-zinc-600">bar</span></td>
                                                                <td className="px-6 py-3 font-mono text-zinc-300">{row.fuel} <span className="text-zinc-600">GJ</span></td>
                                                                <td className="px-6 py-3 font-medium text-rose-400">
                                                                    <AlertIcon />
                                                                    {row.diagnosis}
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            }

            // ----------------------------------------------------
            // SCREEN 2: PENDING APPROVAL (Workers awaiting admin)
            // ----------------------------------------------------
            if (user && user.status === 'pending') {
                return (
                    <div className="min-h-screen flex flex-col items-center justify-center p-4">
                        <div className="w-full max-w-md bg-[#09090b] border border-zinc-800 rounded-xl p-8 text-center">
                            <LockIcon />
                            <h1 className="text-xl font-semibold text-zinc-100 mb-2">Clearance Required</h1>
                            <p className="text-sm text-zinc-400 mb-6">
                                Account <strong className="text-zinc-300">{user.username}</strong> is pending authorization for sector <strong className="text-zinc-300">{user.role}</strong>.
                            </p>
                            <button onClick={() => setUser(null)} className="text-sm text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
                                &larr; Return to Sign In
                            </button>
                        </div>
                    </div>
                );
            }

            // ----------------------------------------------------
            // SCREEN 3: LOGIN / REGISTER (Not authenticated)
            // ----------------------------------------------------
            return (
                <div className="min-h-screen flex items-center justify-center p-4">
                    <div className="w-full max-w-[400px] bg-[#09090b] border border-zinc-800 rounded-xl p-8 shadow-2xl">
                        <ShieldIcon />
                        <h1 className="text-xl font-semibold text-zinc-100 text-center mb-1">MTPC Gateway</h1>
                        <p className="text-zinc-500 text-sm text-center mb-8">Sign in to access telemetry.</p>
                        
                        {errorMsg && (
                            <div className="bg-rose-500/10 border border-rose-500/20 text-rose-500 px-4 py-3 rounded-md mb-6 text-sm text-center font-medium">
                                {errorMsg}
                            </div>
                        )}
                        
                        <form onSubmit={handleAuth} className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-zinc-400 mb-1.5">USER ID</label>
                                <input type="text" required
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2.5 text-sm text-zinc-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all outline-none"
                                    value={formData.username} onChange={e => setFormData({...formData, username: e.target.value})} />
                            </div>
                            
                            <div>
                                <label className="block text-xs font-medium text-zinc-400 mb-1.5">PASSWORD</label>
                                <input type="password" required
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2.5 text-sm text-zinc-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all outline-none"
                                    value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})} />
                            </div>
                            
                            {authMode === 'register' && (
                                <div>
                                    <label className="block text-xs font-medium text-zinc-400 mb-1.5">SECTOR</label>
                                    <select 
                                        className="w-full bg-zinc-950 border border-zinc-800 rounded-md px-3 py-2.5 text-sm text-zinc-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all outline-none appearance-none"
                                        value={formData.role} onChange={e => setFormData({...formData, role: e.target.value})}>
                                        <option>Boiler Operator</option>
                                        <option>Cooling Engineer</option>
                                        <option>Plant Manager (Admin)</option>
                                    </select>
                                </div>
                            )}
                            
                            <button type="submit" disabled={isLoading}
                                className="w-full bg-zinc-100 hover:bg-white text-zinc-950 py-2.5 rounded-md text-sm font-semibold transition-all mt-6 disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center h-10">
                                {isLoading ? (
                                    <div className="w-4 h-4 border-2 border-zinc-950 border-t-transparent rounded-full animate-spin"></div>
                                ) : (
                                    authMode === 'login' ? 'Sign In' : 'Create Account'
                                )}
                            </button>
                        </form>
                        
                        <div className="mt-6 text-center text-sm">
                            <span className="text-zinc-500">
                                {authMode === 'login' ? "No account? " : "Have an account? "}
                            </span>
                            <button onClick={() => { setAuthMode(authMode === 'login' ? 'register' : 'login'); setErrorMsg(''); }} 
                                className="text-zinc-300 hover:text-white font-medium transition-colors">
                                {authMode === 'login' ? 'Register' : 'Sign In'}
                            </button>
                        </div>
                    </div>
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
def home():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    print("Starting Flask MTPC Server on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)