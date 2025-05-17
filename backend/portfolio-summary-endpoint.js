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

// Remove mock portfolio summary metrics and return a 501 error
module.exports = (req, res) => {
  res.status(501).json({
    error: 'Portfolio summary endpoint is not yet implemented. All data must come from CSV, API, or cache.'
  });
};

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
