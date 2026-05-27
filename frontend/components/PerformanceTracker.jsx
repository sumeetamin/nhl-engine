import React, { useState, useEffect } from 'react';

const PerformanceTracker = () => {
  const [dailyData, setDailyData] = useState(null);
  const [historicalData, setHistoricalData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const timestamp = new Date().getTime();
        
        const [dailyRes, histRes] = await Promise.all([
          fetch(`/daily_predictions.json?t=${timestamp}`),
          fetch(`/historical_stats.json?t=${timestamp}`)
        ]);

        if (!dailyRes.ok || !histRes.ok) {
          throw new Error('Could not find prediction files.');
        }

        const daily = await dailyRes.json();
        const hist = await histRes.json();

        setDailyData(daily);
        setHistoricalData(hist);
        setLoading(false);
      } catch (err) {
        console.error("Error fetching data:", err);
        setError("Waiting for Engine to finish calculations... Data not populated yet");
        setTimeout(fetchData, 5000); 
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64 text-slate-300">
        {error ? <p>{error}</p> : <p>Loading Engine Data...</p>}
      </div>
    );
  }

  return (
    <div className="p-6 bg-slate-900 rounded-lg shadow-xl text-slate-100">
      <h2 className="text-2xl font-bold mb-4 text-emerald-400">Engine V5 Status: Online</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Historical Stats Block */}
        <div className="bg-slate-800 p-4 rounded-md border border-slate-700">
          <h3 className="text-lg font-semibold mb-2 text-blue-300">System Metrics</h3>
          <p>Overall Win Rate: <span className="font-mono text-emerald-400">{historicalData?.overall_win_rate || "N/A"}</span></p>
          <p>Avg Edge: <span className="font-mono text-emerald-400">{historicalData?.avg_edge || "N/A"}</span></p>
        </div>

        {/* Today's Top Play Block */}
        <div className="bg-slate-800 p-4 rounded-md border border-slate-700">
           <h3 className="text-lg font-semibold mb-2 text-blue-300">Today's Top Play</h3>
           {dailyData?.today ? (
             <div>
                <p className="font-bold">{dailyData.today.away?.name} @ {dailyData.today.home?.name}</p>
                <p className="text-sm text-slate-400 mt-2">Engine Pick: <span className="text-emerald-400 font-bold">{dailyData.today.details?.best_angle?.play}</span></p>
                <p className="text-sm text-slate-400">Calculated Edge: {dailyData.today.edge}</p>
             </div>
           ) : (
             <p className="text-slate-400">No qualifying EDGE plays for today.</p>
           )}
        </div>
      </div>
    </div>
  );
};

export default PerformanceTracker;