import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const MERCHANT_ID = 1; // Assuming seeded merchant

function App() {
  const [balance, setBalance] = useState({ available_balance_paise: 0, held_balance_paise: 0 });
  const [payouts, setPayouts] = useState([]);
  const [amount, setAmount] = useState('');
  const [bankId, setBankId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      const balRes = await axios.get(`${API_BASE}/merchants/${MERCHANT_ID}/balance/`);
      setBalance(balRes.data);
      const payRes = await axios.get(`${API_BASE}/payouts/?merchant_id=${MERCHANT_ID}`);
      setPayouts(payRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000); // polling
    return () => clearInterval(interval);
  }, []);

  const handlePayout = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const idempotencyKey = uuidv4();
    try {
      await axios.post(`${API_BASE}/payouts/`, {
        merchant_id: MERCHANT_ID,
        amount_paise: parseInt(amount) * 100, // convert INR to paise
        bank_account_id: bankId
      }, {
        headers: { 'Idempotency-Key': idempotencyKey }
      });
      setAmount('');
      setBankId('');
      fetchData();
    } catch (err) {
      setError(err.response?.data?.error || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const map = {
      'pending': 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
      'processing': 'bg-blue-500/20 text-blue-400 border-blue-500/50 animate-pulse',
      'completed': 'bg-green-500/20 text-green-400 border-green-500/50',
      'failed': 'bg-red-500/20 text-red-400 border-red-500/50',
    };
    return `border px-3 py-1 rounded-full text-xs font-semibold ${map[status] || 'bg-slate-700'}`;
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-200 p-8 font-sans transition-all selection:bg-indigo-500/30">
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Header section with gradient text */}
        <header className="flex justify-between items-center mb-12">
          <h1 className="text-4xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400 drop-shadow-sm">
            Playto Pay
          </h1>
          <div className="flex items-center space-x-3 bg-slate-800/50 px-4 py-2 rounded-full border border-slate-700/50 backdrop-blur-md">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-ping"></span>
            <span className="text-sm font-medium text-slate-300">Live Services</span>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Balance Widget */}
          <div className="card-glass relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-3xl group-hover:bg-indigo-500/20 transition-all duration-500 border border-slate-600/50"></div>
            <h2 className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">Available Balance</h2>
            <div className="text-5xl font-black text-white mb-4">
              ₹ {(balance.available_balance_paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div className="flex items-center justify-between mt-6 text-sm text-slate-400">
              <span>Held in Processing:</span>
              <span className="font-semibold text-slate-300">₹ {(balance.held_balance_paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
            </div>
          </div>

          {/* Request Payout Form */}
          <div className="card-glass relative">
            <h2 className="text-xl font-bold mb-6 text-white">Withdraw Funds</h2>
            {error && <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 text-sm">{error}</div>}
            
            <form onSubmit={handlePayout} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Amount (INR)</label>
                <input 
                  type="number" 
                  required
                  min="1"
                  className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all placeholder-slate-600 shadow-inner"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="e.g. 5000"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Bank Account</label>
                <input 
                  type="text" 
                  required
                  className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all placeholder-slate-600 shadow-inner"
                  value={bankId}
                  onChange={(e) => setBankId(e.target.value)}
                  placeholder="e.g. HDFC-12345"
                />
              </div>
              <button 
                type="submit" 
                disabled={loading || !amount || !bankId}
                className="w-full btn-primary flex justify-center items-center h-12 shadow-md hover:shadow-indigo-500/25 disabled:opacity-50 disabled:cursor-not-allowed group"
              >
                {loading ? (
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                ) : "Request Payout"}
              </button>
            </form>
          </div>
        </div>

        {/* Payout History */}
        <div className="card-glass mt-8 border-t-4 border-t-indigo-500 relative overflow-hidden">
          <h2 className="text-xl font-bold mb-6 text-white flex items-center gap-2">
            Recent Transactions
            <div className="w-8 h-[1px] bg-indigo-500/50"></div>
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-slate-400 text-sm border-b border-slate-700">
                  <th className="pb-4 font-medium uppercase tracking-wider">Time</th>
                  <th className="pb-4 font-medium uppercase tracking-wider">Account</th>
                  <th className="pb-4 font-medium uppercase tracking-wider">Amount (INR)</th>
                  <th className="pb-4 font-medium uppercase tracking-wider text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 text-sm">
                {payouts.map((payout) => (
                  <tr key={payout.id} className="hover:bg-slate-800/30 transition-colors group">
                    <td className="py-4 text-slate-400 font-mono text-xs">
                      {new Date(payout.created_at).toLocaleString()}
                    </td>
                    <td className="py-4 text-slate-200">
                      <div className="flex items-center gap-2">
                        <svg className="w-4 h-4 text-indigo-400 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                        </svg>
                        {payout.bank_account_id}
                      </div>
                    </td>
                    <td className="py-4 font-medium text-white">
                      ₹ {(payout.amount_paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-4 text-right">
                      <span className={getStatusBadge(payout.status)}>
                        {payout.status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
                {payouts.length === 0 && (
                  <tr>
                    <td colSpan="4" className="py-8 text-center text-slate-500 italic">No payouts yet. Withdraw funds to see history.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
