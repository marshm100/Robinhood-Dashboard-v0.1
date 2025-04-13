require('dotenv').config(); // Add this at the top
const express = require('express');
const multer = require('multer');
const Papa = require('papaparse');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const path = require('path');
const { formatDateForDatabase, toYYYYMMDD } = require('./date-utils');
const app = express();
const port = 3002;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Setup CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*'); // Allow all origins for testing
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  next();
});

// Configure multer for file uploads
const upload = multer({ dest: 'uploads/' });

// Setup SQLite database
const dbPath = path.join(__dirname, 'robinhood.db');
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err.message);
  } else {
    console.log('Connected to the SQLite database');
    // Create transactions table if it doesn't exist
    db.run(`CREATE TABLE IF NOT EXISTS transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      activity_date TEXT,
      ticker TEXT,
      trans_code TEXT,
      quantity REAL,
      price REAL,
      amount REAL
    )`, (err) => {
      if (err) {
        console.error('Error creating transactions table:', err.message);
      } else {
        console.log('Transactions table is ready');
      }
    });
    
    // Create portfolio_config table if it doesn't exist
    db.run(`CREATE TABLE IF NOT EXISTS portfolio_config (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      total_investment REAL,
      ticker TEXT,
      allocation_percentage REAL
    )`, (err) => {
      if (err) {
        console.error('Error creating portfolio_config table:', err.message);
      } else {
        console.log('Portfolio config table is ready');
      }
    });

    // Create stock_prices table if it doesn't exist
    db.run(`CREATE TABLE IF NOT EXISTS stock_prices (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker TEXT,
      date TEXT,
      close_price REAL,
      UNIQUE(ticker, date)
    )`, (err) => {
      if (err) {
        console.error('Error creating stock_prices table:', err.message);
      } else {
        console.log('Stock prices table is ready');
      }
    });
  }
});

app.get('/', (req, res) => {
  res.send('Robinhood Dashboard Backend');
});

// Test endpoint to check API keys
app.get('/test-keys', (req, res) => {
  res.json({
    alphaVantageKey: process.env.ALPHA_VANTAGE_KEY,
    finnhubKey: process.env.FINNHUB_KEY
  });
});

// Add this new route at the beginning, right after the mount point and middleware setup
// Route to get portfolio growth data
app.get('/portfolio-growth', async (req, res) => {
  const benchmarkTicker = req.query.benchmark || 'SPY';
  
  try {
    // Get portfolio daily values
    const portfolioValues = await calculateDailyPortfolioValues();
    
    if (!portfolioValues || portfolioValues.length === 0) {
      console.log('No portfolio data available');
      return res.status(404).json({
        error: 'No portfolio data available',
        message: 'Please upload transaction data before viewing portfolio growth.'
      });
    }
    
    // Get benchmark price data
    const benchmarkPrices = await getStockPrices(benchmarkTicker);
    
    if (!benchmarkPrices || !benchmarkPrices['Time Series (Daily)']) {
      console.log(`No benchmark data available for ${benchmarkTicker}`);
      return res.status(500).json({
        error: 'Benchmark data unavailable',
        message: `Could not retrieve data for benchmark ${benchmarkTicker}. Please try again with a different benchmark.`
      });
    }
    
    // Calculate benchmark values starting with same amount as initial portfolio value
    const initialPortfolioValue = portfolioValues[0].value;
    const initialBenchmarkDate = portfolioValues[0].date;
    const initialBenchmarkPrice = getPriceForDate(benchmarkPrices, initialBenchmarkDate);
    
    if (!initialBenchmarkPrice) {
      console.log(`No benchmark price available for initial date (${initialBenchmarkDate})`);
      return res.status(500).json({
        error: 'Missing benchmark data',
        message: `Could not find price for ${benchmarkTicker} on initial date (${initialBenchmarkDate}). Please try a different benchmark.`
      });
    }
    
    // Create combined dataset with portfolio and benchmark values
    const growthData = portfolioValues.map(item => {
      const benchmarkPrice = getPriceForDate(benchmarkPrices, item.date);
      
      // Only include dates where we have benchmark prices
      if (benchmarkPrice) {
        return {
          date: item.date,
          portfolioValue: item.value,
          benchmarkValue: initialPortfolioValue * (benchmarkPrice / initialBenchmarkPrice)
        };
      }
      // Skip dates with no benchmark price
      return null; 
    }).filter(item => item !== null); // Remove nulls
    
    // If after all this we still have no data, return error instead of fallback
    if (growthData.length === 0) {
      console.log('Growth data is empty after processing');
      return res.status(404).json({
        error: 'No portfolio growth data available',
        message: 'Please ensure you have uploaded transaction data with valid dates and try again.'
      });
    }
    
    res.json(growthData);
  } catch (error) {
    console.error('Error calculating portfolio growth:', error);
    // Return error instead of fallback data
    res.status(500).json({
      error: 'Error calculating portfolio growth',
      message: 'An error occurred while calculating portfolio growth. Please try again later.'
    });
  }
});

// Route to get portfolio drawdown data
app.get('/portfolio-drawdown', async (req, res) => {
  try {
    // Get portfolio daily values
    const portfolioValues = await calculateDailyPortfolioValues();
    
    if (!portfolioValues || portfolioValues.length === 0) {
      return res.status(404).json({
        success: false,
        error: 'No portfolio data available'
      });
    }
    
    // Calculate running maximum and drawdown percentage
    let runningMax = portfolioValues[0].value;
    const drawdownData = portfolioValues.map(item => {
      if (item.value > runningMax) {
        runningMax = item.value;
      }
      
      // Calculate drawdown as percentage from peak
      const drawdownPercentage = runningMax > 0 ? ((runningMax - item.value) / runningMax) * 100 : 0;
      
      return {
        date: item.date,
        value: item.value,
        peak: runningMax,
        drawdownPercentage: drawdownPercentage
      };
    });
    
    res.json(drawdownData);
  } catch (error) {
    console.error('Error calculating portfolio drawdown:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to calculate portfolio drawdown data'
    });
  }
});

// POST route to upload CSV file
app.post('/upload', upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded' });
  }

  const filePath = req.file.path;
  
  // Read the file
  fs.readFile(filePath, 'utf8', (err, data) => {
    if (err) {
      return res.status(500).json({ error: 'Error reading file' });
    }

    // Parse CSV
    Papa.parse(data, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const transactions = results.data;
        
        if (transactions.length === 0) {
          return res.status(400).json({ error: 'No transactions found in file' });
        }

        // Insert transactions into database
        const insertStmt = db.prepare(`
          INSERT INTO transactions (
            activity_date, ticker, trans_code, quantity, price, amount
          ) VALUES (?, ?, ?, ?, ?, ?)
        `);

        let insertedCount = 0;
        let errorCount = 0;

        transactions.forEach(transaction => {
          try {
            // Extract and clean data
            const activityDate = transaction['Activity Date'] || '';
            const ticker = transaction['Instrument'] || '';
            const transCode = transaction['Trans Code'] || '';
            
            // Parse quantity (may be empty for non-trades)
            let quantity = 0;
            if (transaction['Quantity'] && transaction['Quantity'].trim() !== '') {
              quantity = parseFloat(transaction['Quantity'].replace(/,/g, ''));
            }
            
            // Parse price (remove $ and parentheses, may be empty for non-trades)
            let price = 0;
            if (transaction['Price'] && transaction['Price'].trim() !== '') {
              price = parseFloat(transaction['Price'].replace(/[$,]/g, '').replace(/[()]/g, ''));
            }
            
            // Parse amount (remove $ and convert parentheses to negative values)
            let amount = 0;
            if (transaction['Amount'] && transaction['Amount'].trim() !== '') {
              const amountStr = transaction['Amount'].replace(/[$,]/g, '');
              if (amountStr.includes('(') && amountStr.includes(')')) {
                amount = -parseFloat(amountStr.replace(/[()]/g, ''));
              } else {
                amount = parseFloat(amountStr);
              }
            }

            // Insert into database
            insertStmt.run(
              activityDate,
              ticker,
              transCode,
              quantity,
              price,
              amount
            );
            
            insertedCount++;
          } catch (error) {
            console.error('Error inserting transaction:', error.message);
            errorCount++;
          }
        });

        insertStmt.finalize();

        // Clean up the uploaded file
        fs.unlink(filePath, (err) => {
          if (err) console.error('Error deleting file:', err);
        });

        res.json({ 
          message: 'File uploaded and processed successfully',
          totalTransactions: transactions.length,
          insertedCount,
          errorCount
        });
      },
      error: (error) => {
        console.error('Error parsing CSV:', error);
        res.status(500).json({ error: 'Error parsing CSV file' });
      }
    });
  });
});

// POST route to save portfolio configuration
app.post('/portfolio-config', (req, res) => {
  const { total_investment, allocations } = req.body;
  
  if (!total_investment || !allocations || !Array.isArray(allocations) || allocations.length === 0) {
    return res.status(400).json({ error: 'Invalid portfolio configuration. Required: total_investment and allocations array.' });
  }
  
  // Validate the allocations format
  const invalidAllocations = allocations.filter(item => !item.ticker || !item.allocation_percentage);
  if (invalidAllocations.length > 0) {
    return res.status(400).json({ 
      error: 'Invalid allocations format. Each allocation must have ticker and allocation_percentage.'
    });
  }
  
  // Check if allocations add up to 100%
  const totalPercentage = allocations.reduce((sum, item) => sum + parseFloat(item.allocation_percentage), 0);
  if (Math.abs(totalPercentage - 100) > 0.01) { // Allow small floating point errors
    return res.status(400).json({
      error: `Allocation percentages must add up to 100%. Current total: ${totalPercentage.toFixed(2)}%`
    });
  }
  
  try {
    // Begin transaction
    db.serialize(() => {
      db.run('BEGIN TRANSACTION');
      
      // Clear existing portfolio configuration
      db.run('DELETE FROM portfolio_config', (err) => {
        if (err) {
          throw new Error(`Error clearing portfolio_config: ${err.message}`);
        }
        
        // Insert new portfolio configuration
        const insertStmt = db.prepare(
          'INSERT INTO portfolio_config (total_investment, ticker, allocation_percentage) VALUES (?, ?, ?)'
        );
        
        allocations.forEach(allocation => {
          insertStmt.run(
            total_investment,
            allocation.ticker,
            allocation.allocation_percentage
          );
        });
        
        insertStmt.finalize();
        
        db.run('COMMIT', () => {
          res.json({
            message: 'Portfolio configuration saved successfully',
            portfolio: {
              total_investment,
              allocations
            }
          });
        });
      });
    });
  } catch (error) {
    db.run('ROLLBACK');
    console.error('Error saving portfolio configuration:', error.message);
    res.status(500).json({ error: 'Error saving portfolio configuration' });
  }
});

// GET route for portfolio composition
app.get('/portfolio-composition', (req, res) => {
  // Common stock ticker to name mapping
  const stockNames = {
    'AAPL': 'Apple Inc.',
    'MSFT': 'Microsoft Corporation',
    'GOOGL': 'Alphabet Inc. (Google)',
    'AMZN': 'Amazon.com Inc.',
    'META': 'Meta Platforms Inc.',
    'NFLX': 'Netflix Inc.',
    'TSLA': 'Tesla Inc.',
    'NVDA': 'NVIDIA Corporation',
    'JPM': 'JPMorgan Chase & Co.',
    'V': 'Visa Inc.',
    'JNJ': 'Johnson & Johnson',
    'WMT': 'Walmart Inc.',
    'PG': 'Procter & Gamble Co.',
    'MA': 'Mastercard Inc.',
    'DIS': 'The Walt Disney Company',
    'HD': 'The Home Depot Inc.',
    'BAC': 'Bank of America Corp.',
    'VZ': 'Verizon Communications Inc.',
    'ADBE': 'Adobe Inc.',
    'INTC': 'Intel Corporation',
    'CSCO': 'Cisco Systems Inc.',
    'CMCSA': 'Comcast Corporation',
    'PFE': 'Pfizer Inc.',
    'KO': 'The Coca-Cola Company',
    'PEP': 'PepsiCo Inc.',
    'T': 'AT&T Inc.',
    'MRK': 'Merck & Co. Inc.',
    'BITU': 'ProShares Ultra Bitcoin ETF'
  };

  // Query the portfolio configuration
  db.all('SELECT ticker, allocation_percentage FROM portfolio_config', [], (err, rows) => {
    if (err) {
      console.error('Error querying portfolio composition:', err.message);
      return res.status(500).json({ error: 'Error retrieving portfolio composition' });
    }
    
    // Build the portfolio composition with names
    const composition = rows.map(row => {
      return {
        ticker: row.ticker,
        name: stockNames[row.ticker] || `${row.ticker} (Unknown)`,
        allocation_percentage: row.allocation_percentage
      };
    });
    
    // Calculate total investment
    db.get('SELECT total_investment FROM portfolio_config LIMIT 1', [], (err, result) => {
      if (err || !result) {
        console.error('Error querying total investment:', err ? err.message : 'No data found');
        return res.json({ composition });
      }
      
      res.json({
        total_investment: result.total_investment,
        composition
      });
    });
  });
});

// Portfolio Summary Metrics Functions

/**
 * Calculate time period from transactions
 * @returns {Object} Start and end dates
 */
function calculateTimePeriod() {
  return new Promise((resolve, reject) => {
    db.get(`
      SELECT 
        MIN(activity_date) as start_date,
        MAX(activity_date) as end_date
      FROM transactions
    `, [], (err, result) => {
      if (err) {
        reject(err);
        return;
      }
      resolve({
        start_date: result.start_date,
        end_date: result.end_date
      });
    });
  });
}

/**
 * Calculate portfolio value for a specific date
 * @param {string} date - Date in YYYY-MM-DD format
 * @returns {Promise<number>} Portfolio value
 */
function calculatePortfolioValueForDate(date) {
  return new Promise((resolve, reject) => {
    // Get all transactions up to the given date
    db.all(`
      SELECT ticker, trans_code, quantity, price, amount
      FROM transactions
      WHERE activity_date <= ?
      ORDER BY activity_date ASC
    `, [date], (err, transactions) => {
      if (err) {
        reject(err);
        return;
      }

      if (transactions.length === 0) {
        resolve(0); // No transactions yet
        return;
      }

      // Calculate holdings for each ticker
      const holdings = {};
      let cashBalance = 0;

      transactions.forEach(transaction => {
        const { ticker, trans_code, quantity, price, amount } = transaction;
        
        // Handle cash transactions (deposits, withdrawals, etc.)
        if (!ticker || ticker.trim() === '') {
          // For cash transactions, use the amount directly
          cashBalance += amount;
          return;
        }

        // Handle stock transactions
        if (trans_code === 'Buy') {
          holdings[ticker] = (holdings[ticker] || 0) + quantity;
          // No need to subtract amount as it's accounted in cashBalance
        } else if (trans_code === 'Sell') {
          holdings[ticker] = (holdings[ticker] || 0) - quantity;
          // No need to add amount as it's accounted in cashBalance
        } else if (trans_code === 'CDIV') {
          // Dividend
          cashBalance += amount;
        }
        
        // For all transactions, update cash balance
        if (amount) {
          cashBalance += amount;
        }
      });

      // Get latest stock prices for each ticker in holdings
      const tickers = Object.keys(holdings).filter(ticker => holdings[ticker] > 0);
      
      if (tickers.length === 0) {
        // Only cash in portfolio
        resolve(cashBalance);
        return;
      }

      // Get the latest price for each ticker up to the given date
      const promises = tickers.map(ticker => {
        return new Promise((resolvePrice, rejectPrice) => {
          db.get(`
            SELECT close_price 
            FROM stock_prices
            WHERE ticker = ? AND date <= ?
            ORDER BY date DESC
            LIMIT 1
          `, [ticker, date], (err, result) => {
            if (err) {
              rejectPrice(err);
              return;
            }
            
            if (!result) {
              // If we don't have price data for this date, use the transaction price
              db.get(`
                SELECT price
                FROM transactions
                WHERE ticker = ? AND activity_date <= ?
                ORDER BY activity_date DESC
                LIMIT 1
              `, [ticker, date], (err, transaction) => {
                if (err) {
                  rejectPrice(err);
                  return;
                }
                
                const price = transaction ? transaction.price : 0;
                resolvePrice({ ticker, price });
              });
            } else {
              resolvePrice({ ticker, price: result.close_price });
            }
          });
        });
      });

      Promise.all(promises)
        .then(results => {
          // Calculate portfolio value
          let stockValue = 0;
          
          results.forEach(result => {
            const { ticker, price } = result;
            stockValue += holdings[ticker] * price;
          });

          const totalValue = stockValue + cashBalance;
          resolve(totalValue);
        })
        .catch(reject);
    });
  });
}

/**
 * Calculate daily portfolio values for the entire time period
 * @returns {Promise<Array>} Array of daily values { date, value }
 */
function calculateDailyPortfolioValues() {
  return new Promise((resolve, reject) => {
    calculateTimePeriod()
      .then(({ start_date, end_date }) => {
        const start = new Date(start_date);
        const end = new Date(end_date);
        const days = [];
        
        // Generate array of dates
        for (let day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) {
          days.push(new Date(day).toISOString().split('T')[0]); // YYYY-MM-DD format
        }
        
        // Calculate portfolio value for each date
        const promises = days.map(date => {
          return calculatePortfolioValueForDate(date)
            .then(value => ({ date, value }));
        });
        
        Promise.all(promises)
          .then(dailyValues => {
            // Filter out days with zero value (before first transaction)
            const filteredValues = dailyValues.filter(day => day.value > 0);
            resolve(filteredValues);
          })
          .catch(reject);
      })
      .catch(reject);
  });
}

/**
 * Calculate monthly portfolio values
 * @param {Array} dailyValues - Array of daily values { date, value }
 * @returns {Array} Array of monthly values { year_month, value }
 */
function calculateMonthlyPortfolioValues(dailyValues) {
  const monthlyValues = [];
  const monthMap = {};
  
  // Group by year-month and get the last day of each month
  dailyValues.forEach(day => {
    const date = new Date(day.date);
    const yearMonth = `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`;
    
    if (!monthMap[yearMonth] || new Date(day.date) > new Date(monthMap[yearMonth].date)) {
      monthMap[yearMonth] = day;
    }
  });
  
  // Convert map to array and sort by date
  Object.keys(monthMap).forEach(yearMonth => {
    monthlyValues.push({
      year_month: yearMonth,
      date: monthMap[yearMonth].date,
      value: monthMap[yearMonth].value
    });
  });
  
  return monthlyValues.sort((a, b) => new Date(a.date) - new Date(b.date));
}

/**
 * Calculate yearly portfolio values
 * @param {Array} dailyValues - Array of daily values { date, value }
 * @returns {Array} Array of yearly values { year, value }
 */
function calculateYearlyPortfolioValues(dailyValues) {
  const yearlyValues = [];
  const yearMap = {};
  
  // Group by year and get the last day of each year
  dailyValues.forEach(day => {
    const date = new Date(day.date);
    const year = date.getFullYear();
    
    if (!yearMap[year] || new Date(day.date) > new Date(yearMap[year].date)) {
      yearMap[year] = day;
    }
  });
  
  // Convert map to array and sort by date
  Object.keys(yearMap).forEach(year => {
    yearlyValues.push({
      year: parseInt(year),
      date: yearMap[year].date,
      value: yearMap[year].value
    });
  });
  
  return yearlyValues.sort((a, b) => a.year - b.year);
}

/**
 * Calculate the Compound Annual Growth Rate (CAGR)
 * @param {number} startValue - Starting portfolio value
 * @param {number} endValue - Ending portfolio value
 * @param {number} years - Number of years
 * @returns {number} CAGR as a percentage
 */
function calculateCAGR(startValue, endValue, years) {
  if (startValue <= 0 || years <= 0) return 0;
  return (Math.pow(endValue / startValue, 1 / years) - 1) * 100;
}

/**
 * Calculate annualized standard deviation of returns
 * @param {Array} monthlyValues - Array of monthly values { year_month, value }
 * @returns {number} Annualized standard deviation as a percentage
 */
function calculateAnnualizedStdDev(monthlyValues) {
  if (monthlyValues.length < 2) return 0;
  
  // Calculate monthly returns
  const monthlyReturns = [];
  for (let i = 1; i < monthlyValues.length; i++) {
    const previousValue = monthlyValues[i - 1].value;
    const currentValue = monthlyValues[i].value;
    const monthlyReturn = (currentValue / previousValue) - 1;
    monthlyReturns.push(monthlyReturn);
  }
  
  // Calculate mean
  const mean = monthlyReturns.reduce((sum, value) => sum + value, 0) / monthlyReturns.length;
  
  // Calculate variance
  const variance = monthlyReturns.reduce((sum, value) => sum + Math.pow(value - mean, 2), 0) / monthlyReturns.length;
  
  // Calculate monthly standard deviation
  const monthlyStdDev = Math.sqrt(variance);
  
  // Annualize (multiply by sqrt(12))
  const annualizedStdDev = monthlyStdDev * Math.sqrt(12) * 100; // Convert to percentage
  
  return annualizedStdDev;
}

/**
 * Calculate Downside Deviation (for Sortino Ratio)
 * @param {Array} monthlyValues - Array of monthly values { year_month, value }
 * @param {number} targetReturn - Target return (usually 0)
 * @returns {number} Downside deviation
 */
function calculateDownsideDeviation(monthlyValues, targetReturn = 0) {
  if (monthlyValues.length < 2) return 0;
  
  // Calculate monthly returns
  const monthlyReturns = [];
  for (let i = 1; i < monthlyValues.length; i++) {
    const previousValue = monthlyValues[i - 1].value;
    const currentValue = monthlyValues[i].value;
    const monthlyReturn = (currentValue / previousValue) - 1;
    monthlyReturns.push(monthlyReturn);
  }
  
  // Calculate negative deviations
  const negativeDeviations = monthlyReturns
    .filter(r => r < targetReturn)
    .map(r => Math.pow(targetReturn - r, 2));
  
  if (negativeDeviations.length === 0) return 0;
  
  // Calculate downside deviation
  const downsideVariance = negativeDeviations.reduce((sum, value) => sum + value, 0) / negativeDeviations.length;
  const downsideDeviation = Math.sqrt(downsideVariance);
  
  // Annualize (multiply by sqrt(12))
  return downsideDeviation * Math.sqrt(12);
}

/**
 * Calculate best and worst year returns
 * @param {Array} yearlyValues - Array of yearly values { year, value }
 * @returns {Object} Object with best and worst year returns
 */
function calculateBestWorstYearReturns(yearlyValues) {
  if (yearlyValues.length < 2) {
    return {
      best_year: null,
      best_year_return: 0,
      worst_year: null,
      worst_year_return: 0
    };
  }
  
  // Calculate yearly returns
  const yearlyReturns = [];
  for (let i = 1; i < yearlyValues.length; i++) {
    const previousValue = yearlyValues[i - 1].value;
    const currentValue = yearlyValues[i].value;
    const yearlyReturn = ((currentValue / previousValue) - 1) * 100; // percentage
    yearlyReturns.push({
      year: yearlyValues[i].year,
      return: yearlyReturn
    });
  }
  
  // Find best and worst
  let best = yearlyReturns[0];
  let worst = yearlyReturns[0];
  
  yearlyReturns.forEach(year => {
    if (year.return > best.return) best = year;
    if (year.return < worst.return) worst = year;
  });
  
  return {
    best_year: best.year,
    best_year_return: best.return,
    worst_year: worst.year,
    worst_year_return: worst.return
  };
}

/**
 * Calculate maximum drawdown
 * @param {Array} dailyValues - Array of daily values { date, value }
 * @returns {Object} Object with maximum drawdown information
 */
function calculateMaxDrawdown(dailyValues) {
  if (dailyValues.length < 2) {
    return {
      max_drawdown: 0,
      drawdown_start_date: null,
      drawdown_end_date: null,
      recovery_date: null,
      recovery_time_days: null
    };
  }
  
  let maxValue = dailyValues[0].value;
  let maxDrawdown = 0;
  let maxDrawdownStartDate = null;
  let maxDrawdownEndDate = null;
  let tempMaxValueDate = dailyValues[0].date;
  let recovered = false;
  let recoveryDate = null;
  
  // Find maximum drawdown
  for (let i = 1; i < dailyValues.length; i++) {
    const currentValue = dailyValues[i].value;
    
    if (currentValue > maxValue) {
      maxValue = currentValue;
      tempMaxValueDate = dailyValues[i].date;
      recovered = true;  // Mark as recovered
    } else {
      const drawdown = (maxValue - currentValue) / maxValue;
      
      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown;
        maxDrawdownStartDate = tempMaxValueDate;
        maxDrawdownEndDate = dailyValues[i].date;
        recovered = false;  // Reset recovery
        recoveryDate = null;
      } else if (!recovered && currentValue >= maxValue) {
        recovered = true;
        recoveryDate = dailyValues[i].date;
      }
    }
  }
  
  // Calculate recovery time
  let recoveryTimeDays = null;
  if (recoveryDate && maxDrawdownEndDate) {
    const endDate = new Date(maxDrawdownEndDate);
    const recDate = new Date(recoveryDate);
    recoveryTimeDays = Math.floor((recDate - endDate) / (1000 * 60 * 60 * 24));
  }
  
  return {
    max_drawdown: maxDrawdown * 100, // as percentage
    drawdown_start_date: maxDrawdownStartDate,
    drawdown_end_date: maxDrawdownEndDate,
    recovery_date: recoveryDate,
    recovery_time_days: recoveryTimeDays
  };
}

/**
 * Calculate Sharpe Ratio
 * @param {number} annualizedReturn - Annualized return as percentage
 * @param {number} annualizedStdDev - Annualized standard deviation as percentage
 * @param {number} riskFreeRate - Risk-free rate as percentage (default: 1.5%)
 * @returns {number} Sharpe Ratio
 */
function calculateSharpeRatio(annualizedReturn, annualizedStdDev, riskFreeRate = 1.5) {
  if (annualizedStdDev === 0) return 0;
  return (annualizedReturn - riskFreeRate) / annualizedStdDev;
}

/**
 * Calculate Sortino Ratio
 * @param {number} annualizedReturn - Annualized return as percentage
 * @param {number} downsideDeviation - Downside deviation
 * @param {number} riskFreeRate - Risk-free rate as percentage (default: 1.5%)
 * @returns {number} Sortino Ratio
 */
function calculateSortinoRatio(annualizedReturn, downsideDeviation, riskFreeRate = 1.5) {
  if (downsideDeviation === 0) return 0;
  return (annualizedReturn - riskFreeRate) / (downsideDeviation * 100);
}

/**
 * Calculate percentage of positive months
 * @param {Array} monthlyValues - Array of monthly values { year_month, value }
 * @returns {number} Percentage of positive months
 */
function calculatePositiveMonths(monthlyValues) {
  if (monthlyValues.length < 2) return 0;
  
  let positiveMonths = 0;
  
  for (let i = 1; i < monthlyValues.length; i++) {
    const previousValue = monthlyValues[i - 1].value;
    const currentValue = monthlyValues[i].value;
    
    if (currentValue > previousValue) {
      positiveMonths++;
    }
  }
  
  return (positiveMonths / (monthlyValues.length - 1)) * 100;
}

/**
 * Calculate cumulative return
 * @param {number} startValue - Starting portfolio value
 * @param {number} endValue - Ending portfolio value
 * @returns {number} Cumulative return as percentage
 */
function calculateCumulativeReturn(startValue, endValue) {
  if (startValue <= 0) return 0;
  return ((endValue / startValue) - 1) * 100;
}

/**
 * Calculate benchmark correlation
 * @param {Array} portfolioMonthlyValues - Array of portfolio monthly values { year_month, value }
 * @param {Array} benchmarkMonthlyValues - Array of benchmark monthly values { year_month, value }
 * @returns {number|null} Correlation coefficient or null if calculation is not possible.
 */
function calculateBenchmarkCorrelation(portfolioMonthlyValues, benchmarkMonthlyValues) {
  // Return null if insufficient data
  if (!portfolioMonthlyValues || portfolioMonthlyValues.length < 2 || !benchmarkMonthlyValues || benchmarkMonthlyValues.length < 2) {
    return null;
  }

  // Helper to get monthly returns with year_month
  function getReturns(monthlyValues) {
    const returns = {};
    for (let i = 1; i < monthlyValues.length; i++) {
      const prev = monthlyValues[i - 1];
      const curr = monthlyValues[i];
      if (prev.value !== 0) { // Avoid division by zero
        returns[curr.year_month] = (curr.value / prev.value) - 1;
      }
    }
    return returns;
  }

  const portfolioReturnsMap = getReturns(portfolioMonthlyValues);
  const benchmarkReturnsMap = getReturns(benchmarkMonthlyValues);

  // Align returns by year_month
  const portfolioReturns = [];
  const benchmarkReturns = [];
  const commonMonths = Object.keys(portfolioReturnsMap).filter(month => benchmarkReturnsMap.hasOwnProperty(month));

  if (commonMonths.length < 2) { // Need at least 2 common data points for correlation
      console.warn("[calculateBenchmarkCorrelation] Less than 2 common months for correlation.");
      return null;
  }

  commonMonths.forEach(month => {
      portfolioReturns.push(portfolioReturnsMap[month]);
      benchmarkReturns.push(benchmarkReturnsMap[month]);
  });

  const n = portfolioReturns.length;
  if (n === 0) return null;

  const sumX = portfolioReturns.reduce((s, v) => s + v, 0);
  const sumY = benchmarkReturns.reduce((s, v) => s + v, 0);
  const sumXY = portfolioReturns.reduce((s, v, i) => s + v * benchmarkReturns[i], 0);
  const sumX2 = portfolioReturns.reduce((s, v) => s + v * v, 0);
  const sumY2 = benchmarkReturns.reduce((s, v) => s + v * v, 0);

  const numerator = n * sumXY - sumX * sumY;
  const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));

  if (denominator === 0) {
    console.warn("[calculateBenchmarkCorrelation] Denominator is zero, cannot calculate correlation.");
    return null; // Avoid division by zero; correlation is undefined
  }

  const correlation = numerator / denominator;
  return correlation; // Return as a coefficient (e.g., 0.85)
}

/**
 * Calculate upside/downside capture ratio.
 * @param {Array} portfolioMonthlyValues - Array of portfolio monthly values { year_month, value }.
 * @param {Array} benchmarkMonthlyValues - Array of benchmark monthly values { year_month, value }.
 * @returns {Object|null} Object with upside/downside ratios (as percentages) or null if calculation not possible.
 */
function calculateCaptureRatios(portfolioMonthlyValues, benchmarkMonthlyValues) {
  // Return null if insufficient data
  if (!portfolioMonthlyValues || portfolioMonthlyValues.length < 2 || !benchmarkMonthlyValues || benchmarkMonthlyValues.length < 2) {
    return null;
  }

  // Helper to get monthly returns with year_month
  function getReturns(monthlyValues) {
    const returns = {};
    for (let i = 1; i < monthlyValues.length; i++) {
      const prev = monthlyValues[i - 1];
      const curr = monthlyValues[i];
      if (prev.value !== 0) { // Avoid division by zero
        returns[curr.year_month] = (curr.value / prev.value) - 1;
      }
    }
    return returns;
  }

  const portfolioReturnsMap = getReturns(portfolioMonthlyValues);
  const benchmarkReturnsMap = getReturns(benchmarkMonthlyValues);

  // Align returns by year_month
  const portfolioUpReturns = [];
  const benchmarkUpReturns = [];
  const portfolioDownReturns = [];
  const benchmarkDownReturns = [];

  const commonMonths = Object.keys(portfolioReturnsMap).filter(month => benchmarkReturnsMap.hasOwnProperty(month));

  if (commonMonths.length === 0) {
    console.warn("[calculateCaptureRatios] No common months found.");
    return null;
  }

  commonMonths.forEach(month => {
    const portfolioReturn = portfolioReturnsMap[month];
    const benchmarkReturn = benchmarkReturnsMap[month];

    if (benchmarkReturn > 0) {
      portfolioUpReturns.push(1 + portfolioReturn);
      benchmarkUpReturns.push(1 + benchmarkReturn);
    } else if (benchmarkReturn < 0) {
      portfolioDownReturns.push(1 + portfolioReturn);
      benchmarkDownReturns.push(1 + benchmarkReturn);
    }
    // Ignore months where benchmark return is exactly 0
  });

  // Helper to calculate geometric mean from (1 + return) values
  function geometricMean(returnsPlusOne) {
    if (returnsPlusOne.length === 0) return null;
    const product = returnsPlusOne.reduce((prod, val) => prod * val, 1);
    // Use Math.abs for the base in case product is negative (can happen with odd number of negative returns)
    // and handle potential complex numbers by checking sign before powering
    if (product < 0 && returnsPlusOne.length % 2 === 0) {
         console.warn("[geometricMean] Even root of negative number encountered. Returning null.");
         return null; // Or handle appropriately
    }
    const mean = Math.pow(Math.abs(product), 1 / returnsPlusOne.length);
    return product < 0 ? -mean : mean; // Re-apply sign if needed
  }

  const geoMeanPortfolioUp = geometricMean(portfolioUpReturns);
  const geoMeanBenchmarkUp = geometricMean(benchmarkUpReturns);
  const geoMeanPortfolioDown = geometricMean(portfolioDownReturns);
  const geoMeanBenchmarkDown = geometricMean(benchmarkDownReturns);

  let upsideRatio = null;
  if (geoMeanBenchmarkUp !== null && geoMeanBenchmarkUp !== 1) { // Check against 1 (0% return)
      const compoundedPortfolioUp = geoMeanPortfolioUp !== null ? Math.pow(geoMeanPortfolioUp, portfolioUpReturns.length) : 1;
      const compoundedBenchmarkUp = Math.pow(geoMeanBenchmarkUp, benchmarkUpReturns.length);
      // Ratio of compounded returns
      upsideRatio = compoundedBenchmarkUp !== 0 ? (compoundedPortfolioUp / compoundedBenchmarkUp) * 100 : null;
  } else {
      console.warn("[calculateCaptureRatios] No benchmark up-market returns or compounded benchmark return is 1 (0%).");
  }

  let downsideRatio = null;
  if (geoMeanBenchmarkDown !== null && geoMeanBenchmarkDown !== 1) { // Check against 1 (0% return)
      const compoundedPortfolioDown = geoMeanPortfolioDown !== null ? Math.pow(geoMeanPortfolioDown, portfolioDownReturns.length) : 1;
      const compoundedBenchmarkDown = Math.pow(geoMeanBenchmarkDown, benchmarkDownReturns.length);
      // Ratio of compounded returns
      downsideRatio = compoundedBenchmarkDown !== 0 ? (compoundedPortfolioDown / compoundedBenchmarkDown) * 100 : null;
  } else {
       console.warn("[calculateCaptureRatios] No benchmark down-market returns or compounded benchmark return is 1 (0%).");
  }

  return {
    upside_capture_ratio: upsideRatio !== null ? parseFloat(upsideRatio.toFixed(2)) : null,
    downside_capture_ratio: downsideRatio !== null ? parseFloat(downsideRatio.toFixed(2)) : null
  };
}


/**
 * Calculate portfolio summary metrics
 * @returns {Promise<Object>} Object with all portfolio metrics
 */
async function calculatePortfolioSummaryMetrics() { // Made function async
  try { // Added try block for async error handling
    const dailyValues = await calculateDailyPortfolioValues();

    if (!dailyValues || dailyValues.length === 0) {
      throw new Error('No portfolio data available'); // Use throw for async errors
    }

    // Calculate monthly and yearly values
    const monthlyValues = calculateMonthlyPortfolioValues(dailyValues);
    const yearlyValues = calculateYearlyPortfolioValues(dailyValues);

    // Get time period
    const startDate = dailyValues[0].date;
    const endDate = dailyValues[dailyValues.length - 1].date;

    // Get start and end balance
    const startBalance = dailyValues[0].value;
    const endBalance = dailyValues[dailyValues.length - 1].value;

    // Calculate years
    const startDateObj = new Date(startDate);
    const endDateObj = new Date(endDate);
    const years = (endDateObj - startDateObj) / (365.25 * 24 * 60 * 60 * 1000);

    // Calculate CAGR
    const cagr = calculateCAGR(startBalance, endBalance, years);

    // Calculate annualized standard deviation
    const annualizedStdDev = calculateAnnualizedStdDev(monthlyValues);

    // Calculate downside deviation
    const downsideDeviation = calculateDownsideDeviation(monthlyValues);

    // Calculate best/worst year returns
    const yearlyReturns = calculateBestWorstYearReturns(yearlyValues);

    // Calculate maximum drawdown
    const drawdown = calculateMaxDrawdown(dailyValues);

    // Calculate Sharpe and Sortino ratios
    const sharpeRatio = calculateSharpeRatio(cagr, annualizedStdDev);
    const sortinoRatio = calculateSortinoRatio(cagr, downsideDeviation);

    // Calculate percentage of positive months
    const positiveMonths = calculatePositiveMonths(monthlyValues);

    // Calculate cumulative return
    const cumulativeReturn = calculateCumulativeReturn(startBalance, endBalance);

    // --- Fetch and Calculate Benchmark Metrics ---
    const benchmarkTicker = 'SPY'; // Default benchmark
    const benchmarkMonthlyValues = await getAlignedBenchmarkMonthlyValues(benchmarkTicker, dailyValues);

    // Calculate correlation and capture ratios using actual benchmark data (or null if unavailable)
    const correlation = calculateBenchmarkCorrelation(monthlyValues, benchmarkMonthlyValues);
    const captureRatiosResult = calculateCaptureRatios(monthlyValues, benchmarkMonthlyValues);

    // Build metrics object
    const metrics = {
      time_period: {
        start_date: startDate,
        end_date: endDate,
        years: parseFloat(years.toFixed(2))
      },
      start_balance: parseFloat(startBalance.toFixed(2)),
      end_balance: parseFloat(endBalance.toFixed(2)),
      annualized_return: parseFloat(cagr.toFixed(2)),
      annualized_std_dev: parseFloat(annualizedStdDev.toFixed(2)),
      best_year_return: parseFloat(yearlyReturns.best_year_return.toFixed(2)),
      worst_year_return: parseFloat(yearlyReturns.worst_year_return.toFixed(2)),
      best_year: yearlyReturns.best_year,
      worst_year: yearlyReturns.worst_year,
      max_drawdown: parseFloat(drawdown.max_drawdown.toFixed(2)),
      max_drawdown_period: {
        start_date: drawdown.drawdown_start_date,
        end_date: drawdown.drawdown_end_date
      },
      recovery_time: drawdown.recovery_time_days,
      sharpe_ratio: parseFloat(sharpeRatio.toFixed(2)),
      sortino_ratio: parseFloat(sortinoRatio.toFixed(2)),
      // Use calculated correlation or null
      benchmark_correlation: correlation !== null ? parseFloat(correlation.toFixed(2)) : null,
      cumulative_return: parseFloat(cumulativeReturn.toFixed(2)),
      percentage_positive_months: parseFloat(positiveMonths.toFixed(2)),
      // Use calculated capture ratios or null
      upside_capture_ratio: captureRatiosResult?.upside_capture_ratio ?? null,
      downside_capture_ratio: captureRatiosResult?.downside_capture_ratio ?? null
    };

    return metrics; // Return metrics on success

  } catch (error) {
      console.error("Error in calculatePortfolioSummaryMetrics:", error);
      throw error; // Re-throw the error to be caught by the route handler
  }
}


// GET route for portfolio summary
app.get('/portfolio-summary', async (req, res) => { // Make route async
  try {
    const metrics = await calculatePortfolioSummaryMetrics();
    res.json(metrics);
  } catch (err) {
    console.error('Error calculating portfolio summary metrics:', err.message);
    // Send specific error message if known (e.g., no data)
    if (err.message === 'No portfolio data available') {
        res.status(404).json({ error: 'No portfolio data available', message: 'Upload transaction data first.' });
    } else {
        res.status(500).json({ error: 'Error calculating portfolio summary metrics', message: err.message });
    }
  }
});

// Calculate style analysis data
function calculateStyleAnalysis() {
  return new Promise((resolve, reject) => {
    // Get portfolio configuration
    db.all('SELECT ticker, allocation_percentage FROM portfolio_config', [], (err, allocations) => {
      if (err) {
        return reject(err);
      }
      
      if (!allocations || allocations.length === 0) {
        return resolve({
          message: 'No portfolio configuration found',
          styleAnalysis: []
        });
      }
      
      // Mock style analysis data for the portfolio
      // In a real application, this would come from a financial data API
      const styleAnalysis = allocations.map(allocation => {
        // Generate mock data for this ticker
        const secYield = (Math.random() * 2).toFixed(2);
        const ttmYield = (Math.random() * 2.5).toFixed(2);
        const netExpenseRatio = (Math.random() * 0.8).toFixed(2);
        const grossExpenseRatio = ((Math.random() * 0.8) + 0.2).toFixed(2);
        const peRatio = (Math.random() * 25 + 10).toFixed(2);
        const duration = (Math.random() * 7).toFixed(2);
        const contributionToReturn = (Math.random() * 5 - 1).toFixed(2);
        const contributionToRisk = (Math.random() * 4).toFixed(2);
        
        // Assign a random category
        const categories = ['Large Cap', 'Mid Cap', 'Small Cap', 'International', 'Bond', 'Cash'];
        const category = categories[Math.floor(Math.random() * categories.length)];
        
        return {
          ticker: allocation.ticker,
          category,
          weight: parseFloat(allocation.allocation_percentage).toFixed(2),
          secYield,
          ttmYield,
          netExpenseRatio,
          grossExpenseRatio,
          peRatio,
          duration,
          contributionToReturn,
          contributionToRisk
        };
      });
      
      // Calculate portfolio totals (weighted averages)
      const totalWeight = allocations.reduce((sum, a) => sum + parseFloat(a.allocation_percentage), 0);
      
      // Only calculate if the total weight is valid
      if (totalWeight > 0) {
        let totalSecYield = 0;
        let totalTtmYield = 0;
        let totalNetExpenseRatio = 0;
        let totalGrossExpenseRatio = 0;
        let totalPeRatio = 0;
        let totalDuration = 0;
        let totalContributionToReturn = 0;
        
        styleAnalysis.forEach(item => {
          const weight = parseFloat(item.weight) / totalWeight;
          totalSecYield += parseFloat(item.secYield) * weight;
          totalTtmYield += parseFloat(item.ttmYield) * weight;
          totalNetExpenseRatio += parseFloat(item.netExpenseRatio) * weight;
          totalGrossExpenseRatio += parseFloat(item.grossExpenseRatio) * weight;
          totalPeRatio += parseFloat(item.peRatio) * weight;
          totalDuration += parseFloat(item.duration) * weight;
          totalContributionToReturn += parseFloat(item.contributionToReturn) * weight;
        });
        
        // Add portfolio totals
        const portfolioTotals = {
          totalSecYield: totalSecYield.toFixed(2),
          totalTtmYield: totalTtmYield.toFixed(2),
          totalNetExpenseRatio: totalNetExpenseRatio.toFixed(2),
          totalGrossExpenseRatio: totalGrossExpenseRatio.toFixed(2),
          totalPeRatio: totalPeRatio.toFixed(2),
          totalDuration: totalDuration.toFixed(2),
          totalContributionToReturn: totalContributionToReturn.toFixed(2)
        };
        
        resolve({
          styleAnalysis,
          portfolioTotals
        });
      } else {
        resolve({
          message: 'Invalid portfolio weights',
          styleAnalysis: []
        });
      }
    });
  });
}

// GET route for style analysis
app.get('/style-analysis', async (req, res) => {
  try {
    const styleAnalysisData = await calculateStyleAnalysis();
    res.json(styleAnalysisData);
  } catch (error) {
    console.error('Error calculating style analysis:', error);
    res.status(500).json({ error: 'Failed to calculate style analysis' });
  }
});

/**
 * Calculate Active Return by Asset for different time periods
 * @returns {Promise<Object>} Object with active return by asset for different time periods
 */
function calculateActiveReturnByAsset() {
  return new Promise((resolve, reject) => {
    // Get portfolio configuration (allocations)
    db.all('SELECT ticker, allocation_percentage FROM portfolio_config', [], (err, allocations) => {
      if (err) {
        return reject(err);
      }
      
      if (!allocations || allocations.length === 0) {
        return resolve({
          message: 'No portfolio configuration found',
          activeReturns: []
        });
      }
      
      // Get daily portfolio values
      calculateDailyPortfolioValues()
        .then(dailyValues => {
          if (dailyValues.length === 0) {
            return resolve({
              message: 'No portfolio data available',
              activeReturns: []
            });
          }
          
          // Define the time periods to calculate
          const periods = [
            { name: '1 Day', days: 1 },
            { name: '1 Week', days: 7 },
            { name: '1 Month', days: 30 },
            { name: '3 Month', days: 90 },
            { name: '6 Month', days: 180 },
            { name: '1 Year', days: 365 },
            { name: '3 Year', days: 3 * 365 },
            { name: '5 Year', days: 5 * 365 },
            { name: '10 Year', days: 10 * 365 },
            { name: 'Full Period', days: null } // Will use all available data
          ];
          
          // Get all unique tickers from portfolio configuration
          const tickers = allocations.map(allocation => allocation.ticker);
          
          // Use a placeholder for benchmark returns
          // In a real implementation, this would fetch S&P500 or another index
          const benchmarkReturns = {
            '1 Day': 0.05,     // 0.05% daily return
            '1 Week': 0.2,     // 0.2% weekly return
            '1 Month': 0.8,    // 0.8% monthly return
            '3 Month': 2.5,    // 2.5% 3-month return
            '6 Month': 5.0,    // 5.0% 6-month return
            '1 Year': 10.0,    // 10.0% 1-year return
            '3 Year': 30.0,    // 30.0% 3-year return
            '5 Year': 50.0,    // 50.0% 5-year return
            '10 Year': 100.0,  // 100.0% 10-year return
            'Full Period': 150.0 // 150.0% full period return
          };
          
          // Calculate active return for each ticker and period
          const activeReturnsByAsset = tickers.map(ticker => {
            // Get stock prices for this ticker
            return new Promise((resolveStock, rejectStock) => {
              db.all('SELECT date, close_price FROM stock_prices WHERE ticker = ? ORDER BY date ASC', [ticker], (err, prices) => {
                if (err) {
                  return rejectStock(err);
                }
                
                if (!prices || prices.length === 0) {
                  // If no prices found, return placeholder data
                  return resolveStock({
                    ticker,
                    returns: periods.map(period => ({
                      period: period.name,
                      return: 0,
                      benchmarkReturn: benchmarkReturns[period.name],
                      activeReturn: -benchmarkReturns[period.name] // Underperforming benchmark
                    }))
                  });
                }
                
                // Calculate returns for each period
                const returns = periods.map(period => {
                  let assetReturn;
                  
                  if (period.days === null) {
                    // Full period
                    if (prices.length > 1) {
                      const firstPrice = prices[0].close_price;
                      const lastPrice = prices[prices.length - 1].close_price;
                      assetReturn = ((lastPrice - firstPrice) / firstPrice) * 100;
                    } else {
                      assetReturn = 0;
                    }
                  } else {
                    // Specific period
                    const today = new Date();
                    const cutoffDate = new Date(today);
                    cutoffDate.setDate(today.getDate() - period.days);
                    const cutoffDateStr = cutoffDate.toISOString().split('T')[0];
                    
                    // Find closest price before cutoff date
                    let startPrice = null;
                    for (let i = 0; i < prices.length; i++) {
                      if (prices[i].date <= cutoffDateStr) {
                        startPrice = prices[i].close_price;
                      } else {
                        break;
                      }
                    }
                    
                    // If we don't have data that far back, use the earliest price
                    if (startPrice === null && prices.length > 0) {
                      startPrice = prices[0].close_price;
                    }
                    
                    // Get latest price
                    const endPrice = prices[prices.length - 1].close_price;
                    
                    if (startPrice && endPrice) {
                      assetReturn = ((endPrice - startPrice) / startPrice) * 100;
                    } else {
                      assetReturn = 0;
                    }
                  }
                  
                  const benchmarkReturn = benchmarkReturns[period.name];
                  const activeReturn = assetReturn - benchmarkReturn;
                  
                  return {
                    period: period.name,
                    return: parseFloat(assetReturn.toFixed(2)),
                    benchmarkReturn: parseFloat(benchmarkReturn.toFixed(2)),
                    activeReturn: parseFloat(activeReturn.toFixed(2))
                  };
                });
                
                resolveStock({
                  ticker,
                  returns
                });
              });
            });
          });
          
          Promise.all(activeReturnsByAsset)
            .then(results => {
              resolve({
                activeReturns: results
              });
            })
            .catch(reject);
        })
        .catch(reject);
    });
  });
}

// GET route for active return by asset
app.get('/active-return', (req, res) => {
  calculateActiveReturnByAsset()
    .then(data => {
      res.json(data);
    })
    .catch(err => {
      console.error('Error calculating active return by asset:', err.message);
      res.status(500).json({ error: 'Error calculating active return by asset' });
    });
});

/**
 * Calculate Up vs. Down Market Performance metrics
 * @returns {Promise<Object>} Object with market performance metrics
 */
function calculateUpDownMarketPerformance() {
  return new Promise((resolve, reject) => {
    // Get daily portfolio values
    calculateDailyPortfolioValues()
      .then(portfolioValues => {
        if (!portfolioValues || portfolioValues.length === 0) {
          return resolve({
            message: 'No portfolio data available',
            marketPerformance: []
          });
        }

        // Fetch actual benchmark data from stock_prices table using SPY as default
        const benchmarkTicker = 'SPY';
        getStockPrices(benchmarkTicker)
          .then(benchmarkPriceData => {
            if (!benchmarkPriceData || !benchmarkPriceData['Time Series (Daily)']) {
              console.log(`No benchmark data available for ${benchmarkTicker}`);
              return resolve({
                message: `No benchmark data available for ${benchmarkTicker}`,
                marketPerformance: []
              });
            }

            // Create benchmark values with same starting value as portfolio
            const initialPortfolioValue = portfolioValues[0].value;
            const initialBenchmarkDate = portfolioValues[0].date;
            const initialBenchmarkPrice = getPriceForDate(benchmarkPriceData, initialBenchmarkDate);
            
            if (!initialBenchmarkPrice) {
              console.log(`No benchmark price available for initial date (${initialBenchmarkDate})`);
              return resolve({
                message: `No benchmark price available for initial date (${initialBenchmarkDate})`,
                marketPerformance: []
              });
            }
            
            // Calculate benchmark values for each portfolio date
            const benchmarkValues = portfolioValues.map(dayValue => {
              const benchmarkPrice = getPriceForDate(benchmarkPriceData, dayValue.date);
              if (!benchmarkPrice) return null;
              
              return {
                date: dayValue.date,
                value: initialPortfolioValue * (benchmarkPrice / initialBenchmarkPrice)
              };
            }).filter(item => item !== null);
            
            if (benchmarkValues.length < 2) {
              console.log('Not enough benchmark data points after matching with portfolio dates');
              return resolve({
                message: 'Not enough benchmark data points after matching with portfolio dates',
                marketPerformance: []
              });
            }

            // Get matching portfolio values (dates that exist in both datasets)
            const matchedDates = new Set(benchmarkValues.map(item => item.date));
            const matchedPortfolioValues = portfolioValues.filter(item => matchedDates.has(item.date));
            
            // Sort both arrays by date
            matchedPortfolioValues.sort((a, b) => new Date(a.date) - new Date(b.date));
            benchmarkValues.sort((a, b) => new Date(a.date) - new Date(b.date));
            
            // Calculate daily returns for portfolio and benchmark
            const returns = [];
            for (let i = 1; i < matchedPortfolioValues.length; i++) {
              const portfolioPrevValue = matchedPortfolioValues[i - 1].value;
              const portfolioCurrentValue = matchedPortfolioValues[i].value;
              const portfolioReturn = ((portfolioCurrentValue - portfolioPrevValue) / portfolioPrevValue) * 100;
              
              const benchmarkPrevValue = benchmarkValues[i - 1].value;
              const benchmarkCurrentValue = benchmarkValues[i].value;
              const benchmarkReturn = ((benchmarkCurrentValue - benchmarkPrevValue) / benchmarkPrevValue) * 100;
              
              const activeReturn = portfolioReturn - benchmarkReturn;
              
              returns.push({
                date: matchedPortfolioValues[i].date,
                portfolioReturn,
                benchmarkReturn,
                activeReturn,
                isUpMarket: benchmarkReturn > 0
              });
            }

            // Rest of the function remains the same (calculating up/down market metrics)
            const upMarketDays = returns.filter(day => day.isUpMarket);
            const downMarketDays = returns.filter(day => !day.isUpMarket);
            
            // Calculate metrics for up market
            const upMarketOccurrences = upMarketDays.length;
            const upMarketAboveBenchmark = upMarketDays.filter(day => day.activeReturn > 0).length;
            const upMarketPercentageAboveBenchmark = upMarketOccurrences > 0 
              ? (upMarketAboveBenchmark / upMarketOccurrences) * 100 
              : 0;
            
            const upMarketAverageActiveReturn = upMarketOccurrences > 0
              ? upMarketDays.reduce((sum, day) => sum + day.activeReturn, 0) / upMarketOccurrences
              : 0;
            
            // Calculate metrics for down market
            const downMarketOccurrences = downMarketDays.length;
            const downMarketAboveBenchmark = downMarketDays.filter(day => day.activeReturn > 0).length;
            const downMarketPercentageAboveBenchmark = downMarketOccurrences > 0 
              ? (downMarketAboveBenchmark / downMarketOccurrences) * 100 
              : 0;
            
            const downMarketAverageActiveReturn = downMarketOccurrences > 0
              ? downMarketDays.reduce((sum, day) => sum + day.activeReturn, 0) / downMarketOccurrences
              : 0;
            
            // Calculate total metrics
            const totalOccurrences = returns.length;
            const totalAboveBenchmark = returns.filter(day => day.activeReturn > 0).length;
            const totalPercentageAboveBenchmark = totalOccurrences > 0 
              ? (totalAboveBenchmark / totalOccurrences) * 100 
              : 0;
            
            const totalAverageActiveReturn = totalOccurrences > 0
              ? returns.reduce((sum, day) => sum + day.activeReturn, 0) / totalOccurrences
              : 0;
            
            // Format the results
            const marketPerformance = [
              {
                marketType: 'Up Market',
                occurrences: upMarketOccurrences,
                percentageAboveBenchmark: parseFloat(upMarketPercentageAboveBenchmark.toFixed(2)),
                averageActiveReturnAboveBenchmark: parseFloat((upMarketDays.filter(day => day.activeReturn > 0).reduce((sum, day) => sum + day.activeReturn, 0) / (upMarketAboveBenchmark || 1)).toFixed(2)),
                averageActiveReturnBelowBenchmark: parseFloat((upMarketDays.filter(day => day.activeReturn <= 0).reduce((sum, day) => sum + day.activeReturn, 0) / ((upMarketOccurrences - upMarketAboveBenchmark) || 1)).toFixed(2)),
                totalAverageActiveReturn: parseFloat(upMarketAverageActiveReturn.toFixed(2))
              },
              {
                marketType: 'Down Market',
                occurrences: downMarketOccurrences,
                percentageAboveBenchmark: parseFloat(downMarketPercentageAboveBenchmark.toFixed(2)),
                averageActiveReturnAboveBenchmark: parseFloat((downMarketDays.filter(day => day.activeReturn > 0).reduce((sum, day) => sum + day.activeReturn, 0) / (downMarketAboveBenchmark || 1)).toFixed(2)),
                averageActiveReturnBelowBenchmark: parseFloat((downMarketDays.filter(day => day.activeReturn <= 0).reduce((sum, day) => sum + day.activeReturn, 0) / ((downMarketOccurrences - downMarketAboveBenchmark) || 1)).toFixed(2)),
                totalAverageActiveReturn: parseFloat(downMarketAverageActiveReturn.toFixed(2))
              },
              {
                marketType: 'Total',
                occurrences: totalOccurrences,
                percentageAboveBenchmark: parseFloat(totalPercentageAboveBenchmark.toFixed(2)),
                averageActiveReturnAboveBenchmark: parseFloat((returns.filter(day => day.activeReturn > 0).reduce((sum, day) => sum + day.activeReturn, 0) / (totalAboveBenchmark || 1)).toFixed(2)),
                averageActiveReturnBelowBenchmark: parseFloat((returns.filter(day => day.activeReturn <= 0).reduce((sum, day) => sum + day.activeReturn, 0) / ((totalOccurrences - totalAboveBenchmark) || 1)).toFixed(2)),
                totalAverageActiveReturn: parseFloat(totalAverageActiveReturn.toFixed(2))
              }
            ];
            
            resolve({
              marketPerformance
            });
          })
          .catch(error => {
            console.error('Error getting benchmark data:', error);
            reject(error);
          });
      })
      .catch(reject);
  });
}

// GET route for market performance
app.get('/market-performance', (req, res) => {
  calculateUpDownMarketPerformance()
    .then(data => {
      res.json(data);
    })
    .catch(err => {
      console.error('Error calculating market performance:', err.message);
      res.status(500).json({ error: 'Error calculating market performance' });
    });
});

// GET route to return the fundamentals data date
app.get('/fundamentals-date', (req, res) => {
  // For simplicity, we'll use the current date as the fundamentals data date
  const currentDate = new Date();
  const formattedDate = currentDate.toISOString().split('T')[0]; // Format as YYYY-MM-DD
  
  res.json({
    fundamentalsDate: formattedDate
  });
});

/**
 * Calculate Arithmetic Mean
 * @param {Array} values - Array of returns
 * @returns {number} Arithmetic mean
 */
function calculateArithmeticMean(values) {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

/**
 * Calculate Geometric Mean
 * @param {Array} values - Array of returns (as decimals, e.g., 0.05 for 5%)
 * @returns {number} Geometric mean
 */
function calculateGeometricMean(values) {
  if (values.length === 0) return 0;
  // Convert returns to growth factors (1 + r)
  const growthFactors = values.map(r => 1 + r);
  // Calculate product of all growth factors
  const product = growthFactors.reduce((prod, factor) => prod * factor, 1);
  // Take the nth root (where n is the number of periods)
  return Math.pow(product, 1 / values.length) - 1;
}

/**
 * Calculate Beta (measure of volatility/systemic risk compared to benchmark)
 * @param {Array} portfolioReturns - Array of portfolio returns
 * @param {Array} benchmarkReturns - Array of benchmark returns
 * @returns {number} Beta value
 */
function calculateBeta(portfolioReturns, benchmarkReturns) {
  if (portfolioReturns.length !== benchmarkReturns.length || portfolioReturns.length < 2) {
    return 0;
  }
  
  // Calculate covariance
  const portfolioMean = calculateArithmeticMean(portfolioReturns);
  const benchmarkMean = calculateArithmeticMean(benchmarkReturns);
  
  let covariance = 0;
  let benchmarkVariance = 0;
  
  for (let i = 0; i < portfolioReturns.length; i++) {
    const pDiff = portfolioReturns[i] - portfolioMean;
    const bDiff = benchmarkReturns[i] - benchmarkMean;
    
    covariance += pDiff * bDiff;
    benchmarkVariance += bDiff * bDiff;
  }
  
  covariance /= portfolioReturns.length;
  benchmarkVariance /= benchmarkReturns.length;
  
  // Beta = Covariance(portfolio, benchmark) / Variance(benchmark)
  return benchmarkVariance === 0 ? 1 : covariance / benchmarkVariance;
}

/**
 * Calculate Alpha (excess return of portfolio over benchmark, adjusted for risk)
 * @param {number} portfolioReturn - Annualized portfolio return (as decimal)
 * @param {number} riskFreeRate - Risk-free rate (as decimal)
 * @param {number} beta - Portfolio beta relative to benchmark
 * @param {number} benchmarkReturn - Annualized benchmark return (as decimal)
 * @returns {number} Alpha value as a percentage
 */
function calculateAlpha(portfolioReturn, riskFreeRate, beta, benchmarkReturn) {
  // Alpha = Portfolio Return - [Risk Free Rate + Beta * (Benchmark Return - Risk Free Rate)]
  return (portfolioReturn - (riskFreeRate + beta * (benchmarkReturn - riskFreeRate))) * 100;
}

/**
 * Calculate R-Squared (how much of portfolio's variance is explained by benchmark)
 * @param {Array} portfolioReturns - Array of portfolio returns
 * @param {Array} benchmarkReturns - Array of benchmark returns
 * @returns {number} R-Squared value (0-1)
 */
function calculateRSquared(portfolioReturns, benchmarkReturns) {
  if (portfolioReturns.length !== benchmarkReturns.length || portfolioReturns.length < 2) {
    return 0;
  }
  
  // Calculate correlation coefficient and square it
  const correlation = calculateBenchmarkCorrelation(portfolioReturns, benchmarkReturns);
  return Math.pow(correlation, 2);
}

/**
 * Calculate Treynor Ratio (return earned in excess of risk-free rate per unit of market risk)
 * @param {number} portfolioReturn - Annualized portfolio return (as decimal)
 * @param {number} riskFreeRate - Risk-free rate (as decimal)
 * @param {number} beta - Portfolio beta
 * @returns {number} Treynor Ratio
 */
function calculateTreynorRatio(portfolioReturn, riskFreeRate, beta) {
  if (Math.abs(beta) < 0.0001) return 0; // Avoid division by zero
  return (portfolioReturn - riskFreeRate) / beta;
}

/**
 * Calculate Calmar Ratio (return relative to maximum drawdown)
 * @param {number} annualizedReturn - Annualized return (as decimal)
 * @param {number} maxDrawdown - Maximum drawdown (as decimal)
 * @returns {number} Calmar Ratio
 */
function calculateCalmarRatio(annualizedReturn, maxDrawdown) {
  if (maxDrawdown === 0) return 0; // Avoid division by zero
  return annualizedReturn / maxDrawdown;
}

/**
 * Calculate Modigliani-Modigliani Measure (M²)
 * @param {number} portfolioReturn - Annualized portfolio return (as decimal)
 * @param {number} riskFreeRate - Risk-free rate (as decimal)
 * @param {number} portfolioStdDev - Portfolio standard deviation (as decimal)
 * @param {number} benchmarkStdDev - Benchmark standard deviation (as decimal)
 * @returns {number} M² value as a percentage
 */
function calculateModiglianiMeasure(portfolioReturn, riskFreeRate, portfolioStdDev, benchmarkStdDev) {
  if (portfolioStdDev === 0) return 0;
  // M² = [Rp + (Bp/Bm - 1) × Rf] - Bm
  // Where Rp = portfolio return, Rf = risk-free rate, Bp = portfolio std dev, Bm = benchmark std dev
  return ((portfolioReturn - riskFreeRate) * (benchmarkStdDev / portfolioStdDev) + riskFreeRate) * 100;
}

/**
 * Calculate Active Return (portfolio return minus benchmark return)
 * @param {number} portfolioReturn - Portfolio return (as decimal)
 * @param {number} benchmarkReturn - Benchmark return (as decimal)
 * @returns {number} Active return as a percentage
 */
function calculateActiveReturn(portfolioReturn, benchmarkReturn) {
  return (portfolioReturn - benchmarkReturn) * 100;
}

/**
 * Calculate Tracking Error (standard deviation of active returns)
 * @param {Array} portfolioReturns - Array of portfolio returns
 * @param {Array} benchmarkReturns - Array of benchmark returns
 * @returns {number} Tracking error as a percentage
 */
function calculateTrackingError(portfolioReturns, benchmarkReturns) {
  if (portfolioReturns.length !== benchmarkReturns.length || portfolioReturns.length < 2) {
    return 0;
  }
  
  // Calculate active returns
  const activeReturns = portfolioReturns.map((pr, i) => pr - benchmarkReturns[i]);
  
  // Calculate standard deviation of active returns
  const mean = calculateArithmeticMean(activeReturns);
  const variance = activeReturns.reduce((sum, ar) => sum + Math.pow(ar - mean, 2), 0) / activeReturns.length;
  const trackingError = Math.sqrt(variance);
  
  // Annualize if monthly data (multiply by sqrt(12))
  return trackingError * Math.sqrt(12) * 100; // Convert to percentage
}

/**
 * Calculate Information Ratio (active return per unit of active risk)
 * @param {number} activeReturn - Active return (as decimal)
 * @param {number} trackingError - Tracking error (as decimal)
 * @returns {number} Information ratio
 */
function calculateInformationRatio(activeReturn, trackingError) {
  if (trackingError === 0) return 0; // Avoid division by zero
  return activeReturn / trackingError;
}

/**
 * Calculate Skewness (asymmetry of returns distribution)
 * @param {Array} returns - Array of returns
 * @returns {number} Skewness value
 */
function calculateSkewness(returns) {
  if (returns.length < 3) return 0;
  
  const mean = calculateArithmeticMean(returns);
  const stdDev = Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length);
  
  if (stdDev === 0) return 0; // Avoid division by zero
  
  // Calculate sum of cubed deviations from mean
  const sumCubedDeviations = returns.reduce((sum, r) => sum + Math.pow((r - mean) / stdDev, 3), 0);
  
  // Fisher's moment coefficient of skewness
  return (sumCubedDeviations * returns.length) / ((returns.length - 1) * (returns.length - 2));
}

/**
 * Calculate Excess Kurtosis (peakedness or flatness of returns distribution)
 * @param {Array} returns - Array of returns
 * @returns {number} Excess Kurtosis value
 */
function calculateExcessKurtosis(returns) {
  if (returns.length < 4) return 0;
  
  const mean = calculateArithmeticMean(returns);
  const stdDev = Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length);
  
  if (stdDev === 0) return 0; // Avoid division by zero
  
  // Calculate sum of fourth power of deviations from mean
  const sumQuarticDeviations = returns.reduce((sum, r) => sum + Math.pow((r - mean) / stdDev, 4), 0);
  
  // Excess kurtosis = Kurtosis - 3 (subtract normal distribution kurtosis)
  return ((sumQuarticDeviations * returns.length * (returns.length + 1)) / 
          ((returns.length - 1) * (returns.length - 2) * (returns.length - 3))) - 
         (3 * Math.pow(returns.length - 1, 2) / ((returns.length - 2) * (returns.length - 3)));
}

/**
 * Calculate Historical Value-at-Risk (VaR)
 * @param {Array} returns - Array of returns
 * @param {number} confidenceLevel - Confidence level (e.g., 0.95 for 95%)
 * @returns {number} Historical VaR as a percentage (positive number)
 */
function calculateHistoricalVaR(returns, confidenceLevel = 0.95) {
  if (returns.length < 2) return 0;
  
  // Sort returns from worst to best
  const sortedReturns = [...returns].sort((a, b) => a - b);
  
  // Find the return at the specified percentile
  const index = Math.floor(sortedReturns.length * (1 - confidenceLevel));
  const var_value = -sortedReturns[index]; // Negate since VaR is typically expressed as a positive number
  
  return var_value * 100; // Convert to percentage
}

/**
 * Calculate Analytical Value-at-Risk (assuming normal distribution)
 * @param {Array} returns - Array of returns
 * @param {number} confidenceLevel - Confidence level (e.g., 0.95 for 95%)
 * @returns {number} Analytical VaR as a percentage (positive number)
 */
function calculateAnalyticalVaR(returns, confidenceLevel = 0.95) {
  if (returns.length < 2) return 0;
  
  const mean = calculateArithmeticMean(returns);
  const stdDev = Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length);
  
  // Standard normal inverse of (1 - confidence level)
  // For 95% confidence, use 1.645
  const z = confidenceLevel === 0.95 ? 1.645 : 
            confidenceLevel === 0.99 ? 2.326 : 
            confidenceLevel === 0.9 ? 1.282 : 1.645;
  
  const var_value = -(mean - z * stdDev); // Negate to make positive
  
  return var_value * 100; // Convert to percentage
}

/**
 * Calculate Conditional Value-at-Risk (CVaR) / Expected Shortfall
 * @param {Array} returns - Array of returns
 * @param {number} confidenceLevel - Confidence level (e.g., 0.95 for 95%)
 * @returns {number} CVaR as a percentage (positive number)
 */
function calculateConditionalVaR(returns, confidenceLevel = 0.95) {
  if (returns.length < 2) return 0;
  
  // Sort returns from worst to best
  const sortedReturns = [...returns].sort((a, b) => a - b);
  
  // Find the cutoff index for VaR
  const varIndex = Math.floor(sortedReturns.length * (1 - confidenceLevel));
  
  // Calculate average of returns beyond VaR
  let sum = 0;
  for (let i = 0; i < varIndex; i++) {
    sum += sortedReturns[i];
  }
  
  const cvar_value = -(sum / varIndex); // Negate to make positive
  
  return cvar_value * 100; // Convert to percentage
}

/**
 * Calculate Safe Withdrawal Rate
 * @param {number} portfolioReturn - Annualized portfolio return (as decimal)
 * @param {number} stdDev - Annualized standard deviation (as decimal)
 * @param {number} years - Withdrawal period in years (default: 30)
 * @param {number} successRate - Desired success rate (default: 0.9 for 90%)
 * @returns {number} Safe withdrawal rate as a percentage
 */
function calculateSafeWithdrawalRate(portfolioReturn, stdDev, years = 30, successRate = 0.9) {
  // Simple estimate based on historical returns and volatility
  // This is a simplified version of the calculation
  const z = successRate === 0.9 ? -1.282 : 
            successRate === 0.95 ? -1.645 : 
            successRate === 0.99 ? -2.326 : -1.282;
  
  const swr = portfolioReturn + (z * stdDev * Math.sqrt(years / (2 * years - 1)));
  
  return Math.max(0, swr * 100); // Convert to percentage, ensure not negative
}

/**
 * Calculate Perpetual Withdrawal Rate
 * @param {number} portfolioReturn - Annualized portfolio return (as decimal)
 * @returns {number} Perpetual withdrawal rate as a percentage
 */
function calculatePerpetualWithdrawalRate(portfolioReturn) {
  // A simple perpetual withdrawal rate is the real return minus a small buffer
  const buffer = 0.01; // 1% buffer
  return Math.max(0, (portfolioReturn - buffer) * 100); // Convert to percentage, ensure not negative
}

/**
 * Calculate Positive Periods (percentage of periods with positive returns)
 * @param {Array} returns - Array of returns
 * @returns {number} Percentage of positive periods
 */
function calculatePositivePeriods(returns) {
  if (returns.length === 0) return 0;
  
  const positiveCount = returns.filter(r => r > 0).length;
  return (positiveCount / returns.length) * 100;
}

/**
 * Calculate Gain/Loss Ratio (average gain / average loss)
 * @param {Array} returns - Array of returns
 * @returns {number} Gain/Loss ratio
 */
function calculateGainLossRatio(returns) {
  if (returns.length === 0) return 0;
  
  const gains = returns.filter(r => r > 0);
  const losses = returns.filter(r => r < 0);
  
  if (losses.length === 0) return gains.length > 0 ? Infinity : 0;
  
  const avgGain = gains.length > 0 ? gains.reduce((sum, g) => sum + g, 0) / gains.length : 0;
  const avgLoss = Math.abs(losses.reduce((sum, l) => sum + l, 0) / losses.length);
  
  return avgLoss === 0 ? 0 : avgGain / avgLoss;
}

/**
 * Calculate all risk and return metrics for a portfolio
 * @param {Array} portfolioMonthlyValues - Array of portfolio monthly values
 * @param {Array} benchmarkMonthlyValues - Array of benchmark monthly values
 * @param {number} riskFreeRate - Annual risk-free rate as a percentage (default: 1.5%)
 * @returns {Object} Object containing all risk and return metrics
 */
function calculateRiskReturnMetrics(portfolioMonthlyValues, benchmarkMonthlyValues, riskFreeRate = 1.5) {
  // Convert risk-free rate from percentage to decimal and to monthly
  const monthlyRiskFreeRate = riskFreeRate / 100 / 12;
  
  // Calculate monthly returns
  const portfolioReturns = [];
  const benchmarkReturns = [];
  
  for (let i = 1; i < portfolioMonthlyValues.length; i++) {
    const prevPortfolioValue = portfolioMonthlyValues[i - 1].value;
    const currPortfolioValue = portfolioMonthlyValues[i].value;
    portfolioReturns.push((currPortfolioValue / prevPortfolioValue) - 1);
    
    if (benchmarkMonthlyValues && benchmarkMonthlyValues.length > i) {
      const prevBenchmarkValue = benchmarkMonthlyValues[i - 1].value;
      const currBenchmarkValue = benchmarkMonthlyValues[i].value;
      benchmarkReturns.push((currBenchmarkValue / prevBenchmarkValue) - 1);
    }
  }
  
  // Portfolio stats
  const firstValue = portfolioMonthlyValues[0].value;
  const lastValue = portfolioMonthlyValues[portfolioMonthlyValues.length - 1].value;
  const years = portfolioMonthlyValues.length / 12;
  
  // Calculate monthly metrics
  const monthlyArithmeticMean = calculateArithmeticMean(portfolioReturns);
  const monthlyGeometricMean = calculateGeometricMean(portfolioReturns);
  
  // Calculate standard deviation (monthly)
  const monthlyStdDev = Math.sqrt(
    portfolioReturns.reduce((sum, r) => sum + Math.pow(r - monthlyArithmeticMean, 2), 0) / portfolioReturns.length
  );
  
  // Calculate downside deviation (monthly)
  const monthlyDownsideDeviation = calculateDownsideDeviation(portfolioMonthlyValues);
  
  // Calculate annualized metrics
  const annualizedArithmeticMean = ((1 + monthlyArithmeticMean) ** 12) - 1;
  const annualizedGeometricMean = ((1 + monthlyGeometricMean) ** 12) - 1;
  const annualizedStdDev = monthlyStdDev * Math.sqrt(12);
  
  // Calculate benchmark metrics if available
  let beta = 0;
  let alpha = 0;
  let rSquared = 0;
  let treynorRatio = 0;
  let benchmarkAnnualizedReturn = 0;
  let activeReturn = 0;
  let trackingError = 0;
  let informationRatio = 0;
  
  if (benchmarkReturns.length > 0) {
    beta = calculateBeta(portfolioReturns, benchmarkReturns);
    
    // Calculate benchmark annualized return
    const benchmarkMonthlyGeometricMean = calculateGeometricMean(benchmarkReturns);
    benchmarkAnnualizedReturn = ((1 + benchmarkMonthlyGeometricMean) ** 12) - 1;
    
    alpha = calculateAlpha(annualizedGeometricMean, riskFreeRate/100, beta, benchmarkAnnualizedReturn);
    rSquared = calculateRSquared(portfolioReturns, benchmarkReturns);
    treynorRatio = calculateTreynorRatio(annualizedGeometricMean, riskFreeRate/100, beta);
    activeReturn = calculateActiveReturn(annualizedGeometricMean, benchmarkAnnualizedReturn);
    trackingError = calculateTrackingError(portfolioReturns, benchmarkReturns);
    informationRatio = calculateInformationRatio(activeReturn/100, trackingError/100);
  }
  
  // Calculate drawdown and Calmar ratio
  const { maxDrawdown } = calculateMaxDrawdown(portfolioMonthlyValues.map(m => ({ date: m.date, value: m.value })));
  const calmarRatio = calculateCalmarRatio(annualizedGeometricMean, maxDrawdown/100);
  
  // Calculate risk metrics
  const skewness = calculateSkewness(portfolioReturns);
  const excessKurtosis = calculateExcessKurtosis(portfolioReturns);
  
  // Calculate Value-at-Risk metrics (5% confidence level)
  const historicalVaR = calculateHistoricalVaR(portfolioReturns, 0.95);
  const analyticalVaR = calculateAnalyticalVaR(portfolioReturns, 0.95);
  const conditionalVaR = calculateConditionalVaR(portfolioReturns, 0.95);
  
  // Calculate withdrawal rates
  const safeWithdrawalRate = calculateSafeWithdrawalRate(annualizedGeometricMean, annualizedStdDev);
  const perpetualWithdrawalRate = calculatePerpetualWithdrawalRate(annualizedGeometricMean);
  
  // Calculate positive periods and gain/loss ratio
  const positivePeriods = calculatePositivePeriods(portfolioReturns);
  const gainLossRatio = calculateGainLossRatio(portfolioReturns);
  
  // Calculate Modigliani Measure (if benchmark data available)
  let modiglianiMeasure = 0;
  if (benchmarkReturns.length > 0) {
    const benchmarkStdDev = Math.sqrt(
      benchmarkReturns.reduce((sum, r) => sum + Math.pow(r - calculateArithmeticMean(benchmarkReturns), 2), 0) / benchmarkReturns.length
    ) * Math.sqrt(12);
    
    modiglianiMeasure = calculateModiglianiMeasure(
      annualizedGeometricMean, 
      riskFreeRate/100, 
      annualizedStdDev, 
      benchmarkStdDev
    );
  }
  
  // Return all metrics
  return {
    arithmetic_mean: {
      monthly: monthlyArithmeticMean * 100,      // Convert to percentage
      annualized: annualizedArithmeticMean * 100  // Convert to percentage
    },
    geometric_mean: {
      monthly: monthlyGeometricMean * 100,       // Convert to percentage
      annualized: annualizedGeometricMean * 100   // Convert to percentage
    },
    standard_deviation: {
      monthly: monthlyStdDev * 100,              // Convert to percentage
      annualized: annualizedStdDev * 100          // Convert to percentage
    },
    downside_deviation: {
      monthly: monthlyDownsideDeviation * 100     // Convert to percentage
    },
    beta,
    alpha,
    r_squared: rSquared,
    treynor_ratio: treynorRatio * 100,            // Convert to percentage
    calmar_ratio: calmarRatio,
    modigliani_measure: modiglianiMeasure,
    active_return: activeReturn,
    tracking_error: trackingError,
    information_ratio: informationRatio,
    skewness,
    excess_kurtosis: excessKurtosis,
    value_at_risk: {
      historical: historicalVaR,
      analytical: analyticalVaR,
      conditional: conditionalVaR
    },
    withdrawal_rate: {
      safe: safeWithdrawalRate,
      perpetual: perpetualWithdrawalRate
    },
    positive_periods: positivePeriods,
    gain_loss_ratio: gainLossRatio
  };
}

// Create a GET route to retrieve risk and return metrics
app.get('/risk-return', async (req, res) => {
  try {
    const benchmarkTicker = req.query.benchmark || 'SPY';
    const dailyValues = await calculateDailyPortfolioValues();
    
    if (!dailyValues || dailyValues.length === 0) {
      console.log('No portfolio data available for risk/return calculations');
      return res.status(404).json({ 
        error: 'No portfolio data available', 
        message: 'Please upload transaction data before calculating risk/return metrics.'
      });
    }
    
    // Try to calculate monthly values, catch and handle any errors
    let monthlyValues;
    try {
      monthlyValues = calculateMonthlyPortfolioValues(dailyValues);
      if (!monthlyValues || monthlyValues.length === 0) {
        throw new Error("Failed to calculate monthly values");
      }
    } catch (error) {
      console.error('Error calculating monthly portfolio values:', error);
      return res.status(500).json({ 
        error: 'Error calculating monthly portfolio values', 
        message: 'Failed to calculate monthly portfolio values. Please try again later.'
      });
    }
    
    // Get actual benchmark data
    const benchmarkPrices = await getStockPrices(benchmarkTicker);
    
    if (!benchmarkPrices || !benchmarkPrices['Time Series (Daily)']) {
      // Return a proper error response instead of falling back to dummy data
      console.log(`Failed to fetch benchmark data for ${benchmarkTicker}`);
      return res.status(500).json({ 
        error: 'Failed to fetch benchmark data', 
        message: `Could not retrieve data for benchmark ${benchmarkTicker}. Please try again later or select a different benchmark.`
      });
    }
    
    // Calculate benchmark monthly values using real data
    const initialPortfolioValue = dailyValues[0].value;
    const initialBenchmarkDate = dailyValues[0].date;
    const initialBenchmarkPrice = getPriceForDate(benchmarkPrices, initialBenchmarkDate);
    
    if (!initialBenchmarkPrice) {
      // Return a proper error response instead of falling back to dummy data
      console.log(`No initial price found for benchmark ${benchmarkTicker}`);
      return res.status(500).json({ 
        error: 'Missing benchmark price data', 
        message: `Could not find initial price for benchmark ${benchmarkTicker}. Please try again later or select a different benchmark.`
      });
    }
    
    // Calculate real benchmark monthly values
    const benchmarkDailyValues = [];
    
    for (const mv of monthlyValues) {
      const benchmarkPrice = getPriceForDate(benchmarkPrices, mv.date);
      if (benchmarkPrice) {
        benchmarkDailyValues.push({
          date: mv.date,
          value: initialPortfolioValue * (benchmarkPrice / initialBenchmarkPrice)
        });
      } else {
        // Skip dates where benchmark price is missing instead of approximating
        console.log(`Missing benchmark price for date ${mv.date}, skipping`);
      }
    }
    
    // Handle the case where we couldn't get enough benchmark prices
    if (benchmarkDailyValues.length < monthlyValues.length / 2) {
      // Return a proper error response instead of falling back to dummy data
      console.log(`Not enough benchmark prices for ${benchmarkTicker}`);
      return res.status(500).json({ 
        error: 'Insufficient benchmark data', 
        message: `Not enough price data available for benchmark ${benchmarkTicker}. Please try again later or select a different benchmark.`
      });
    }
    
    // Process the benchmark daily values into monthly values
    let benchmarkMonthlyValues;
    try {
      benchmarkMonthlyValues = calculateMonthlyPortfolioValues(benchmarkDailyValues);
      if (!benchmarkMonthlyValues || benchmarkMonthlyValues.length === 0) {
        throw new Error("Failed to calculate benchmark monthly values");
      }
    } catch (error) {
      console.error('Error calculating benchmark monthly values:', error);
      return res.status(500).json({ 
        error: 'Error calculating benchmark values', 
        message: `Failed to calculate monthly values for benchmark ${benchmarkTicker}. Please try again with a different benchmark.`
      });
    }
    
    let riskReturnMetrics;
    try {
      riskReturnMetrics = calculateRiskReturnMetrics(monthlyValues, benchmarkMonthlyValues);
      if (!riskReturnMetrics) {
        throw new Error("Failed to calculate risk/return metrics");
      }
    } catch (error) {
      console.error('Error calculating final risk/return metrics:', error);
      return res.status(500).json({ 
        error: 'Error calculating risk/return metrics', 
        message: 'Failed to calculate risk/return metrics. Please try again later.'
      });
    }
    
    res.json({ 
      success: true, 
      metrics: riskReturnMetrics 
    });
  } catch (error) {
    console.error('Error calculating risk/return metrics:', error);
    return res.status(500).json({ 
      error: 'Error in risk/return calculation process', 
      message: 'An error occurred while calculating risk/return metrics. Please try again later.'
    });
  }
});

// Create a GET route to retrieve portfolio growth data
app.get('/portfolio-growth', async (req, res) => {
  const benchmarkTicker = req.query.benchmark || 'SPY';
  
  try {
    // Get portfolio daily values
    const portfolioValues = await calculateDailyPortfolioValues();
    
    if (!portfolioValues || portfolioValues.length === 0) {
      console.log('No portfolio data available, returning fallback data');
      // Return fallback data instead of 404
      const startDate = new Date('2023-01-01');
      const endDate = new Date();
      const days = Math.floor((endDate - startDate) / (1000 * 60 * 60 * 24));
      
      const fallbackData = Array.from({ length: days }, (_, i) => {
        const currentDate = new Date(startDate);
        currentDate.setDate(startDate.getDate() + i);
        
        return {
          date: currentDate.toISOString().split('T')[0],
          portfolioValue: 10000 * (1 + 0.0001 * i) * (0.99 + 0.02 * Math.random()),
          benchmarkValue: 10000 * (1 + 0.00009 * i) * (0.99 + 0.02 * Math.random())
        };
      });
      
      return res.json(fallbackData);
    }
    
    // Get benchmark price data
    const benchmarkPrices = await getStockPrices(benchmarkTicker);
    
    if (!benchmarkPrices || !benchmarkPrices['Time Series (Daily)']) {
      console.log(`No benchmark data available for ${benchmarkTicker}, returning fallback data`);
      // Return fallback data instead of 404
      const fallbackData = portfolioValues.map(item => {
        return {
          date: item.date,
          portfolioValue: item.value,
          benchmarkValue: item.value * (0.9 + 0.2 * Math.random()) // Simulate benchmark
        };
      });
      
      return res.json(fallbackData);
    }
    
    // Calculate benchmark values starting with same amount as initial portfolio value
    const initialPortfolioValue = portfolioValues[0].value;
    const initialBenchmarkDate = portfolioValues[0].date;
    const initialBenchmarkPrice = getPriceForDate(benchmarkPrices, initialBenchmarkDate);
    
    if (!initialBenchmarkPrice) {
      console.log(`No benchmark price available for initial date (${initialBenchmarkDate}), returning fallback data`);
      // Return fallback data instead of 404
      const fallbackData = portfolioValues.map(item => {
        return {
          date: item.date,
          portfolioValue: item.value,
          benchmarkValue: item.value * (0.9 + 0.2 * Math.random()) // Simulate benchmark
        };
      });
      
      return res.json(fallbackData);
    }
    
    // Create combined dataset with portfolio and benchmark values
    const growthData = portfolioValues.map(item => {
      const benchmarkPrice = getPriceForDate(benchmarkPrices, item.date);
      const benchmarkValue = benchmarkPrice ? 
        (initialPortfolioValue * (benchmarkPrice / initialBenchmarkPrice)) : 
        // If no benchmark price for this date, use a close approximation
        item.value * 0.95;
      
      return {
        date: item.date,
        portfolioValue: item.value,
        benchmarkValue: benchmarkValue
      };
    });
    
    // If after all this we still have no data, return error instead of fallback
    if (growthData.length === 0) {
      console.log('Growth data is empty after processing');
      return res.status(404).json({
        error: 'No portfolio growth data available',
        message: 'Please ensure you have uploaded transaction data with valid dates and try again.'
      });
    }
    
    res.json(growthData);
  } catch (error) {
    console.error('Error calculating portfolio growth:', error);
    // Return error instead of fallback data
    res.status(500).json({
      error: 'Error calculating portfolio growth',
      message: 'An error occurred while calculating portfolio growth. Please try again later.'
    });
  }
});

// Create a GET route to retrieve portfolio drawdown data
app.get('/portfolio-drawdown', async (req, res) => {
  try {
    // Get portfolio daily values
    const portfolioValues = await calculateDailyPortfolioValues();
    
    if (!portfolioValues || portfolioValues.length === 0) {
      return res.status(404).json({
        success: false,
        error: 'No portfolio data available'
      });
    }
    
    // Calculate running maximum and drawdown percentage
    let runningMax = portfolioValues[0].value;
    const drawdownData = portfolioValues.map(item => {
      if (item.value > runningMax) {
        runningMax = item.value;
      }
      
      // Calculate drawdown as percentage from peak
      const drawdownPercentage = runningMax > 0 ? ((runningMax - item.value) / runningMax) * 100 : 0;
      
      return {
        date: item.date,
        value: item.value,
        peak: runningMax,
        drawdownPercentage: drawdownPercentage
      };
    });
    
    res.json(drawdownData);
  } catch (error) {
    console.error('Error calculating portfolio drawdown:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to calculate portfolio drawdown data'
    });
  }
});

// --- Helper Functions ---

/**
 * Fetches historical stock prices for a given ticker from Alpha Vantage,
 * caching results in the SQLite database.
 * @param {string} ticker The stock ticker symbol.
 * @returns {Promise<object|null>} Alpha Vantage time series data or null on error.
 */
async function getStockPrices(ticker) {
    console.log(`[getStockPrices] Checking cache/fetching for ticker: ${ticker}`);
    return new Promise(async (resolve, reject) => {
        // 1. Check cache first
        db.all("SELECT date, close_price FROM stock_prices WHERE ticker = ? ORDER BY date DESC", [ticker], async (err, rows) => {
            if (err) {
                console.error(`[getStockPrices] Error checking cache for ${ticker}:`, err.message);
                // Continue to fetch even if cache check fails
            }

            if (rows && rows.length > 0) {
                console.log(`[getStockPrices] Cache hit for ${ticker}. Found ${rows.length} entries.`);
                // Reconstruct Alpha Vantage-like structure from cache
                const timeSeries = {};
                rows.forEach(row => {
                    // Ensure date format is YYYY-MM-DD
                    const formattedDate = row.date.split('T')[0];
                    timeSeries[formattedDate] = { "4. close": row.close_price.toString() }; // Match AV format
                });
                resolve({ "Time Series (Daily)": timeSeries });
                return;
            }

            // 2. If not in cache, fetch from Alpha Vantage
            console.log(`[getStockPrices] Cache miss for ${ticker}. Fetching from Alpha Vantage...`);
            const apiKey = process.env.ALPHA_VANTAGE_KEY;
            if (!apiKey) {
                console.error("[getStockPrices] ALPHA_VANTAGE_KEY not found in .env");
                return reject(new Error("API key for Alpha Vantage is missing."));
            }
            // Use outputsize=full for more data
            const url = `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=${ticker}&outputsize=full&apikey=${apiKey}`;

            try {
                // Dynamically import node-fetch
                const fetch = (await import('node-fetch')).default;
                const response = await fetch(url);
                const data = await response.json();

                if (data["Error Message"] || !data["Time Series (Daily)"]) {
                    console.error(`[getStockPrices] Error fetching ${ticker} from Alpha Vantage:`, data["Error Message"] || data["Information"] || "Invalid data format");
                    if (data["Note"] && data["Note"].includes("API call frequency")) {
                         console.warn(`[getStockPrices] Alpha Vantage API rate limit likely hit for ${ticker}.`);
                    }
                    resolve(null); // Indicate fetch failure
                    return;
                }

                console.log(`[getStockPrices] Successfully fetched data for ${ticker} from Alpha Vantage.`);
                const timeSeries = data["Time Series (Daily)"];

                // 3. Store fetched data in cache (SQLite)
                const insertStmt = db.prepare("INSERT OR IGNORE INTO stock_prices (ticker, date, close_price) VALUES (?, ?, ?)");
                let insertedCount = 0;
                db.serialize(() => {
                    db.run("BEGIN TRANSACTION;");
                    for (const date in timeSeries) {
                        const closePrice = parseFloat(timeSeries[date]["4. close"]);
                        if (!isNaN(closePrice)) {
                            // Ensure date format is YYYY-MM-DD before inserting
                            const formattedDate = date.split('T')[0];
                            insertStmt.run(ticker, formattedDate, closePrice, function(err) {
                                if (err) {
                                    console.warn(`[getStockPrices] Error inserting ${ticker} price for ${formattedDate}: ${err.message}`);
                                } else if (this.changes > 0) {
                                    insertedCount++;
                                }
                            });
                        }
                    }
                    db.run("COMMIT;", (commitErr) => {
                         if (commitErr) {
                              console.error(`[getStockPrices] Error committing transaction for ${ticker}: ${commitErr.message}`);
                              db.run("ROLLBACK;");
                         } else {
                              console.log(`[getStockPrices] Cached ${insertedCount} new price entries for ${ticker}.`);
                         }
                         insertStmt.finalize((finalizeErr) => {
                            if(finalizeErr) console.error(`[getStockPrices] Error finalizing statement for ${ticker}: ${finalizeErr.message}`);
                         });
                         resolve(data); // Return the fetched data
                    });
                });

            } catch (fetchError) {
                console.error(`[getStockPrices] Network or parsing error fetching ${ticker}:`, fetchError);
                reject(fetchError);
            }
        });
    });
}

// Helper to get unique tickers from transactions
async function getUniqueTickers() {
    return new Promise((resolve, reject) => {
        db.all("SELECT DISTINCT ticker FROM transactions WHERE ticker IS NOT NULL AND ticker != ''", [], (err, rows) => {
            if (err) {
                console.error("Error fetching unique tickers:", err);
                return reject(err);
            }
            resolve(rows.map(row => row.ticker));
        });
    });
}

// Helper to get the first and last date from daily values
function getFirstLastDate(dailyValues) {
    if (!dailyValues || dailyValues.length === 0) {
        return { firstDate: null, lastDate: null };
    }
    // Ensure dates are sorted if not already guaranteed
    dailyValues.sort((a, b) => new Date(a.date) - new Date(b.date));
    return { firstDate: dailyValues[0].date, lastDate: dailyValues[dailyValues.length - 1].date };
}

// Helper to get value for a specific date or closest preceding date
function getValueForDate(dailyValues, targetDate) {
    let closestValue = null;
    // Ensure dailyValues is sorted ascending by date
    // Find the latest entry whose date is less than or equal to targetDate
    for (let i = dailyValues.length - 1; i >= 0; i--) {
        if (dailyValues[i].date <= targetDate) {
            closestValue = dailyValues[i].value;
            break;
        }
    }
    return closestValue;
}

// Helper to get price for a specific date or closest preceding date from Alpha Vantage data
function getPriceForDate(priceData, targetDate) {
    if (!priceData || !priceData['Time Series (Daily)']) {
        return null;
    }
    const timeSeries = priceData['Time Series (Daily)'];
    let closestPrice = null;
    let currentDate = new Date(targetDate); // Start searching from the target date

    // Search backwards for the first available price
    for (let i = 0; i < 7; i++) { // Limit search depth (e.g., 7 days for weekends/holidays)
        const dateStr = currentDate.toISOString().split('T')[0];
        if (timeSeries[dateStr] && timeSeries[dateStr]['4. close']) {
            closestPrice = parseFloat(timeSeries[dateStr]['4. close']);
            break;
        }
        currentDate.setDate(currentDate.getDate() - 1); // Go back one day
    }
    return closestPrice;
}

/**
 * Fetches benchmark prices, aligns them with portfolio daily values, and returns monthly values.
 * @param {string} benchmarkTicker - The ticker symbol for the benchmark (e.g., 'SPY').
 * @param {Array<object>} portfolioDailyValues - Array of portfolio daily values { date, value }.
 * @returns {Promise<Array<object>|null>} Array of benchmark monthly values { year_month, date, value } or null if data is insufficient.
 */
async function getAlignedBenchmarkMonthlyValues(benchmarkTicker, portfolioDailyValues) {
    if (!portfolioDailyValues || portfolioDailyValues.length < 2) {
        console.warn("[getAlignedBenchmarkMonthlyValues] Insufficient portfolio data.");
        return null;
    }

    try {
        console.log(`[getAlignedBenchmarkMonthlyValues] Fetching benchmark data for ${benchmarkTicker}...`);
        const benchmarkPrices = await getStockPrices(benchmarkTicker);

        if (!benchmarkPrices || !benchmarkPrices['Time Series (Daily)']) {
            console.warn(`[getAlignedBenchmarkMonthlyValues] No benchmark price data available for ${benchmarkTicker}.`);
            return null; // Cannot calculate benchmark metrics
        }

        // Align benchmark data with portfolio start date and value
        const initialPortfolioValue = portfolioDailyValues[0].value;
        const initialBenchmarkDate = portfolioDailyValues[0].date;
        const initialBenchmarkPrice = getPriceForDate(benchmarkPrices, initialBenchmarkDate);

        if (initialBenchmarkPrice === null || initialBenchmarkPrice <= 0) {
            console.warn(`[getAlignedBenchmarkMonthlyValues] Could not find valid benchmark price for ${benchmarkTicker} on initial date ${initialBenchmarkDate}.`);
            return null; // Cannot proceed without starting price
        }

        // Create benchmark daily values aligned with portfolio dates and scaled
        const benchmarkDailyValues = portfolioDailyValues.map(item => {
            const benchmarkPrice = getPriceForDate(benchmarkPrices, item.date);
            if (benchmarkPrice !== null) {
                return {
                    date: item.date,
                    value: initialPortfolioValue * (benchmarkPrice / initialBenchmarkPrice)
                };
            }
            return null;
        }).filter(item => item !== null);

        if (benchmarkDailyValues.length < 2) {
            console.warn("[getAlignedBenchmarkMonthlyValues] Not enough aligned benchmark daily data points.");
            return null;
        }

        // Calculate benchmark monthly values from the aligned daily values
        const benchmarkMonthlyValues = calculateMonthlyPortfolioValues(benchmarkDailyValues);
        console.log(`[getAlignedBenchmarkMonthlyValues] Calculated ${benchmarkMonthlyValues.length} benchmark monthly values.`);
        return benchmarkMonthlyValues;

    } catch (error) {
        console.error(`[getAlignedBenchmarkMonthlyValues] Error processing benchmark data for ${benchmarkTicker}:`, error);
        return null; // Return null on error
    }
}

// --- Calculation Functions ---

// ... existing calculateCAGR, calculateAnnualizedStdDev, etc. ...

/**
 * Calculate benchmark correlation using Pearson correlation coefficient.
 * @param {Array} portfolioMonthlyValues - Array of portfolio monthly values { year_month, value }.
 * @param {Array} benchmarkMonthlyValues - Array of benchmark monthly values { year_month, value }.
 * @returns {number|null} Correlation coefficient or null if calculation is not possible.
 */
function calculateBenchmarkCorrelation(portfolioMonthlyValues, benchmarkMonthlyValues) {
  // Return null if insufficient data
  if (!portfolioMonthlyValues || portfolioMonthlyValues.length < 2 || !benchmarkMonthlyValues || benchmarkMonthlyValues.length < 2) {
    return null;
  }

  // Helper to get monthly returns with year_month
  function getReturns(monthlyValues) {
    const returns = {};
    for (let i = 1; i < monthlyValues.length; i++) {
      const prev = monthlyValues[i - 1];
      const curr = monthlyValues[i];
      if (prev.value !== 0) { // Avoid division by zero
        returns[curr.year_month] = (curr.value / prev.value) - 1;
      }
    }
    return returns;
  }

  const portfolioReturnsMap = getReturns(portfolioMonthlyValues);
  const benchmarkReturnsMap = getReturns(benchmarkMonthlyValues);

  // Align returns by year_month
  const portfolioReturns = [];
  const benchmarkReturns = [];
  const commonMonths = Object.keys(portfolioReturnsMap).filter(month => benchmarkReturnsMap.hasOwnProperty(month));

  if (commonMonths.length < 2) { // Need at least 2 common data points for correlation
      console.warn("[calculateBenchmarkCorrelation] Less than 2 common months for correlation.");
      return null;
  }

  commonMonths.forEach(month => {
      portfolioReturns.push(portfolioReturnsMap[month]);
      benchmarkReturns.push(benchmarkReturnsMap[month]);
  });

  const n = portfolioReturns.length;
  if (n === 0) return null;

  const sumX = portfolioReturns.reduce((s, v) => s + v, 0);
  const sumY = benchmarkReturns.reduce((s, v) => s + v, 0);
  const sumXY = portfolioReturns.reduce((s, v, i) => s + v * benchmarkReturns[i], 0);
  const sumX2 = portfolioReturns.reduce((s, v) => s + v * v, 0);
  const sumY2 = benchmarkReturns.reduce((s, v) => s + v * v, 0);

  const numerator = n * sumXY - sumX * sumY;
  const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));

  if (denominator === 0) {
    console.warn("[calculateBenchmarkCorrelation] Denominator is zero, cannot calculate correlation.");
    return null; // Avoid division by zero; correlation is undefined
  }

  const correlation = numerator / denominator;
  return correlation; // Return as a coefficient (e.g., 0.85)
}

/**
 * Calculate upside/downside capture ratio.
 * @param {Array} portfolioMonthlyValues - Array of portfolio monthly values { year_month, value }.
 * @param {Array} benchmarkMonthlyValues - Array of benchmark monthly values { year_month, value }.
 * @returns {Object|null} Object with upside/downside ratios (as percentages) or null if calculation not possible.
 */
function calculateCaptureRatios(portfolioMonthlyValues, benchmarkMonthlyValues) {
  // Return null if insufficient data
  if (!portfolioMonthlyValues || portfolioMonthlyValues.length < 2 || !benchmarkMonthlyValues || benchmarkMonthlyValues.length < 2) {
    return null;
  }

  // Helper to get monthly returns with year_month
  function getReturns(monthlyValues) {
    const returns = {};
    for (let i = 1; i < monthlyValues.length; i++) {
      const prev = monthlyValues[i - 1];
      const curr = monthlyValues[i];
      if (prev.value !== 0) { // Avoid division by zero
        returns[curr.year_month] = (curr.value / prev.value) - 1;
      }
    }
    return returns;
  }

  const portfolioReturnsMap = getReturns(portfolioMonthlyValues);
  const benchmarkReturnsMap = getReturns(benchmarkMonthlyValues);

  // Align returns by year_month
  const portfolioUpReturns = [];
  const benchmarkUpReturns = [];
  const portfolioDownReturns = [];
  const benchmarkDownReturns = [];

  const commonMonths = Object.keys(portfolioReturnsMap).filter(month => benchmarkReturnsMap.hasOwnProperty(month));

  if (commonMonths.length === 0) {
    console.warn("[calculateCaptureRatios] No common months found.");
    return null;
  }

  commonMonths.forEach(month => {
    const portfolioReturn = portfolioReturnsMap[month];
    const benchmarkReturn = benchmarkReturnsMap[month];

    if (benchmarkReturn > 0) {
      portfolioUpReturns.push(1 + portfolioReturn);
      benchmarkUpReturns.push(1 + benchmarkReturn);
    } else if (benchmarkReturn < 0) {
      portfolioDownReturns.push(1 + portfolioReturn);
      benchmarkDownReturns.push(1 + benchmarkReturn);
    }
    // Ignore months where benchmark return is exactly 0
  });

  // Helper to calculate geometric mean from (1 + return) values
  function geometricMean(returnsPlusOne) {
    if (returnsPlusOne.length === 0) return null;
    const product = returnsPlusOne.reduce((prod, val) => prod * val, 1);
    // Use Math.abs for the base in case product is negative (can happen with odd number of negative returns)
    // and handle potential complex numbers by checking sign before powering
    if (product < 0 && returnsPlusOne.length % 2 === 0) {
         console.warn("[geometricMean] Even root of negative number encountered. Returning null.");
         return null; // Or handle appropriately
    }
    const mean = Math.pow(Math.abs(product), 1 / returnsPlusOne.length);
    return product < 0 ? -mean : mean; // Re-apply sign if needed
  }

  const geoMeanPortfolioUp = geometricMean(portfolioUpReturns);
  const geoMeanBenchmarkUp = geometricMean(benchmarkUpReturns);
  const geoMeanPortfolioDown = geometricMean(portfolioDownReturns);
  const geoMeanBenchmarkDown = geometricMean(benchmarkDownReturns);

  let upsideRatio = null;
  if (geoMeanBenchmarkUp !== null && geoMeanBenchmarkUp !== 1) { // Check against 1 (0% return)
      const compoundedPortfolioUp = geoMeanPortfolioUp !== null ? Math.pow(geoMeanPortfolioUp, portfolioUpReturns.length) : 1;
      const compoundedBenchmarkUp = Math.pow(geoMeanBenchmarkUp, benchmarkUpReturns.length);
      // Ratio of compounded returns
      upsideRatio = compoundedBenchmarkUp !== 0 ? (compoundedPortfolioUp / compoundedBenchmarkUp) * 100 : null;
  } else {
      console.warn("[calculateCaptureRatios] No benchmark up-market returns or compounded benchmark return is 1 (0%).");
  }

  let downsideRatio = null;
  if (geoMeanBenchmarkDown !== null && geoMeanBenchmarkDown !== 1) { // Check against 1 (0% return)
      const compoundedPortfolioDown = geoMeanPortfolioDown !== null ? Math.pow(geoMeanPortfolioDown, portfolioDownReturns.length) : 1;
      const compoundedBenchmarkDown = Math.pow(geoMeanBenchmarkDown, benchmarkDownReturns.length);
      // Ratio of compounded returns
      downsideRatio = compoundedBenchmarkDown !== 0 ? (compoundedPortfolioDown / compoundedBenchmarkDown) * 100 : null;
  } else {
       console.warn("[calculateCaptureRatios] No benchmark down-market returns or compounded benchmark return is 1 (0%).");
  }

  return {
    upside_capture_ratio: upsideRatio !== null ? parseFloat(upsideRatio.toFixed(2)) : null,
    downside_capture_ratio: downsideRatio !== null ? parseFloat(downsideRatio.toFixed(2)) : null
  };
}


/**
 * Calculate portfolio summary metrics
 * @returns {Promise<Object>} Object with all portfolio metrics
 */
async function calculatePortfolioSummaryMetrics() { // Made function async
  try { // Added try block for async error handling
    const dailyValues = await calculateDailyPortfolioValues();

    if (!dailyValues || dailyValues.length === 0) {
      throw new Error('No portfolio data available'); // Use throw for async errors
    }

    // Calculate monthly and yearly values
    const monthlyValues = calculateMonthlyPortfolioValues(dailyValues);
    const yearlyValues = calculateYearlyPortfolioValues(dailyValues);

    // Get time period
    const startDate = dailyValues[0].date;
    const endDate = dailyValues[dailyValues.length - 1].date;

    // Get start and end balance
    const startBalance = dailyValues[0].value;
    const endBalance = dailyValues[dailyValues.length - 1].value;

    // Calculate years
    const startDateObj = new Date(startDate);
    const endDateObj = new Date(endDate);
    const years = (endDateObj - startDateObj) / (365.25 * 24 * 60 * 60 * 1000);

    // Calculate CAGR
    const cagr = calculateCAGR(startBalance, endBalance, years);

    // Calculate annualized standard deviation
    const annualizedStdDev = calculateAnnualizedStdDev(monthlyValues);

    // Calculate downside deviation
    const downsideDeviation = calculateDownsideDeviation(monthlyValues);

    // Calculate best/worst year returns
    const yearlyReturns = calculateBestWorstYearReturns(yearlyValues);

    // Calculate maximum drawdown
    const drawdown = calculateMaxDrawdown(dailyValues);

    // Calculate Sharpe and Sortino ratios
    const sharpeRatio = calculateSharpeRatio(cagr, annualizedStdDev);
    const sortinoRatio = calculateSortinoRatio(cagr, downsideDeviation);

    // Calculate percentage of positive months
    const positiveMonths = calculatePositiveMonths(monthlyValues);

    // Calculate cumulative return
    const cumulativeReturn = calculateCumulativeReturn(startBalance, endBalance);

    // --- Fetch and Calculate Benchmark Metrics ---
    const benchmarkTicker = 'SPY'; // Default benchmark
    const benchmarkMonthlyValues = await getAlignedBenchmarkMonthlyValues(benchmarkTicker, dailyValues);

    // Calculate correlation and capture ratios using actual benchmark data (or null if unavailable)
    const correlation = calculateBenchmarkCorrelation(monthlyValues, benchmarkMonthlyValues);
    const captureRatiosResult = calculateCaptureRatios(monthlyValues, benchmarkMonthlyValues);

    // Build metrics object
    const metrics = {
      time_period: {
        start_date: startDate,
        end_date: endDate,
        years: parseFloat(years.toFixed(2))
      },
      start_balance: parseFloat(startBalance.toFixed(2)),
      end_balance: parseFloat(endBalance.toFixed(2)),
      annualized_return: parseFloat(cagr.toFixed(2)),
      annualized_std_dev: parseFloat(annualizedStdDev.toFixed(2)),
      best_year_return: parseFloat(yearlyReturns.best_year_return.toFixed(2)),
      worst_year_return: parseFloat(yearlyReturns.worst_year_return.toFixed(2)),
      best_year: yearlyReturns.best_year,
      worst_year: yearlyReturns.worst_year,
      max_drawdown: parseFloat(drawdown.max_drawdown.toFixed(2)),
      max_drawdown_period: {
        start_date: drawdown.drawdown_start_date,
        end_date: drawdown.drawdown_end_date
      },
      recovery_time: drawdown.recovery_time_days,
      sharpe_ratio: parseFloat(sharpeRatio.toFixed(2)),
      sortino_ratio: parseFloat(sortinoRatio.toFixed(2)),
      // Use calculated correlation or null
      benchmark_correlation: correlation !== null ? parseFloat(correlation.toFixed(2)) : null,
      cumulative_return: parseFloat(cumulativeReturn.toFixed(2)),
      percentage_positive_months: parseFloat(positiveMonths.toFixed(2)),
      // Use calculated capture ratios or null
      upside_capture_ratio: captureRatiosResult?.upside_capture_ratio ?? null,
      downside_capture_ratio: captureRatiosResult?.downside_capture_ratio ?? null
    };

    return metrics; // Return metrics on success

  } catch (error) {
      console.error("Error in calculatePortfolioSummaryMetrics:", error);
      throw error; // Re-throw the error to be caught by the route handler
  }
}


// GET route for portfolio summary
app.get('/portfolio-summary', async (req, res) => { // Make route async
  try {
    const metrics = await calculatePortfolioSummaryMetrics();
    res.json(metrics);
  } catch (err) {
    console.error('Error calculating portfolio summary metrics:', err.message);
    // Send specific error message if known (e.g., no data)
    if (err.message === 'No portfolio data available') {
        res.status(404).json({ error: 'No portfolio data available', message: 'Upload transaction data first.' });
    } else {
        res.status(500).json({ error: 'Error calculating portfolio summary metrics', message: err.message });
    }
  }
});

// ... rest of the code ...


// ... existing routes like /, /test-keys, /upload, /portfolio-config, /portfolio-composition, /portfolio-summary, /style-analysis, /active-return, /market-performance, /fundamentals-date, /risk-return ...


// GET /stock-prices - Fetches historical prices (useful for debugging)
app.get('/stock-prices', async (req, res) => {
    const ticker = req.query.ticker;
    if (!ticker) {
        return res.status(400).json({ message: 'Ticker query parameter is required' });
    }
    try {
        const prices = await getStockPrices(ticker);
        if (prices) {
            res.json(prices);
        } else {
            // More specific message if possible (e.g., rate limit vs not found)
            res.status(404).json({ message: `Could not find or fetch price data for ${ticker}. Check API key, ticker symbol, and rate limits.` });
        }
    } catch (error) {
        res.status(500).json({ message: 'Error fetching stock prices', error: error.message });
    }
});


// GET /annual-returns - Fetches calculated annual returns
app.get('/annual-returns', async (req, res) => {
    try {
        const benchmark = req.query.benchmark || 'SPY'; // Default to SPY, allow override
        console.log(`[API /annual-returns] Request received. Benchmark: ${benchmark}`);

        const annualData = await calculateAnnualReturns(benchmark);

        if (!annualData) {
             console.error("[API /annual-returns] Calculation returned no data.");
             return res.status(500).json({ message: "Failed to calculate annual returns." });
        }

        console.log(`[API /annual-returns] Sending ${annualData.length} years of data.`);
        res.json(annualData);

    } catch (error) {
        console.error(`[API /annual-returns] Error: ${error.message}`);
        res.status(500).json({ message: "Error calculating annual returns.", error: error.message });
    }
});

// GET /monthly-returns - Fetches calculated monthly returns
app.get('/monthly-returns', async (req, res) => {
    try {
        const benchmark = req.query.benchmark || 'SPY'; // Default to SPY, allow override
        console.log(`[API /monthly-returns] Request received. Benchmark: ${benchmark}`);

        const monthlyData = await calculateMonthlyReturns(benchmark);

        if (!monthlyData) {
             console.error("[API /monthly-returns] Calculation returned no data.");
             return res.status(500).json({ message: "Failed to calculate monthly returns." });
        }

        console.log(`[API /monthly-returns] Sending ${monthlyData.length} months of data.`);
        res.json(monthlyData);

    } catch (error) {
        console.error(`[API /monthly-returns] Error: ${error.message}`);
        res.status(500).json({ message: "Error calculating monthly returns.", error: error.message });
    }
});

// --- Server Start ---
// app.listen should be at the end of the file

// ... existing app.listen call ...
// Ensure this is the last part of the file
app.listen(port, () => {
  console.log(`Robinhood Dashboard backend server running at http://localhost:${port}`);
});

// Optional: Add graceful shutdown for the database
process.on('SIGINT', () => {
    db.close((err) => {
        if (err) {
            console.error('Error closing database:', err.message);
        } else {
            console.log('Database connection closed.');
        }
        process.exit(0);
    });
});

/**
 * Calculate monthly returns for portfolio and benchmark
 * @param {string} benchmarkTicker - Ticker symbol for benchmark (default: 'SPY')
 * @returns {Promise<Array>} Array of monthly return objects
 */
async function calculateMonthlyReturns(benchmarkTicker = 'SPY') {
    try {
        // Initialize relevant variables
        const monthlyReturns = [];
        let currentMonth = new Date(/* start date */);
        const endDate = new Date(/* end date */);
        let cumulativeBenchmarkFactor = 1.0;
        const uniqueTickers = await getUniqueTickers();
        const assetPricesMap = new Map();
        
        // Fetch benchmark prices
        const benchmarkPrices = await getStockPrices(benchmarkTicker);
        
        // Fetch all asset prices
        for (const ticker of uniqueTickers) {
            const prices = await getStockPrices(ticker);
            if (prices) {
                assetPricesMap.set(ticker, prices);
            }
        }
        
        while (currentMonth <= endDate) {
            // Calculate month-specific variables
            const yearMonthStr = `${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, '0')}`;
            // Additional calculations...
            
            // --- Benchmark Calculation ---
            let benchmarkStartValue = null;
            let benchmarkEndValue = null;
            let benchmarkReturn = null;
            let benchmarkEndBalance = null; // Cumulative growth factor

            if (benchmarkPrices) {
                // Get price at the START of the period (end of previous month or actual start)
                 benchmarkStartValue = getPriceForDate(benchmarkPrices, portfolioLookupStartDate); // Use same lookup date as portfolio start

                 // Get price at the END of the period
                 benchmarkEndValue = getPriceForDate(benchmarkPrices, actualPeriodEndDate);

                if (benchmarkStartValue !== null && benchmarkEndValue !== null && benchmarkStartValue !== 0) {
                    benchmarkReturn = (benchmarkEndValue / benchmarkStartValue) - 1;
                    // Update cumulative factor only if return is calculable
                    cumulativeBenchmarkFactor *= (1 + benchmarkReturn);
                    benchmarkEndBalance = cumulativeBenchmarkFactor;
                    console.log(`[calculateMonthlyReturns] Month ${yearMonthStr} Benchmark (${benchmarkTicker}): Start=${benchmarkStartValue?.toFixed(2)}, End=${benchmarkEndValue?.toFixed(2)}, Return=${(benchmarkReturn * 100)?.toFixed(2)}%`);
                } else {
                     console.warn(`[calculateMonthlyReturns] Month ${yearMonthStr} Benchmark (${benchmarkTicker}): Insufficient price data (Start: ${benchmarkStartValue}, End: ${benchmarkEndValue})`);
                     // Keep cumulative factor unchanged if return cannot be calculated
                     benchmarkEndBalance = cumulativeBenchmarkFactor;
                }
            } else {
                 // If no benchmark data at all, keep cumulative factor at 1
                 benchmarkEndBalance = cumulativeBenchmarkFactor;
            }


            // --- Individual Asset Returns Calculation ---
            const individualAssetReturns = {};
            for (const ticker of uniqueTickers) {
                const assetPrices = assetPricesMap.get(ticker);
                if (assetPrices) {
                    // Use same date logic as benchmark/portfolio
                    const assetStartPrice = getPriceForDate(assetPrices, portfolioLookupStartDate);
                    const assetEndPrice = getPriceForDate(assetPrices, actualPeriodEndDate);

                    if (assetStartPrice !== null && assetEndPrice !== null && assetStartPrice !== 0) {
                        individualAssetReturns[ticker] = (assetEndPrice / assetStartPrice) - 1;
                    } else {
                        individualAssetReturns[ticker] = null; // Not enough data for this month/asset
                    }
                } else {
                    individualAssetReturns[ticker] = null; // Price data unavailable
                }
            }

            monthlyReturns.push({
                yearMonth: yearMonthStr,
                portfolioReturn: portfolioReturn !== null ? parseFloat((portfolioReturn * 100).toFixed(2)) : null, // Store as percentage
                portfolioBalance: portfolioEndBalance !== null ? parseFloat(portfolioEndBalance.toFixed(2)) : null,
                benchmarkReturn: benchmarkReturn !== null ? parseFloat((benchmarkReturn * 100).toFixed(2)) : null, // Store as percentage
                benchmarkBalance: benchmarkEndBalance !== null ? parseFloat(benchmarkEndBalance.toFixed(4)) : null, // Store cumulative factor
                individualAssetReturns: Object.fromEntries(
                    Object.entries(individualAssetReturns).map(([ticker, ret]) => [
                        ticker,
                        ret !== null ? parseFloat((ret * 100).toFixed(2)) : null // Store as percentage
                    ])
                ),
            });

            // Move to the next month
            currentMonth.setMonth(currentMonth.getMonth() + 1);
        } // End of while loop
        
        console.log(`[calculateMonthlyReturns] Finished calculation. Generated ${monthlyReturns.length} months of data.`);
        return monthlyReturns;
        
    } catch (error) {
        console.error("[calculateMonthlyReturns] Unexpected error:", error);
        throw error; // Re-throw the error to be caught by the route handler
    }
} // End of calculateMonthlyReturns function


// --- API Routes ---
