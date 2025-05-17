import { useState, useEffect } from 'react';

// Component to display raw database data
function RawDataPage({ onBack }) {
  const [transactions, setTransactions] = useState([]);
  const [stockPrices, setStockPrices] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch data from the backend on component mount
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch('http://localhost:3002/raw-data');
        if (!response.ok) {
          // Try to get text first, in case it's an HTML error page
          const errorText = await response.text();
          try {
            // Try parsing as JSON, which is expected for structured errors
            const errorData = JSON.parse(errorText);
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
          } catch (jsonError) { // eslint-disable-line no-unused-vars
            // If JSON parsing fails, use the raw text (likely HTML)
            // Limit the length to avoid huge error messages
            throw new Error(`HTTP error ${response.status}: ${errorText.substring(0, 500)}...`);
          }
        }
        const data = await response.json();
        setTransactions(data.transactions || []);
        setStockPrices(data.stockPrices || []);
      } catch (fetchError) {
        console.error("Error fetching raw data:", fetchError);
        setError(fetchError.message);
        setTransactions([]);
        setStockPrices([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []); // Empty dependency array means this runs once on mount

  return (
    <div className="w-full max-w-7xl mx-auto p-4 md:p-8 bg-gray-900 rounded-lg shadow-lg border border-neon-cyan glow-border-cyan mt-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl md:text-3xl font-bold text-neon-magenta glow-pink">Raw Database Data</h2>
        <button 
          onClick={onBack} // Call the function passed via props to go back
          className="py-2 px-4 rounded-full font-semibold text-black bg-neon-cyan hover:bg-cyan-300 shadow-md glow-button-cyan transition duration-300 ease-in-out"
        >
          Back to Dashboard
        </button>
      </div>

      {isLoading ? (
        <p className="text-center text-neon-cyan text-lg">Loading raw data...</p>
      ) : error ? (
        <p className="text-center text-red-500 text-lg">Error loading data: {error}</p>
      ) : (
        <div className="space-y-8">
          {/* Transactions Table */}
          <div>
            <h3 className="text-xl font-semibold text-neon-orange mb-4">Transactions (Latest 100)</h3>
            {transactions.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-neon-orange">
                <table className="w-full text-left border-collapse text-sm">
                  <thead className="bg-gray-800">
                    <tr className="border-b border-neon-orange">
                      <th className="p-2 text-neon-orange">ID</th>
                      <th className="p-2 text-neon-orange">Activity Date</th>
                      <th className="p-2 text-neon-orange">Ticker</th>
                      <th className="p-2 text-neon-orange">Trans Code</th>
                      <th className="p-2 text-neon-orange text-right">Quantity</th>
                      <th className="p-2 text-neon-orange text-right">Price</th>
                      <th className="p-2 text-neon-orange text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="bg-gray-900">
                    {transactions.map((tx) => (
                      <tr key={tx.id} className="border-b border-gray-700 hover:bg-gray-800">
                        <td className="p-2 text-gray-400">{tx.id}</td>
                        <td className="p-2">{tx.activity_date ? tx.activity_date.split('T')[0] : 'N/A'}</td>
                        <td className="p-2 text-neon-cyan font-semibold">{tx.ticker || 'N/A'}</td>
                        <td className="p-2">{tx.trans_code}</td>
                        <td className="p-2 text-right">{tx.quantity?.toFixed(4) ?? 'N/A'}</td>
                        <td className="p-2 text-right">{typeof tx.price === 'number' ? `$${tx.price.toFixed(2)}` : 'N/A'}</td>
                        <td className="p-2 text-right">{typeof tx.amount === 'number' ? `$${tx.amount.toFixed(2)}` : 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-center text-gray-500">No transaction data found.</p>
            )}
          </div>

          {/* Stock Prices Table */}
          <div>
            <h3 className="text-xl font-semibold text-neon-yellow mb-4">Stock Prices Cache (Latest 200 Entries)</h3>
            {stockPrices.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-neon-yellow">
                <table className="w-full text-left border-collapse text-sm">
                  <thead className="bg-gray-800">
                    <tr className="border-b border-neon-yellow">
                      <th className="p-2 text-neon-yellow">ID</th>
                      <th className="p-2 text-neon-yellow">Ticker</th>
                      <th className="p-2 text-neon-yellow">Date</th>
                      <th className="p-2 text-neon-yellow text-right">Close Price</th>
                    </tr>
                  </thead>
                  <tbody className="bg-gray-900">
                    {stockPrices.map((price) => (
                      <tr key={price.id} className="border-b border-gray-700 hover:bg-gray-800">
                        <td className="p-2 text-gray-400">{price.id}</td>
                        <td className="p-2 text-neon-cyan font-semibold">{price.ticker}</td>
                        <td className="p-2">{price.date ? price.date.split('T')[0] : 'N/A'}</td>
                        <td className="p-2 text-right">{typeof price.close_price === 'number' ? `$${price.close_price.toFixed(2)}` : 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-center text-gray-500">No stock price data found.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default RawDataPage; 