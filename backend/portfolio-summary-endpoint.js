require('dotenv').config();
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const app = express();
const port = 3002;

// Setup CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', 'http://localhost:5173');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  next();
});

// Setup SQLite database
const dbPath = path.join(__dirname, 'robinhood.db');
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err.message);
  } else {
    console.log('Connected to the SQLite database');
  }
});

// Mock portfolio summary metrics function
function calculatePortfolioSummaryMetrics() {
  return new Promise((resolve, reject) => {
    // For testing, return mock data
    const metrics = {
      time_period: {
        start_date: '2023-01-01',
        end_date: '2023-12-31',
        years: 1.0
      },
      start_balance: 10000.00,
      end_balance: 12000.00,
      annualized_return: 20.00,
      annualized_std_dev: 15.00,
      best_year_return: 25.00,
      worst_year_return: -5.00,
      best_year: '2023',
      worst_year: '2022',
      max_drawdown: -8.50,
      max_drawdown_period: {
        start_date: '2023-02-15',
        end_date: '2023-03-10'
      },
      recovery_time: 30,
      sharpe_ratio: 1.23,
      sortino_ratio: 1.45,
      benchmark_correlation: 0.85,
      cumulative_return: 20.00,
      percentage_positive_months: 75.00,
      upside_capture_ratio: 110.00,
      downside_capture_ratio: 80.00
    };
    
    resolve(metrics);
  });
}

// GET route for portfolio summary
app.get('/portfolio-summary', (req, res) => {
  console.log('Portfolio summary endpoint called');
  calculatePortfolioSummaryMetrics()
    .then(metrics => {
      console.log('Sending metrics response');
      res.json(metrics);
    })
    .catch(err => {
      console.error('Error calculating portfolio summary metrics:', err.message);
      res.status(500).json({ error: 'Error calculating portfolio summary metrics' });
    });
});

// Root route
app.get('/', (req, res) => {
  res.send('Robinhood Dashboard Backend - Portfolio Summary Test');
});

// Start server
app.listen(port, () => {
  console.log(`Server running on http://localhost:${port}`);
});

// Handle process termination
process.on('SIGINT', () => {
  db.close((err) => {
    if (err) {
      console.error('Error closing database:', err.message);
    } else {
      console.log('Database connection closed');
    }
    process.exit(0);
  });
}); 
