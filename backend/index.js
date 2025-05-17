// --- Step 1: Load Dependencies ---
require('dotenv').config(); // Loads environment variables from a .env file (like API keys) into process.env
const express = require('express'); // Imports the Express framework for building web servers
const multer = require('multer'); // Imports Multer, used for handling file uploads (like the CSV)
const Papa = require('papaparse'); // Imports PapaParse, used for parsing CSV data
const sqlite3 = require('sqlite3').verbose(); // Imports SQLite3 for database operations (with extra debugging info)
const fs = require('fs'); // Imports the built-in Node.js File System module for reading/writing files
const path = require('path'); // Imports the built-in Node.js Path module for working with file paths
const { formatDateForDatabase, toYYYYMMDD } = require('./date-utils'); // Imports custom date formatting functions
const { performance } = require('perf_hooks'); // For timing

// --- Step 2: Initialize Express App ---
const app = express(); // Creates an instance of the Express application
const port = 3002; // Defines the port number the server will listen on (e.g., http://localhost:3002)

// --- Step 3: Configure Middleware ---
app.use(express.json()); // Allows the server to parse incoming request bodies as JSON
app.use(express.urlencoded({ extended: true })); // Allows URL-encoded payloads

// Setup CORS
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*'); // Allow any origin (restrict in production)
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  next();
});

// Configure multer for file uploads
const upload = multer({ dest: 'uploads/' }); // Store temporary files in uploads/

// --- Step 4: Setup SQLite Database ---
const dbPath = path.join(__dirname, 'robinhood.db'); // Database file path
console.log(`Using database at: ${dbPath}`);

// Create a database connection instance
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('Error opening database:', err.message);
  } else {
    console.log('Connected to the SQLite database.');

    // Create 'transactions' Table (if needed)
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
        console.log('Transactions table confirmed or created.');
      }
    });

    // Create 'stock_prices' Table (if needed) for caching
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
        console.log('Stock prices table is ready.');
      }
    });
  }
});

// --- Step 5: Define API Routes (Endpoints) ---

// --- Route: GET / ---
app.get('/', (req, res) => {
  res.send('Robinhood Dashboard Backend - Running');
});

// --- Route: GET /test-keys ---
app.get('/test-keys', (req, res) => {
  res.json({
    alphaVantageKey: process.env.ALPHA_VANTAGE_KEY ? 'Loaded' : 'Missing',
    finnhubKey: process.env.FINNHUB_KEY ? 'Loaded' : 'Missing'
  });
});

// --- Route: POST /upload ---
// Handles uploading the transaction CSV file, parsing it, and storing in the DB.
app.post('/upload', upload.single('file'), (req, res) => {
  console.log('[API /upload] Request received.');
  if (!req.file) {
    console.log('[API /upload] No file uploaded.');
    return res.status(400).json({ error: 'No file uploaded' });
  }
  console.log(`[API /upload] File uploaded: ${req.file.originalname}, Temp path: ${req.file.path}`);
  const filePath = req.file.path;

  fs.readFile(filePath, 'utf8', (err, data) => {
    if (err) {
      console.error('[API /upload] Error reading uploaded file:', err);
      fs.unlink(filePath, (unlinkErr) => { /* handle unlink error */ });
      return res.status(500).json({ error: 'Error reading file' });
    }
    console.log('[API /upload] File read successfully.');

    Papa.parse(data, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        console.log(`[API /upload] CSV parsing complete. Found ${results.data.length} rows.`);
        const transactions = results.data;

        const requiredHeaders = ['Activity Date', 'Instrument', 'Trans Code', 'Quantity', 'Price', 'Amount'];
        const csvHeaders = results.meta && results.meta.fields ? results.meta.fields : Object.keys(transactions[0] || {});
        const missingHeaders = requiredHeaders.filter(h => !csvHeaders.includes(h));
        if (missingHeaders.length > 0) {
          console.error(`[API /upload] Missing required CSV headers: ${missingHeaders.join(', ')}`);
          fs.unlink(filePath, (unlinkErr) => { /* handle unlink error */ });
          return res.status(400).json({ error: `Missing required CSV headers: ${missingHeaders.join(', ')}` });
        }

        console.log('[API /upload] First 2 parsed transactions:', transactions.slice(0, 2));

        if (!transactions || transactions.length === 0) {
          console.log('[API /upload] No transactions found in the parsed CSV.');
          fs.unlink(filePath, (unlinkErr) => { /* handle unlink error */ });
          return res.status(400).json({ error: 'No transactions found in file' });
        }

        db.run('DELETE FROM transactions', (deleteErr) => {
          if (deleteErr) {
            console.error(`[API /upload] Error clearing existing transactions: ${deleteErr.message}`);
            fs.unlink(filePath, (unlinkErr) => { /* handle unlink error */ });
            return res.status(500).json({ error: 'Error preparing database' });
          }
          console.log(`[API /upload] Successfully cleared existing transactions.`);

          const insertStmt = db.prepare(`
            INSERT INTO transactions (
              activity_date, ticker, trans_code, quantity, price, amount
            ) VALUES (?, ?, ?, ?, ?, ?)
          `);

          let insertedCount = 0;
          let errorCount = 0;
          console.log(`[API /upload] Processing ${transactions.length} transactions for insertion...`);

          transactions.forEach((transaction, index) => {
            try {
              let activityDateRaw = transaction['Activity Date'] || '';
              let activityDate = formatDateForDatabase(activityDateRaw);
              const ticker = transaction['Instrument'] || '';
              const transCode = transaction['Trans Code'] || '';
              let quantity = 0;
              if (transaction['Quantity'] && transaction['Quantity'].trim() !== '') {
                quantity = parseFloat(transaction['Quantity'].replace(/,/g, ''));
                if (isNaN(quantity)) quantity = 0;
              }
              let price = 0;
              if (transaction['Price'] && transaction['Price'].trim() !== '') {
                price = parseFloat(transaction['Price'].replace(/[$,()]/g, ''));
                if (isNaN(price)) price = 0;
              }
              let amount = 0;
              if (transaction['Amount'] && transaction['Amount'].trim() !== '') {
                const amountStr = transaction['Amount'].replace(/[$,]/g, '');
                if (amountStr.includes('(') && amountStr.includes(')')) {
                  amount = -parseFloat(amountStr.replace(/[()]/g, ''));
                } else {
                  amount = parseFloat(amountStr);
                }
                if (isNaN(amount)) amount = 0;
              }

              insertStmt.run(
                activityDate, ticker, transCode, quantity, price, amount,
                (runErr) => {
                  if (runErr) {
                    console.error(`[API /upload] Error inserting transaction row ${index + 1}: ${runErr.message}, Data: ${JSON.stringify(transaction)}`);
                    errorCount++;
                  } else {
                    insertedCount++;
                  }
                }
              );
            } catch (processError) {
              console.error(`[API /upload] Error processing transaction row ${index + 1}:`, transaction, processError.message);
              errorCount++;
            }
          });

          insertStmt.finalize((finalizeErr) => {
             if (finalizeErr) {
               console.error(`[API /upload] Error finalizing insert statement: ${finalizeErr.message}`);
             } else {
               console.log(`[API /upload] Insert statement finalized successfully. Inserted: ${insertedCount}, Errors: ${errorCount}`);
             }

             fs.unlink(filePath, (unlinkErr) => {
                if (unlinkErr) console.error(`[API /upload] Error deleting temp file: ${unlinkErr.message}`);
                else console.log(`[API /upload] Temp file deleted: ${filePath}`);
             });

             console.log(`[API /upload] CSV Upload Complete: ${insertedCount} inserted, ${errorCount} errors.`);
             res.json({
                message: 'File uploaded and processed successfully.',
                totalTransactions: transactions.length,
                insertedCount,
                errorCount
             });
          }); // End finalize
        }); // End delete callback
      }, // End complete callback
      error: (parseError) => {
        console.error('[API /upload] Error parsing CSV:', parseError);
        fs.unlink(filePath, (unlinkErr) => { /* handle unlink error */ });
        res.status(500).json({ error: 'Error parsing CSV file', details: parseError.message });
      }
    }); // End Papa.parse
  }); // End fs.readFile
}); // End POST /upload

// --- Route: GET /portfolio-composition (Refactored) ---
// Calculates current holdings based on the transactions table and fetches current prices.

// Helper function to calculate current holdings from transactions
async function calculateCurrentHoldings() {
    console.log('[calculateCurrentHoldings] Calculating current holdings from transactions...');
    return new Promise((resolve, reject) => {
        // Query to aggregate buys and sells for each ticker
        const query = `
            SELECT
                ticker,
                SUM(CASE WHEN trans_code = 'Buy' THEN quantity ELSE 0 END) as total_bought,
                SUM(CASE WHEN trans_code = 'Sell' THEN quantity ELSE 0 END) as total_sold
            FROM transactions
            WHERE ticker IS NOT NULL AND quantity IS NOT NULL AND trans_code IN ('Buy', 'Sell')
            GROUP BY ticker;
        `;

        db.all(query, [], (err, rows) => {
            if (err) {
                console.error('[calculateCurrentHoldings] DB error fetching and aggregating transactions:', err.message);
                reject(new Error('Failed to calculate holdings from database.'));
            } else {
                const holdings = {};
                rows.forEach(row => {
                    const currentQuantity = row.total_bought - row.total_sold;
                    // Only include if holding quantity is significant (handles potential floating point dust)
                    if (Math.abs(currentQuantity) > 0.000001) {
                         holdings[row.ticker] = currentQuantity;
                    }
                });
                console.log(`[calculateCurrentHoldings] Calculated holdings for ${Object.keys(holdings).length} tickers.`);
                resolve(holdings);
            }
        });
    });
}

app.get('/portfolio-composition', checkTransactionsExist, async (req, res) => {
    console.log('[API /portfolio-composition] Request received.');
    const startTime = performance.now(); // Start timing

    try {
        const holdings = await calculateCurrentHoldings();
        console.log(`[API /portfolio-composition] Calculated ${Object.keys(holdings).length} current holdings.`);

        if (Object.keys(holdings).length === 0) {
            console.log('[API /portfolio-composition] No holdings found. Returning empty composition.');
            return res.json({ composition: [], totalValue: 0 });
        }

        // --- Fetch latest prices for all holdings ---
        const uniqueTickers = Object.keys(holdings);
        const pricePromises = uniqueTickers.map(ticker =>
            getStockPrices(ticker).catch(error => {
                // Log specific errors for price fetching but don't stop the whole composition
                console.error(`[API /portfolio-composition] Price fetch/cache check FAILED for ${ticker}: ${error.message}`);
                return null; // Indicate failure for this ticker
            })
        );

        // Wait for all price checks/fetches to attempt completion
        await Promise.allSettled(pricePromises);
        console.log('[API /portfolio-composition] All price fetch/cache checks attempted.');

        // --- Get latest available price (cached or newly fetched) for each ticker ---
        let composition = [];
        let totalPortfolioValue = 0;
        const latestPricePromises = uniqueTickers.map(async (ticker) => {
             // Retrieve the latest price from the database (might be stale if API failed)
            const priceRow = await new Promise((resolve, reject) => {
                db.get("SELECT close_price FROM stock_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1", [ticker], (err, row) => {
                    if (err) reject(err);
                    else resolve(row);
                });
            });

            if (priceRow && priceRow.close_price > 0) {
                 const latestPrice = priceRow.close_price;
                 const quantity = holdings[ticker];
                 const value = quantity * latestPrice;
                 totalPortfolioValue += value; // Add to total value
                 console.log(`[API /portfolio-composition] Latest price found for ${ticker}: ${latestPrice}`);
                 // Return data for composition array construction later
                 return { ticker, quantity, latestPrice, value };
            } else {
                 console.warn(`[API /portfolio-composition] Could not find valid latest price for ${ticker} in DB after fetch attempt. Excluding from composition.`);
                 return null; // Indicate price unavailable
            }
        });

        const priceResults = await Promise.allSettled(latestPricePromises);
        console.log('[API /portfolio-composition] All price fetch/DB queries finished.');

        // Construct composition array from successful price lookups
        priceResults.forEach(result => {
            if (result.status === 'fulfilled' && result.value) {
                 composition.push({
                     ticker: result.value.ticker,
                     quantity: result.value.quantity,
                     currentPrice: parseFloat(result.value.latestPrice.toFixed(2)),
                     marketValue: parseFloat(result.value.value.toFixed(2))
                 });
            } else if (result.status === 'rejected') {
                 console.error(`[API /portfolio-composition] Error retrieving price result from DB for a ticker: ${result.reason}`);
            }
             // Ignore null fulfilled results (where price wasn't found)
        });

        // Calculate weights AFTER total value is known
        composition = composition.map(item => ({
            ...item,
            weight: totalPortfolioValue > 0 ? parseFloat(((item.marketValue / totalPortfolioValue) * 100).toFixed(2)) : 0
        }));

        // Sort by market value descending
        composition.sort((a, b) => b.marketValue - a.marketValue);

        const endTime = performance.now();
        console.log(`[API /portfolio-composition] Calculated final total portfolio value: ${totalPortfolioValue}`);
        console.log(`[API /portfolio-composition] Sending final composition response. Took ${((endTime - startTime) / 1000).toFixed(2)}s.`);
        res.json({
            composition: composition,
            totalValue: parseFloat(totalPortfolioValue.toFixed(2))
        });

    } catch (error) {
        console.error('[API /portfolio-composition] Error calculating portfolio composition:', error);
        console.error('[API /portfolio-composition] Error stack:', error.stack); // Log stack trace
        res.status(500).json({ error: 'Failed to calculate portfolio composition.', details: error.message });
    }
});

// --- Helper Function: Check if Transactions Exist ---
// Used by analytics endpoints before attempting calculations.
function checkTransactionsExist(req, res, next) {
  db.get('SELECT COUNT(*) as count FROM transactions', [], (err, row) => {
    if (err) {
      console.error('[DB Check] Error checking transactions:', err);
      return res.status(500).json({ error: 'Error checking transaction data.' });
    }
    if (row.count === 0) {
      console.log('[DB Check] No transactions found in DB.');
      return res.status(404).json({ error: 'No transactions found. Please upload transaction data first.' });
    }
    // Store count for potential use in the next handler
    req.transactionCount = row.count;
    console.log(`[DB Check] Found ${row.count} transactions in DB.`);
    next(); // Proceed to the actual endpoint logic
  });
}


// --- Analytics Endpoints (Refactored - Return 501 for now) ---

app.get('/portfolio-growth', checkTransactionsExist, async (req, res) => {
  const benchmarkTicker = req.query.benchmark || 'SPY';
  console.log(`[API /portfolio-growth] Request received. Benchmark: ${benchmarkTicker}. Transactions: ${req.transactionCount}`);
  try {
    const { dateValues, uniqueSortedPriceDates } = await calculateMonthlyPortfolioValues(benchmarkTicker); // RENAMED

    if (Object.keys(dateValues).length === 0) {
      console.log('[API /portfolio-growth] No daily values calculated, returning empty array.');
      return res.json([]); // Return empty array as expected by frontend potentially
    }

    console.log('[API /portfolio-growth] Formatting daily values for chart...');
    
    const growthData = [];
    let initialPortfolioValue = null;
    let initialBenchmarkValue = null;
    let firstValidDateStr = null; // Track the first date for filtering later
    let normalizationPossible = false;
    let normalizationFactor = 1; // Default to 1 (no normalization)

    // Find the first date with a non-null, positive portfolio value
    for (const dateStr of uniqueSortedPriceDates) {
        const dayData = dateValues[dateStr];
        // Check dayData exists, portfolioValue is not null, and portfolioValue is positive
        if (dayData && dayData.portfolioValue !== null && dayData.portfolioValue > 0) {
            firstValidDateStr = dateStr;
            initialPortfolioValue = dayData.portfolioValue;
            // Also check if the benchmark exists and is non-zero for this date
            // Use optional chaining for benchmarkPrice access as dayData is confirmed to exist here
            if (dayData.benchmarkPrice !== null && dayData.benchmarkPrice !== 0) {
                initialBenchmarkValue = dayData.benchmarkPrice;
                normalizationPossible = true;
                normalizationFactor = initialPortfolioValue / initialBenchmarkValue;
                console.log(`[API /portfolio-growth] Normalization possible. Factor: ${normalizationFactor} (Initial Port: ${initialPortfolioValue}, Initial Bench: ${initialBenchmarkValue} on ${firstValidDateStr})`);
            } else {
                 // Use optional chaining here too for safety when logging
                console.warn(`[API /portfolio-growth] Initial portfolio value found on ${firstValidDateStr}, but benchmark value is missing or zero (${dayData?.benchmarkPrice}). Normalization disabled.`);
            }
            break; // Found the first relevant date, stop searching
        }
    }

    if (firstValidDateStr === null) {
         console.warn(`[API /portfolio-growth] No dates with a positive portfolio value found. Attempting to return zero values.`);
         // Instead of returning [], create zero-value entries for the chart
         const zeroGrowthData = uniqueSortedPriceDates.map(dateStr => ({
             date: dateStr,
             portfolioValue: 0,
             benchmarkValue: 0 // Or fetch raw benchmark if desired, though it might also be 0/null
         }));
         console.log(`[API /portfolio-growth] Sending ${zeroGrowthData.length} zero-value data points.`);
         return res.json(zeroGrowthData);
    }

    if (!normalizationPossible) {
         console.warn(`[API /portfolio-growth] Normalization not possible. Sending raw benchmark data.`);
    }

    // Iterate starting from the first valid date
    const startIndex = uniqueSortedPriceDates.indexOf(firstValidDateStr);
    if (startIndex === -1) {
        console.error(`[API /portfolio-growth] Internal error: firstValidDateStr ${firstValidDateStr} not found in uniqueSortedPriceDates.`);
        // Return zero values here too as a fallback
        const zeroGrowthData = uniqueSortedPriceDates.map(dateStr => ({
            date: dateStr,
            portfolioValue: 0,
            benchmarkValue: 0 
        }));
        return res.json(zeroGrowthData);
    }

    for (let i = startIndex; i < uniqueSortedPriceDates.length; i++) {
        const dateStr = uniqueSortedPriceDates[i];
        const dayData = dateValues[dateStr];

        // Portfolio value should ideally exist from startIndex onwards, but double-check
        // Ensure dayData exists before trying to access portfolioValue
        if (dayData && dayData.portfolioValue !== null) {
            const portfolioValue = parseFloat(dayData.portfolioValue.toFixed(2));
            let benchmarkValue = null;

            // Calculate benchmark value: apply normalization if possible, else use raw value
            // Check benchmarkPrice exists on dayData
            if (dayData.benchmarkPrice !== null) {
                if (normalizationPossible) {
                    benchmarkValue = parseFloat((dayData.benchmarkPrice * normalizationFactor).toFixed(2));
                } else {
                    // Send raw benchmark value if normalization wasn't possible
                    benchmarkValue = parseFloat(dayData.benchmarkPrice.toFixed(2));
                }
            } // benchmarkValue remains null if dayData.benchmarkPrice is null

            growthData.push({
                date: dateStr,
                portfolioValue: portfolioValue,
                benchmarkValue: benchmarkValue
            });
        } else {
            // This case might indicate data gaps after the first valid date, log it.
            console.warn(`[API /portfolio-growth] Missing portfolio value for date ${dateStr} after initial value was found. Skipping this date.`);
        }
    }

    console.log(`[API /portfolio-growth] Sending ${growthData.length} data points.`);
    res.json(growthData);

  } catch (error) {
      console.error('[API /portfolio-growth] General error:', error);
      console.error('[API /portfolio-growth] Error Stack Trace:', error.stack);
      res.status(500).json({ error: 'Failed to calculate portfolio growth.', details: error.message });
  }
}); // <<< Add this closing brace and parenthesis

// Refactored helper function to calculate MONTHLY portfolio values
async function calculateMonthlyPortfolioValues(benchmarkTicker = 'SPY') {
  console.log(`[calculateMonthlyPortfolioValues] Starting calculation with benchmark: ${benchmarkTicker}`);

  // Step 1: Get all transactions (no change)
  let transactions = await new Promise((resolve, reject) => { // Changed to let
    db.all("SELECT activity_date, ticker, trans_code, quantity, price, amount FROM transactions ORDER BY activity_date ASC", [], (err, rows) => {
      if (err) {
        console.error('[calculateMonthlyPortfolioValues] DB error fetching transactions:', err.message);
        reject(new Error('Failed to fetch transactions.'));
      } else {
        resolve(rows);
      }
    });
  });

  // --- ADDED: Filter out transactions with invalid dates --- 
  const originalCount = transactions.length;
  transactions = transactions.filter(t => {
      if (!t.activity_date) return false;
      const date = new Date(t.activity_date + 'T00:00:00Z'); // Ensure consistent parsing check
      return !isNaN(date.getTime());
  });
  const filteredCount = transactions.length;
  if (originalCount > filteredCount) {
      console.warn(`[calculateMonthlyPortfolioValues] Filtered out ${originalCount - filteredCount} transactions due to invalid activity_date.`);
  }
  // --- END ADDED FILTER ---

  if (transactions.length === 0) {
    console.log('[calculateMonthlyPortfolioValues] No valid transactions found after filtering. Returning empty data.'); // Updated log
    return { dateValues: {}, uniqueSortedPriceDates: [] };
  }

  // Step 2: Determine date range and required tickers
  // Remove previous validDates check as we filter upfront now
  /* 
  const validDates = transactions
    .map(t => new Date(t.activity_date))
    .filter(d => !isNaN(d.getTime()));
  
  if (validDates.length === 0) {
    throw new Error('No valid transaction dates found in the data.');
  }
  
  const minDate = new Date(Math.min(...validDates));
  const maxDate = new Date(Math.max(...validDates));

  if (isNaN(minDate.getTime()) || isNaN(maxDate.getTime())) {
    throw new Error('Could not determine a valid date range from transactions.');
  }
  */

  const portfolioTickers = [...new Set(transactions.filter(t => t.ticker).map(t => t.ticker))];
  const allTickers = [...new Set([...portfolioTickers, benchmarkTicker])];

  // Use the dates from the *filtered* transactions array
  const firstTxDate = new Date(transactions[0].activity_date + 'T00:00:00Z'); 
  const lastTxDate = new Date(transactions[transactions.length - 1].activity_date + 'T00:00:00Z');

  // Validation (now less likely to fail, but keep for safety and logging)
  if (isNaN(firstTxDate.getTime())) {
      // Log the raw value directly for better debugging
      const rawDate = transactions[0]?.activity_date;
      console.error(`[calculateMonthlyPortfolioValues] Invalid first transaction date after filtering. Value: '${rawDate}'`);
      throw new Error(`Invalid date found in first transaction after filtering. Value: '${rawDate}'`);
  }
  if (isNaN(lastTxDate.getTime())) {
      const rawDate = transactions[transactions.length - 1]?.activity_date;
      console.error(`[calculateMonthlyPortfolioValues] Invalid last transaction date after filtering. Value: '${rawDate}'`);
      throw new Error(`Invalid date found in last transaction after filtering. Value: '${rawDate}'`);
  }

  // Use firstTxDate and lastTxDate directly for logging
  console.log(`[calculateMonthlyPortfolioValues] Date range from valid transactions: ${firstTxDate.toISOString().split('T')[0]} to ${lastTxDate.toISOString().split('T')[0]}`); 
  console.log(`[calculateMonthlyPortfolioValues] Required tickers: ${allTickers.join(', ')}`);

  // Step 3: Ensure stock prices are cached (no change)
  console.log('[calculateMonthlyPortfolioValues] Ensuring stock prices are cached...');
  try {
    const priceFetchResults = await Promise.allSettled(allTickers.map(ticker => getStockPrices(ticker)));
    console.log('[calculateMonthlyPortfolioValues] Stock price caching/fetching attempts complete.');

    const failedTickers = priceFetchResults
      .map((result, index) => ({ result, ticker: allTickers[index] }))
      .filter(item => item.result.status === 'rejected');

    if (failedTickers.length > 0) {
      console.warn(`[calculateMonthlyPortfolioValues] Failed to fetch/cache prices for ${failedTickers.length} tickers:`);
      failedTickers.forEach(item => {
        console.warn(`  - ${item.ticker}: ${item.result.reason?.message || item.result.reason}`);
      });
    }

  } catch (priceError) {
    console.error('[calculateMonthlyPortfolioValues] Unexpected error during price fetching stage:', priceError.message);
    throw new Error(`Unexpected error during price fetching: ${priceError.message}`);
  }

  // Step 4: Fetch all necessary prices from DB cache (no change)
  console.log('[calculateMonthlyPortfolioValues] Fetching cached prices from DB...');
  const prices = await new Promise((resolve, reject) => {
    const query = `SELECT ticker, date, close_price FROM stock_prices WHERE ticker IN (${allTickers.map(() => '?').join(',')})`;
    db.all(query, allTickers, (err, rows) => {
      if (err) {
        console.error('[calculateMonthlyPortfolioValues] DB error fetching cached prices:', err.message);
        reject(new Error('Failed to fetch cached stock prices.'));
      } else {
        const priceMap = {};
        rows.forEach(row => {
          if (!priceMap[row.ticker]) {
            priceMap[row.ticker] = {};
          }
          priceMap[row.ticker][row.date.split('T')[0]] = row.close_price;
        });
        resolve(priceMap);
      }
    });
  });
  console.log('[calculateMonthlyPortfolioValues] Cached prices fetched.');
  console.log(`[calculateMonthlyPortfolioValues] Price map structure: ${Object.keys(prices).length} tickers`);

  // --- Step 5: Calculate END-OF-MONTH portfolio values --- 
  console.log('[calculateMonthlyPortfolioValues] Calculating end-of-month values...');
  const dateValues = {}; // Store results keyed by YYYY-MM-DD (last day of month)
  let currentHoldings = {};
  let currentCash = 0;
  let transactionIndex = 0;

  // Use today's date if it's later than the last transaction
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0); // Normalize to UTC midnight
  // Correctly determine the final date as the maximum of last transaction or today
  const finalDate = new Date(Math.max(lastTxDate.getTime(), today.getTime())); 

  // Log the calculated dates for verification
  console.log(`[calculateMonthlyPortfolioValues] Date Range Check: First Tx=${firstTxDate.toISOString().split('T')[0]}, Last Tx=${lastTxDate.toISOString().split('T')[0]}, Today=${today.toISOString().split('T')[0]}, Final Date=${finalDate.toISOString().split('T')[0]}`);

  const startYear = firstTxDate.getUTCFullYear();
  const startMonth = firstTxDate.getUTCMonth(); // 0-11
  const endYear = finalDate.getUTCFullYear();
  const endMonth = finalDate.getUTCMonth(); // 0-11

  let monthlyDates = []; // Store the YYYY-MM-DD dates we calculate for

  for (let year = startYear; year <= endYear; year++) {
      const monthStart = (year === startYear) ? startMonth : 0;
      const monthEnd = (year === endYear) ? endMonth : 11;

      for (let month = monthStart; month <= monthEnd; month++) {
          // Get the last day of the current month (handles leap years)
          const lastDayOfMonth = new Date(Date.UTC(year, month + 1, 0)); // Day 0 of next month = last day of current month
          const dateStr = lastDayOfMonth.toISOString().split('T')[0]; // YYYY-MM-DD

          // --- Process Transactions UP TO this month-end date --- 
          while (transactionIndex < transactions.length && new Date(transactions[transactionIndex].activity_date + 'T00:00:00Z') <= lastDayOfMonth) {
              const t = transactions[transactionIndex];
              // (Transaction processing logic - identical to daily version)
              const qty = parseFloat(t.quantity) || 0;
              let amount = 0;
              if (t.amount) {
                  const amountStr = String(t.amount).replace(/[$,]/g, '');
                  if (amountStr.includes('(') && amountStr.includes(')')) {
                      amount = -parseFloat(amountStr.replace(/[()]/g, ''));
                  } else {
                      amount = parseFloat(amountStr);
                  }
                  if (isNaN(amount)) amount = 0;
              }
              const cashEffect = amount;

              if (t.trans_code === 'Buy' && t.ticker && qty > 0) {
                  currentHoldings[t.ticker] = (currentHoldings[t.ticker] || 0) + qty;
                  currentCash += cashEffect;
              } else if (t.trans_code === 'Sell' && t.ticker && qty > 0) {
                  currentHoldings[t.ticker] = (currentHoldings[t.ticker] || 0) - qty;
                  currentCash += cashEffect;
              } else if (['CDIV', 'CINT', 'RTP', 'MISC'].includes(t.trans_code)) {
                  currentCash += cashEffect;
              } else if ((t.trans_code === 'Buy' || t.trans_code === 'Sell') && !t.ticker) {
                   currentCash += cashEffect;
              }
              if (t.ticker && Math.abs(currentHoldings[t.ticker] || 0) < 0.000001) {
                   delete currentHoldings[t.ticker]; // Clean up zero holdings
              }
              transactionIndex++;
          } // End transaction processing for the month
          
          // --- Calculate Holdings Value at Month End --- 
          let holdingsValue = 0;
          for (const ticker in currentHoldings) {
              if (currentHoldings[ticker] === 0) continue;

              // Find price for ticker ON dateStr (month end date)
              let price = prices[ticker]?.[dateStr];
              
              // If exact month-end price missing, carry forward LAST known price BEFORE or ON dateStr
              if (price === undefined || price === null) {
                  if (prices[ticker]) {
                       const tickerDates = Object.keys(prices[ticker]).sort();
                       let lastKnownPrice = null;
                       // Find the latest date <= dateStr
                       for (let i = tickerDates.length - 1; i >= 0; i--) {
                           if (tickerDates[i] <= dateStr) {
                               lastKnownPrice = prices[ticker][tickerDates[i]];
                               if (lastKnownPrice !== undefined && lastKnownPrice !== null) {
                                    price = lastKnownPrice;
                                    // Optional: Log if we carried forward
                                    // if (tickerDates[i] !== dateStr) { console.log(`[MonthlyCalc] Carried forward price for ${ticker} from ${tickerDates[i]} to ${dateStr}`); }
                                    break; // Found the most recent price
                               }
                           }
                       }
                  }
              }

              if (price !== undefined && price !== null) {
                   holdingsValue += currentHoldings[ticker] * price;
              } else {
                   // Price still missing after carry-forward attempt
                   if (Math.abs(currentHoldings[ticker]) > 0.000001) {
                       console.warn(`[calculateMonthlyPortfolioValues] Missing price for ${ticker} (Qty: ${currentHoldings[ticker]}) on month-end ${dateStr} and no previous price found.`);
                   }
              }
          } // End holdings value calculation

          const totalValue = holdingsValue + currentCash;
          const benchmarkPrice = prices[benchmarkTicker]?.[dateStr] ?? 
              (prices[benchmarkTicker] ? 
                   Object.keys(prices[benchmarkTicker]).sort().reduce((lastPrice, currentPriceDate) => {
                       return currentPriceDate <= dateStr ? prices[benchmarkTicker][currentPriceDate] : lastPrice; // Use <= to get price on the dateStr itself if available
                   }, null) 
                   : null);
          
          // Store the calculated value for the month-end date
          dateValues[dateStr] = {
              portfolioValue: totalValue,
              benchmarkPrice: benchmarkPrice
          };
          monthlyDates.push(dateStr); // Add to our list of calculated dates

          // Log monthly summary (reduced logging)
          console.log(`[calculateMonthlyPortfolioValues] Month End: ${dateStr}, Holdings: ${Object.keys(currentHoldings).length}, Portfolio Value: ${totalValue.toFixed(2)}, Benchmark Price: ${benchmarkPrice?.toFixed(2) ?? 'N/A'}`);
      } // End month loop
  } // End year loop

  console.log(`[calculateMonthlyPortfolioValues] Monthly values calculated for ${monthlyDates.length} dates.`);
  // Return structure remains the same, but content is now monthly - use original key name
  return { dateValues, uniqueSortedPriceDates: monthlyDates.sort() }; 
}

app.get('/annual-returns', checkTransactionsExist, async (req, res) => {
  const benchmarkTicker = req.query.benchmark || 'SPY';
  console.log(`[API /annual-returns] Request received. Benchmark: ${benchmarkTicker}. Transactions: ${req.transactionCount}`);

  try {
    // Call the refactored helper function - UPDATED NAME
    const { dateValues, uniqueSortedPriceDates } = await calculateMonthlyPortfolioValues(benchmarkTicker);

    if (Object.keys(dateValues).length === 0) {
      console.log('[API /annual-returns] No monthly values calculated, returning empty array.'); // Updated log message slightly
      return res.json([]);
    }

    // --- Step 7: Calculate Annual Returns --- 
    console.log('[API /annual-returns] Calculating annual returns from daily values...');
    const annualReturns = [];
    // Determine year range from the sorted dates returned by the helper
    const minYear = parseInt(uniqueSortedPriceDates[0].split('-')[0], 10);
    const maxYear = parseInt(uniqueSortedPriceDates[uniqueSortedPriceDates.length - 1].split('-')[0], 10);
    const yearsInRange = Array.from({ length: maxYear - minYear + 1 }, (_, i) => minYear + i);

    for (const year of yearsInRange) {
        // Find the first and last date with data *within* the year
        const datesInYear = uniqueSortedPriceDates.filter(d => d.startsWith(year + '-'));
        // Need at least two *valid* data points (non-null values) in the year or adjacent years to calculate return

        let startOfYearDate = null;
        let startOfYearValue = null;
        let startOfYearBenchPrice = null;

        // Find end of previous year's value
        const endOfPrevYearDate = uniqueSortedPriceDates.filter(d => parseInt(d.split('-')[0], 10) === year - 1).pop();
        // Check if the date exists AND the corresponding value exists in dateValues
        if (endOfPrevYearDate && dateValues[endOfPrevYearDate]?.portfolioValue !== null) {
            startOfYearDate = endOfPrevYearDate;
            startOfYearValue = dateValues[startOfYearDate].portfolioValue;
            startOfYearBenchPrice = dateValues[startOfYearDate].benchmarkPrice; // Benchmark might still be null here
        } else {
            // If no previous year data, find the *first* valid date of the current year
            for (const date of datesInYear) {
                // Check if the date entry exists AND the portfolio value is not null
                if (dateValues[date] && dateValues[date].portfolioValue !== null) {
                    startOfYearDate = date;
                    startOfYearValue = dateValues[date].portfolioValue;
                    // Also check benchmark price exists on this specific date entry
                    startOfYearBenchPrice = dateValues[date].benchmarkPrice !== null ? dateValues[date].benchmarkPrice : null;
                    break;
                }
            }
        }

        // Find last valid value for the year
        let endOfYearDate = null;
        let endOfYearValue = null;
        let endOfYearBenchPrice = null;
        for (let i = datesInYear.length - 1; i >= 0; i--) {
             const date = datesInYear[i];
             // Check if the date entry exists AND the portfolio value is not null
             if (dateValues[date] && dateValues[date].portfolioValue !== null) {
                endOfYearDate = date;
                endOfYearValue = dateValues[date].portfolioValue;
                // Also check benchmark price exists on this specific date entry
                endOfYearBenchPrice = dateValues[date].benchmarkPrice !== null ? dateValues[date].benchmarkPrice : null;
                break;
             }
        }

        let portfolioReturn = 0;
        let benchmarkReturn = 0;

        // Calculate portfolio return if possible
        // Ensure both start and end values were successfully found
        if (startOfYearValue !== null && endOfYearValue !== null && startOfYearValue !== 0) {
            portfolioReturn = (endOfYearValue / startOfYearValue) - 1;
        } else {
             console.warn(`[API /annual-returns] Could not calculate portfolio return for ${year}. Start: ${startOfYearValue} (${startOfYearDate}), End: ${endOfYearValue} (${endOfYearDate})`);
        }

        // Calculate benchmark return if possible (using the same start/end dates as portfolio)
        // Ensure the dates were found and the benchmark prices exist for those dates
        const actualStartBenchPrice = startOfYearDate ? dateValues[startOfYearDate]?.benchmarkPrice : null;
        const actualEndBenchPrice = endOfYearDate ? dateValues[endOfYearDate]?.benchmarkPrice : null;

        if (actualStartBenchPrice !== null && actualEndBenchPrice !== null && actualStartBenchPrice !== 0) {
            benchmarkReturn = (actualEndBenchPrice / actualStartBenchPrice) - 1;
        } else {
             console.warn(`[API /annual-returns] Could not calculate benchmark return for ${year}. Start Price: ${actualStartBenchPrice} (${startOfYearDate}), End Price: ${actualEndBenchPrice} (${endOfYearDate})`);
        }

        annualReturns.push({
            year: year,
            // Ensure NaN is not returned, default to 0
            portfolioReturn: isNaN(portfolioReturn) ? 0 : parseFloat((portfolioReturn * 100).toFixed(2)),
            benchmarkReturn: isNaN(benchmarkReturn) ? 0 : parseFloat((benchmarkReturn * 100).toFixed(2))
        });
    }

    console.log('[API /annual-returns] Sending response:', annualReturns);
    res.json(annualReturns);

  } catch (error) {
    console.error('[API /annual-returns] General error:', error);
    console.error('[API /annual-returns] Error Stack Trace:', error.stack);
    res.status(500).json({ error: 'Failed to calculate annual returns.', details: error.message });
  }
});

app.get('/monthly-returns', checkTransactionsExist, async (req, res) => {
   const benchmarkTicker = req.query.benchmark || 'SPY';
   console.log(`[API /monthly-returns] Request received. Benchmark: ${benchmarkTicker}. Transactions: ${req.transactionCount}`);
   try {
      const { dateValues, uniqueSortedPriceDates } = await calculateMonthlyPortfolioValues(benchmarkTicker); // RENAMED

      if (Object.keys(dateValues).length === 0) {
         console.log('[API /monthly-returns] No daily values calculated, returning empty array.');
         return res.json([]);
      }

      console.log('[API /monthly-returns] Calculating monthly returns from daily values...');
      const monthlyReturns = [];
      let lastMonthValue = null;
      let lastMonthBenchValue = null;
      let currentMonthStr = '';

      for (const dateStr of uniqueSortedPriceDates) {
         const yearMonth = dateStr.substring(0, 7); // YYYY-MM
         const dailyData = dateValues[dateStr];

         if (dailyData && dailyData.portfolioValue !== null) {
            if (currentMonthStr !== '' && currentMonthStr !== yearMonth) {
               // End of a month, calculate return if possible
               if (lastMonthValue !== null && lastMonthValue !== 0) {
                  const monthEndValue = dateValues[uniqueSortedPriceDates[uniqueSortedPriceDates.indexOf(dateStr) - 1]]?.portfolioValue;
                  const monthEndBenchValue = dateValues[uniqueSortedPriceDates[uniqueSortedPriceDates.indexOf(dateStr) - 1]]?.benchmarkPrice;
                  
                  let portfolioReturn = 0;
                  if (monthEndValue !== null) {
                     portfolioReturn = (monthEndValue / lastMonthValue) - 1;
                  } else {
                      console.warn(`[API /monthly-returns] Missing portfolio end value for ${currentMonthStr}`);
                  }

                  let benchmarkReturn = 0;
                  if (lastMonthBenchValue !== null && lastMonthBenchValue !== 0 && monthEndBenchValue !== null) {
                     benchmarkReturn = (monthEndBenchValue / lastMonthBenchValue) - 1;
                  } else {
                      console.warn(`[API /monthly-returns] Could not calculate benchmark return for ${currentMonthStr}. Start: ${lastMonthBenchValue}, End: ${monthEndBenchValue}`);
                  }

                  monthlyReturns.push({
                     yearMonth: currentMonthStr,
                     portfolioReturn: isNaN(portfolioReturn) ? 0 : parseFloat((portfolioReturn * 100).toFixed(2)),
                     benchmarkReturn: isNaN(benchmarkReturn) ? 0 : parseFloat((benchmarkReturn * 100).toFixed(2))
                  });
               }
               // Reset for the new month
               lastMonthValue = dateValues[uniqueSortedPriceDates[uniqueSortedPriceDates.indexOf(dateStr) - 1]]?.portfolioValue; // Value at end of previous month (start of this month)
               lastMonthBenchValue = dateValues[uniqueSortedPriceDates[uniqueSortedPriceDates.indexOf(dateStr) - 1]]?.benchmarkPrice;
               currentMonthStr = yearMonth;
            } else if (currentMonthStr === '') {
                 // First month initialization
                 currentMonthStr = yearMonth;
                 lastMonthValue = dailyData.portfolioValue; // Use the very first value as the 'start'
                 lastMonthBenchValue = dailyData.benchmarkPrice;
            }
         } // else skip days with null portfolio value
      }
      
      // Calculate for the last month
      if (currentMonthStr !== '' && lastMonthValue !== null && lastMonthValue !== 0) {
         const lastDate = uniqueSortedPriceDates[uniqueSortedPriceDates.length - 1];
         const monthEndValue = dateValues[lastDate]?.portfolioValue;
         const monthEndBenchValue = dateValues[lastDate]?.benchmarkPrice;

         let portfolioReturn = 0;
         if (monthEndValue !== null) {
            portfolioReturn = (monthEndValue / lastMonthValue) - 1;
         } else {
             console.warn(`[API /monthly-returns] Missing portfolio end value for ${currentMonthStr}`);
         }

         let benchmarkReturn = 0;
         if (lastMonthBenchValue !== null && lastMonthBenchValue !== 0 && monthEndBenchValue !== null) {
            benchmarkReturn = (monthEndBenchValue / lastMonthBenchValue) - 1;
         } else {
             console.warn(`[API /monthly-returns] Could not calculate benchmark return for ${currentMonthStr}. Start: ${lastMonthBenchValue}, End: ${monthEndBenchValue}`);
         }

         monthlyReturns.push({
             yearMonth: currentMonthStr,
             portfolioReturn: isNaN(portfolioReturn) ? 0 : parseFloat((portfolioReturn * 100).toFixed(2)),
             benchmarkReturn: isNaN(benchmarkReturn) ? 0 : parseFloat((benchmarkReturn * 100).toFixed(2))
         });
      }

      console.log(`[API /monthly-returns] Calculated ${monthlyReturns.length} months of returns.`);
      res.json(monthlyReturns);

   } catch (error) {
      console.error('[API /monthly-returns] General error:', error);
      console.error('[API /monthly-returns] Error Stack Trace:', error.stack);
      res.status(500).json({ error: 'Failed to calculate monthly returns.', details: error.message });
   }
});

app.get('/portfolio-drawdown', checkTransactionsExist, async (req, res) => {
   console.log(`[API /portfolio-drawdown] Request received. Transactions: ${req.transactionCount}`);
   try {
      // We only need portfolio values for drawdown, no benchmark needed for the helper call
      const { dateValues, uniqueSortedPriceDates } = await calculateMonthlyPortfolioValues(); // RENAMED (pass benchmark explicitly? Default is SPY)

      if (Object.keys(dateValues).length === 0) {
         console.log('[API /portfolio-drawdown] No daily values calculated, returning empty array.');
         return res.json([]);
      }

      console.log('[API /portfolio-drawdown] Calculating drawdowns from daily values...');
      const drawdownData = [];
      let peakValue = -Infinity; // Start with negative infinity to ensure the first value becomes the peak
      let hasEncounteredPositiveValue = false; // Flag to track if we've seen a positive value yet

      for (const dateStr of uniqueSortedPriceDates) {
         const currentValue = dateValues[dateStr]?.portfolioValue; // Uses optional chaining

         if (currentValue !== null && currentValue !== undefined) {
            // Update peak regardless of whether it's positive or negative initially
            if (currentValue > peakValue) {
               peakValue = currentValue;
            }

            // Check if we have encountered the first positive value
            if (!hasEncounteredPositiveValue && currentValue > 0) {
                hasEncounteredPositiveValue = true;
                // Optional: Reset peak here if you only want to track drawdown *after* becoming positive
                // peakValue = currentValue; 
            }

            let drawdownPercentage = 0;
            // Calculate drawdown percentage *only* if we have seen a positive value AND the current peak is positive
            if (hasEncounteredPositiveValue && peakValue > 0) {
               drawdownPercentage = ((currentValue - peakValue) / peakValue) * 100;
            }
            // Ensure drawdown is not positive (it should be 0 or negative)
            drawdownPercentage = Math.min(0, drawdownPercentage);

            drawdownData.push({
               date: dateStr,
               portfolioValue: parseFloat(currentValue.toFixed(2)), 
               peakValue: parseFloat(peakValue.toFixed(2)), // Keep track of peak for potential debugging
               drawdownPercentage: parseFloat(drawdownPercentage.toFixed(2))
            });
         } else {
             // If value is null for a day, we can either skip it or carry forward the last drawdown
             // Skipping for now, as interpolating drawdown might be misleading
             console.warn(`[API /portfolio-drawdown] Skipping drawdown calculation for ${dateStr} due to null portfolio value.`);
         }
      }

      console.log(`[API /portfolio-drawdown] Calculated drawdown for ${drawdownData.length} data points.`);
      res.json(drawdownData);

   } catch (error) {
      console.error('[API /portfolio-drawdown] General error:', error);
      console.error('[API /portfolio-drawdown] Error Stack Trace:', error.stack);
      res.status(500).json({ error: 'Failed to calculate portfolio drawdown.', details: error.message });
   }
});

app.get('/risk-return-metrics', checkTransactionsExist, async (req, res) => {
   const benchmarkTicker = req.query.benchmark || 'SPY';
   console.log(`[API /risk-return-metrics] Request received. Benchmark: ${benchmarkTicker}. Transactions: ${req.transactionCount}`);
   try {
      const { dateValues, uniqueSortedPriceDates } = await calculateMonthlyPortfolioValues(benchmarkTicker); // RENAMED

      if (Object.keys(dateValues).length < 2) { // Need at least 2 data points for returns
         console.log('[API /risk-return-metrics] Not enough daily values (<2) calculated, returning N/A.');
         return res.json({ 
            portfolio: { sharpe: 'N/A', stdDev: 'N/A' }, 
            benchmark: { sharpe: 'N/A', stdDev: 'N/A' }
         });
      }

      console.log('[API /risk-return-metrics] Calculating daily returns...');
      const portfolioReturns = [];
      const benchmarkReturns = [];

      for (let i = 1; i < uniqueSortedPriceDates.length; i++) {
         const currentDate = uniqueSortedPriceDates[i];
         const prevDate = uniqueSortedPriceDates[i - 1];

         const currentValue = dateValues[currentDate]?.portfolioValue;
         const prevValue = dateValues[prevDate]?.portfolioValue;
         const currentBench = dateValues[currentDate]?.benchmarkPrice;
         const prevBench = dateValues[prevDate]?.benchmarkPrice;

         // Calculate portfolio daily return
         if (currentValue !== null && prevValue !== null && prevValue !== 0) {
            portfolioReturns.push((currentValue / prevValue) - 1);
         } else {
             portfolioReturns.push(null); // Mark as null if calculation not possible
         }

         // Calculate benchmark daily return
         if (currentBench !== null && prevBench !== null && prevBench !== 0) {
            benchmarkReturns.push((currentBench / prevBench) - 1);
         } else {
             benchmarkReturns.push(null); // Mark as null
         }
      }

      const validPortfolioReturns = portfolioReturns.filter(r => r !== null);
      const validBenchmarkReturns = benchmarkReturns.filter(r => r !== null);
      
      console.log(`[API /risk-return-metrics] Calculated ${validPortfolioReturns.length} valid portfolio daily returns.`);
      console.log(`[API /risk-return-metrics] Calculated ${validBenchmarkReturns.length} valid benchmark daily returns.`);

      // --- Calculation Helpers ---
      const calculateMean = (arr) => arr.reduce((sum, val) => sum + val, 0) / arr.length;
      const calculateStdDev = (arr, mean) => {
          if (arr.length < 2) return 0; // Need at least 2 points for std dev
          const variance = arr.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / (arr.length - 1); // Sample std dev
          return Math.sqrt(variance);
      };
      const calculateSharpe = (avgReturn, stdDev, riskFreeRate = 0) => {
          if (stdDev === 0) return 0; // Avoid division by zero
          return (avgReturn - riskFreeRate) / stdDev;
      };
      // --- End Helpers ---

      let portfolioAvgDailyReturn = 0;
      let portfolioStdDev = 0;
      let portfolioSharpe = 0;
      let benchmarkAvgDailyReturn = 0;
      let benchmarkStdDev = 0;
      let benchmarkSharpe = 0;

      // Calculate Portfolio Metrics
      if (validPortfolioReturns.length >= 2) { // Need at least 2 returns for std dev/Sharpe
          portfolioAvgDailyReturn = calculateMean(validPortfolioReturns);
          portfolioStdDev = calculateStdDev(validPortfolioReturns, portfolioAvgDailyReturn);
          portfolioSharpe = calculateSharpe(portfolioAvgDailyReturn, portfolioStdDev);
          console.log(`[API /risk-return-metrics] Portfolio Metrics: Avg Daily Return=${portfolioAvgDailyReturn}, Std Dev=${portfolioStdDev}, Sharpe=${portfolioSharpe}`);
      } else {
          console.warn('[API /risk-return-metrics] Not enough valid portfolio returns (<2) to calculate metrics.');
      }
      
      // Calculate Benchmark Metrics
      if (validBenchmarkReturns.length >= 2) { // Need at least 2 returns for std dev/Sharpe
          benchmarkAvgDailyReturn = calculateMean(validBenchmarkReturns);
          benchmarkStdDev = calculateStdDev(validBenchmarkReturns, benchmarkAvgDailyReturn);
          benchmarkSharpe = calculateSharpe(benchmarkAvgDailyReturn, benchmarkStdDev);
          console.log(`[API /risk-return-metrics] Benchmark Metrics: Avg Daily Return=${benchmarkAvgDailyReturn}, Std Dev=${benchmarkStdDev}, Sharpe=${benchmarkSharpe}`);
      } else {
           console.warn('[API /risk-return-metrics] Not enough valid benchmark returns (<2) to calculate metrics.');
      }
      
      // TODO: Annualize metrics if needed (multiply avg daily return by 252, std dev by sqrt(252))
      // For now, returning metrics based on daily calculations

      res.json({
         portfolio: {
            sharpe: validPortfolioReturns.length >= 2 ? parseFloat(portfolioSharpe.toFixed(4)) : 'N/A',
            stdDev: validPortfolioReturns.length >= 2 ? parseFloat((portfolioStdDev * 100).toFixed(2)) + '%' : 'N/A' // Return StdDev as percentage
         },
         benchmark: {
            sharpe: validBenchmarkReturns.length >= 2 ? parseFloat(benchmarkSharpe.toFixed(4)) : 'N/A',
            stdDev: validBenchmarkReturns.length >= 2 ? parseFloat((benchmarkStdDev * 100).toFixed(2)) + '%' : 'N/A' // Return StdDev as percentage
         }
      });

   } catch (error) {
      console.error('[API /risk-return-metrics] General error:', error);
      console.error('[API /risk-return-metrics] Error Stack Trace:', error.stack);
      res.status(500).json({ error: 'Failed to calculate risk-return metrics.', details: error.message });
   }
});

// --- Not Implemented Endpoints ---

app.get('/style-analysis', checkTransactionsExist, async (req, res) => {
    console.log('[API /style-analysis] Request received.');
    const startTime = performance.now();

    try {
        // 1. Get current holdings (ticker -> quantity)
        const holdings = await calculateCurrentHoldings();
        console.log(`[API /style-analysis] Calculated ${Object.keys(holdings).length} current holdings.`);

        if (Object.keys(holdings).length === 0) {
            console.log('[API /style-analysis] No holdings found.');
            // Return empty structure consistent with frontend expectations
            return res.json({ styleAnalysis: [], portfolioTotals: { totalPeRatio: 'N/A' } });
        }

        // 2. Fetch latest prices to calculate market value and weights
        const uniqueTickers = Object.keys(holdings);
        const priceFetchPromises = uniqueTickers.map(ticker =>
            getStockPrices(ticker).catch(error => {
                console.error(`[API /style-analysis] Price fetch/cache check FAILED for ${ticker}: ${error.message}`);
                return null; // Allow continuing for other tickers
            })
        );
        await Promise.allSettled(priceFetchPromises);
        console.log('[API /style-analysis] Price fetch/cache checks attempted.');

        let holdingDataWithValue = [];
        let totalPortfolioValue = 0;
        const latestPricePromises = uniqueTickers.map(async (ticker) => {
            const priceRow = await new Promise((resolve, reject) => {
                db.get("SELECT close_price FROM stock_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1", [ticker], (err, row) => {
                    if (err) reject(err); else resolve(row);
                });
            });
            if (priceRow && priceRow.close_price > 0) {
                const latestPrice = priceRow.close_price;
                const quantity = holdings[ticker];
                const value = quantity * latestPrice;
                totalPortfolioValue += value;
                return { ticker, quantity, latestPrice, value };
            } else {
                console.warn(`[API /style-analysis] Could not find valid latest price for ${ticker} in DB. Excluding from style analysis value calculation.`);
                return null;
            }
        });

        const priceResults = await Promise.allSettled(latestPricePromises);
        console.log(`[API /style-analysis] Total portfolio value calculated: ${totalPortfolioValue}`);

        // Construct style analysis data
        let styleAnalysisData = [];
        let weightedPeSum = 0;
        let totalWeightWithPe = 0;

        const fundamentalPromises = priceResults.map(async (result) => {
            if (result.status === 'fulfilled' && result.value) {
                const { ticker, quantity, latestPrice, value } = result.value;
                const weight = totalPortfolioValue > 0 ? (value / totalPortfolioValue) * 100 : 0;

                // Fetch fundamental data (profile & metrics) for each holding
                const [profileData, metricsData] = await Promise.all([
                    fetchFinnhubProfile(ticker),
                    fetchFinnhubMetrics(ticker)
                ]);

                const category = profileData?.finnhubIndustry || 'N/A';
                // Look for P/E in metrics - check common fields
                let peRatio = metricsData?.metric?.peNormalizedAnnual ?? metricsData?.metric?.peBasicExclExtraTTM ?? metricsData?.metric?.peExclExtraTTM ?? null;

                // Ensure P/E is a number
                if (peRatio !== null && typeof peRatio === 'number' && isFinite(peRatio)) {
                    peRatio = parseFloat(peRatio.toFixed(2));
                    // Add to weighted average calculation
                    weightedPeSum += peRatio * (weight / 100); // Use weight as fraction
                    totalWeightWithPe += (weight / 100);
                } else {
                    peRatio = 'N/A'; // If not found or not a valid number
                }

                styleAnalysisData.push({
                    ticker: ticker,
                    category: category,
                    weight: parseFloat(weight.toFixed(2)),
                    secYield: 'N/A', // Placeholder
                    ttmYield: 'N/A', // Placeholder
                    netExpenseRatio: 'N/A', // Placeholder
                    grossExpenseRatio: 'N/A', // Placeholder
                    peRatio: peRatio,
                    duration: null, // Placeholder
                    contributionToReturn: 'N/A', // Placeholder
                    contributionToRisk: 'N/A' // Placeholder
                });
            } else if (result.status === 'rejected') {
                 console.error(`[API /style-analysis] Error retrieving price result from DB for a ticker: ${result.reason}`);
            }
        });

        await Promise.allSettled(fundamentalPromises);
        console.log('[API /style-analysis] Fundamental data fetches attempted.');

        // Sort by weight descending
        styleAnalysisData.sort((a, b) => b.weight - a.weight);

        // 4. Calculate Portfolio Totals
        const totalPeRatio = totalWeightWithPe > 0 ? parseFloat((weightedPeSum / totalWeightWithPe).toFixed(2)) : 'N/A';

        const portfolioTotals = {
            totalSecYield: 'N/A',
            totalTtmYield: 'N/A',
            totalNetExpenseRatio: 'N/A',
            totalGrossExpenseRatio: 'N/A',
            totalPeRatio: totalPeRatio,
            totalDuration: null,
            totalContributionToReturn: 'N/A'
        };

        const endTime = performance.now();
        console.log(`[API /style-analysis] Completed. Total weighted P/E: ${totalPeRatio}. Took ${((endTime - startTime) / 1000).toFixed(2)}s.`);

        // 5. Send Response
        res.json({
            styleAnalysis: styleAnalysisData,
            portfolioTotals: portfolioTotals
        });

    } catch (error) {
        console.error('[API /style-analysis] Error calculating style analysis:', error);
        console.error('[API /style-analysis] Error stack:', error.stack);
        res.status(500).json({ error: 'Failed to calculate style analysis.', details: error.message });
    }
});

app.get('/active-return', (req, res) => {
  console.log('[API /active-return] Request received - Not Implemented.');
  res.status(501).json({ error: 'Active return calculation is not yet implemented.' });
});

app.get('/market-performance', (req, res) => {
  console.log('[API /market-performance] Request received - Not Implemented.');
  res.status(501).json({ error: 'Market performance calculation is not yet implemented.' });
});


// --- Stock Price Fetching/Caching Helper (Refactored) ---
// Priority: Cache -> Alpha Vantage -> Finnhub -> Resolve if any cache exists, else reject
async function getStockPrices(ticker) {
    console.log(`[getStockPrices] === Starting process for ticker: ${ticker} ===`);
    const fetch = (await import('node-fetch')).default;
    const today = toYYYYMMDD(new Date()); // Get today's date early

    // --- 1. Check Cache --- 
    let latestCachedDate = null;
    let needsUpdate = true; // Assume update needed initially
    try {
        const latestEntry = await new Promise((resolve, reject) => {
            db.get("SELECT date FROM stock_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1", [ticker], (err, row) => {
                if (err) reject(err); // DB error checking cache is critical
                else resolve(row);
            });
        });
        latestCachedDate = latestEntry ? latestEntry.date : null;

        // Check if cache is up-to-date (e.g., contains today's or yesterday's data)
        // Allowing yesterday might be better due to market close times & API delays
        if (latestCachedDate) {
            const latestDateObj = new Date(latestCachedDate + 'T00:00:00Z');
            const todayObj = new Date(today + 'T00:00:00Z');
            const diffTime = Math.abs(todayObj - latestDateObj);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            
            // Consider cache fresh if data is from within the last 1-2 business days (adjust as needed)
            // Simple check: is it today or yesterday?
            const yesterday = toYYYYMMDD(new Date(Date.now() - 86400000)); // 1 day ago
            if (latestCachedDate === today || latestCachedDate === yesterday) {
                needsUpdate = false;
                console.log(`[getStockPrices] Cache hit for ${ticker} (data from ${latestCachedDate} is recent enough).`);
                console.log(`[getStockPrices] === Resolved for ${ticker} from recent cache. ===`);
                return; // Resolve immediately
            }
        }
        console.log(`[getStockPrices] Cache check for ${ticker}: Latest cached date is ${latestCachedDate || 'none'}. Update needed: ${needsUpdate}.`);

    } catch (dbErr) {
        console.error(`[getStockPrices] DB error checking cache for ${ticker}:`, dbErr.message);
        // If we can't even check the cache, it's risky to proceed. Reject.
        console.log(`[getStockPrices] === Rejected for ${ticker} due to DB cache check error. ===`);
        throw dbErr; 
    }

    // --- 2. Attempt Alpha Vantage --- 
    let avFailed = false;
    let fetchedData = null;
    const alphaVantageKey = process.env.ALPHA_VANTAGE_KEY;

    if (!alphaVantageKey) {
        console.warn(`[getStockPrices] Alpha Vantage API key missing. Skipping AV fetch for ${ticker}.`);
        avFailed = true;
    } else {
        const avUrl = `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=${ticker}&outputsize=compact&apikey=${alphaVantageKey}`;
        const safeAvUrl = avUrl.replace(/apikey=.*$/, 'apikey=HIDDEN');
        console.log(`[getStockPrices] Attempting Alpha Vantage fetch for ${ticker}: ${safeAvUrl}`);
        try {
            const response = await fetch(avUrl);
            console.log(`[getStockPrices] Alpha Vantage response status for ${ticker}: ${response.status}`);
            if (!response.ok) throw new Error(`AV API request failed with status ${response.status}`);
            
            const data = await response.json();

            if (data["Error Message"]) throw new Error(`AV API Error: ${data["Error Message"]}`);
            if (data["Note"]) throw new Error(`AV API Note (likely rate limit): ${data["Note"]}`);
            if (!data["Time Series (Daily)"]) throw new Error("Unexpected AV API response format: Missing 'Time Series (Daily)'");
            
            console.log(`[getStockPrices] Alpha Vantage fetch successful for ${ticker}.`);
            fetchedData = data["Time Series (Daily)"]; // Structure: { 'YYYY-MM-DD': { '4. close': price }, ... }

        } catch (avError) {
            console.warn(`[getStockPrices] Alpha Vantage fetch FAILED for ${ticker}: ${avError.message}`);
            avFailed = true;
        }
    }

    // --- 3. Attempt Finnhub if Alpha Vantage Failed --- 
    let fhFailed = false;
    if (avFailed) { // <<<<<< RESTORE THIS IF CHECK
        console.log(`[getStockPrices] Alpha Vantage failed for ${ticker}, attempting Finnhub...`); // Restored log message
        try {
            // <<<<<< REMOVE TEMPORARILY HARDCODED TICKER >>>>>>
            // const testTicker = 'AAPL'; // REMOVE
            // console.log(`[getStockPrices] TESTING Finnhub fetch with hardcoded ticker: ${testTicker}`); // REMOVE
            fetchedData = await fetchFromFinnhub(ticker); // Use original ticker here
             // Check if Finnhub returned data
             if (!fetchedData || fetchedData.length === 0) {
                 console.warn(`[getStockPrices] Finnhub did not return data for ${ticker}.`);
                 fhFailed = true;
                 fetchedData = null; // Ensure fetchedData is null if Finnhub returned nothing
             } else {
                 console.log(`[getStockPrices] Finnhub fetch successful for ${ticker}.`);
             }
        } catch (fhError) {
            console.warn(`[getStockPrices] Finnhub fetch FAILED for ${ticker}: ${fhError.message}`);
            fhFailed = true;
            fetchedData = null; // Ensure fetchedData is null on error
        }
    }

    // --- 5. Final Resolution --- 
    // Resolve if *any* data exists (even if stale and update failed), reject only if absolutely no data found.
    if (!avFailed || !fhFailed) { // <<<<<< RESTORE THIS LOGIC
        // At least one API succeeded OR we didn't need an update.
        console.log(`[getStockPrices] === Resolved for ${ticker} (Update successful or not needed). ===`);
        return; // Resolve 
    } else {
        // Both APIs failed. Check if *any* old data exists.
        if (latestCachedDate) {
             console.log(`[getStockPrices] Both APIs failed for ${ticker}, but stale data exists (${latestCachedDate}). Resolving.`);
             console.log(`[getStockPrices] === Resolved for ${ticker} (Update failed, using stale cache). ===`);
             return; // Resolve
        } else {
             // <<<<< Pass the correct ticker to the error message >>>>>
             const finalError = new Error(`Failed to fetch any price data for ${ticker}. Both APIs failed and no cache exists.`);
             console.error(`[getStockPrices] ${finalError.message}`);
             console.log(`[getStockPrices] === Rejected for ${ticker} (No data available). ===`);
             throw finalError; // Reject - No data at all for this ticker
        }
    }
    // <<<<< REMOVE TEMPORARY RESOLUTION >>>>>
    // console.log(`[getStockPrices] === Reached end of test for ${ticker}. Check logs for Finnhub results for ${testTicker}. ===`);
    // return; 
}

// --- Finnhub Fetching Helper ---
async function fetchFromFinnhub(ticker) {
    console.log(`[fetchFromFinnhub] Attempting fetch for ticker: ${ticker} using /quote endpoint.`);
    const fetch = (await import('node-fetch')).default;
    const apiKey = process.env.FINNHUB_KEY;

    if (!apiKey) {
        throw new Error("Finnhub API key not set in .env");
    }

    // Finnhub /quote endpoint
    const url = `https://finnhub.io/api/v1/quote?symbol=${ticker}&token=${apiKey}`;
    const safeUrl = url.replace(/token=.*$/, 'token=HIDDEN');
    console.log(`[fetchFromFinnhub] Fetching URL for ${ticker}: ${safeUrl}`);

    try {
        const response = await fetch(url);
        console.log(`[fetchFromFinnhub] API response status for ${ticker}: ${response.status}`);

        if (!response.ok) {
            // Check for specific rate limit status code
            if (response.status === 429) {
                 console.warn(`[fetchFromFinnhub] Finnhub rate limit hit for ${ticker}.`);
                 // Return empty array to indicate failure due to rate limit, but not a critical error
                 return []; 
            }
            throw new Error(`Finnhub API request failed for ${ticker} with status ${response.status}`);
        }

        const data = await response.json();

        // Extract the previous close price ('pc')
        const previousClose = data.pc;

        if (previousClose === undefined || previousClose === null || isNaN(parseFloat(previousClose)) || previousClose === 0) { // Added check for 0
            console.warn(`[fetchFromFinnhub] Finnhub /quote response for ${ticker} missing or invalid previous close price (pc):`, data);
            return []; // Return empty array if no valid previous close
        }

        const price = parseFloat(previousClose);

        // Infer date as yesterday (simple approach)
        const yesterday = toYYYYMMDD(new Date(Date.now() - 86400000));

        console.log(`[fetchFromFinnhub] Successfully fetched previous close for ${ticker}: ${price} (associating with date ${yesterday})`);
        // Return in the expected array format [{date, price}]
        return [{ date: yesterday, price: price }];

    } catch (error) {
        // Don't re-throw rate limit errors specifically if already handled
        if (error.message.includes('status 429')) {
             console.warn(`[fetchFromFinnhub] Rate limit error during fetch for ${ticker}.`);
             return [];
        }
        console.error(`[fetchFromFinnhub] Network or JSON parsing error fetching ${ticker}:`, error.message);
        throw error; // Re-throw other errors to be caught by getStockPrices
    }
}

// --- Route: GET /fundamentals-date (Placeholder) ---
app.get('/fundamentals-date', (req, res) => {
  console.log('[API /fundamentals-date] Request received - Placeholder.');
  // Placeholder response - replace with actual logic if needed later
  res.json({ fundamentalsDate: 'Data not available' });
  // Alternatively, use 501 if it requires calculation:
  // res.status(501).json({ error: 'Fundamentals date endpoint not implemented.' });
});

// --- Other Helper Functions (Keep for future implementation) ---
// calculateCAGR, calculateAnnualizedStdDev, calculateDownsideDeviation, etc.
// These will be needed when the actual analytics endpoints are implemented.
// Ensure they don't rely on mock data or removed structures.

// (Add back any necessary calculation helpers here, ensuring they are compatible
//  with data derived solely from 'transactions' and 'stock_prices')


// --- Server Start ---
app.listen(port, () => {
  console.log(`Robinhood Dashboard backend server running at http://localhost:${port}`);
});

// --- Finnhub Helper Functions ---

// Cache for Finnhub data (simple in-memory cache)
const finnhubCache = new Map();
const FINNHUB_CACHE_TTL = 1000 * 60 * 60 * 4; // Cache for 4 hours

async function fetchFinnhubProfile(ticker) {
    const cacheKey = `profile_${ticker}`;
    const cached = finnhubCache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp < FINNHUB_CACHE_TTL)) {
        console.log(`[fetchFinnhubProfile] Cache hit for ${ticker}`);
        return cached.data;
    }

    console.log(`[fetchFinnhubProfile] Attempting Finnhub /stock/profile2 fetch for ${ticker}`);
    const fetch = (await import('node-fetch')).default;
    const apiKey = process.env.FINNHUB_KEY;
    if (!apiKey) {
        console.warn('[fetchFinnhubProfile] Finnhub API key missing.');
        return null; // Cannot fetch without API key
    }

    const url = `https://finnhub.io/api/v1/stock/profile2?symbol=${ticker}&token=${apiKey}`;
    const safeUrl = url.replace(/token=.*$/, 'token=HIDDEN');
    console.log(`[fetchFinnhubProfile] Fetching URL: ${safeUrl}`);

    try {
        const response = await fetch(url);
        console.log(`[fetchFinnhubProfile] API response status for ${ticker}: ${response.status}`);
        if (!response.ok) {
            if (response.status === 429) {
                console.warn(`[fetchFinnhubProfile] Finnhub rate limit hit for ${ticker}.`);
            } else {
                console.warn(`[fetchFinnhubProfile] Finnhub API request failed for ${ticker} with status ${response.status}`);
            }
            return null; // Return null on fetch failure
        }
        const data = await response.json();

        // Basic validation: Check if the response is an empty object {} which can happen for unknown tickers
        if (Object.keys(data).length === 0) {
            console.warn(`[fetchFinnhubProfile] Received empty profile data for ${ticker}, likely unknown symbol.`);
            return null;
        }

        console.log(`[fetchFinnhubProfile] Success for ${ticker}.`);
        finnhubCache.set(cacheKey, { data, timestamp: Date.now() });
        return data; // Return the profile data (e.g., { country: 'US', currency: 'USD', finnhubIndustry: 'Technology', ... })

    } catch (error) {
        console.error(`[fetchFinnhubProfile] Network or JSON parsing error fetching ${ticker}:`, error.message);
        return null; // Return null on error
    }
}

async function fetchFinnhubMetrics(ticker) {
    const cacheKey = `metrics_${ticker}`;
    const cached = finnhubCache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp < FINNHUB_CACHE_TTL)) {
        console.log(`[fetchFinnhubMetrics] Cache hit for ${ticker}`);
        return cached.data;
    }

    console.log(`[fetchFinnhubMetrics] Attempting Finnhub /stock/metric fetch for ${ticker}`);
    const fetch = (await import('node-fetch')).default;
    const apiKey = process.env.FINNHUB_KEY;
    if (!apiKey) {
        console.warn('[fetchFinnhubMetrics] Finnhub API key missing.');
        return null;
    }

    // Fetch basic price metrics which often include P/E
    const url = `https://finnhub.io/api/v1/stock/metric?symbol=${ticker}&metric=price&token=${apiKey}`;
    const safeUrl = url.replace(/token=.*$/, 'token=HIDDEN');
    console.log(`[fetchFinnhubMetrics] Fetching URL: ${safeUrl}`);

    try {
        const response = await fetch(url);
        console.log(`[fetchFinnhubMetrics] API response status for ${ticker}: ${response.status}`);
        if (!response.ok) {
             if (response.status === 429) {
                 console.warn(`[fetchFinnhubMetrics] Finnhub rate limit hit for ${ticker}.`);
             } else {
                 console.warn(`[fetchFinnhubMetrics] Finnhub API request failed for ${ticker} with status ${response.status}`);
             }
             return null;
        }
        const data = await response.json();

        // Validate response structure (expects 'metric' object)
        if (!data || typeof data.metric !== 'object' || data.metric === null) {
             console.warn(`[fetchFinnhubMetrics] Received invalid metrics data for ${ticker}:`, data);
             return null;
        }

        console.log(`[fetchFinnhubMetrics] Success for ${ticker}.`);
        finnhubCache.set(cacheKey, { data, timestamp: Date.now() });
        // Return the metrics data (e.g., { metric: { peNormalizedAnnual: 25.5, ... }, symbol: 'AAPL' })
        return data;

    } catch (error) {
        console.error(`[fetchFinnhubMetrics] Network or JSON parsing error fetching ${ticker}:`, error.message);
        return null;
    }
}

// --- Route: GET /raw-data ---
// Fetches a sample of raw data from the database tables.
app.get('/raw-data', async (req, res) => {
    console.log('[API /raw-data] Request received.');
    try {
        // Fetch limited transactions (e.g., latest 100)
        const transactionsPromise = new Promise((resolve, reject) => {
            db.all("SELECT * FROM transactions ORDER BY activity_date DESC, id DESC LIMIT 100", [], (err, rows) => {
                if (err) {
                    console.error('[API /raw-data] DB error fetching transactions:', err.message);
                    reject(new Error('Failed to fetch transactions.'));
                } else {
                    console.log(`[API /raw-data] Fetched ${rows.length} transactions.`);
                    resolve(rows);
                }
            });
        });

        // Fetch limited stock prices (e.g., latest 200 by date within ticker)
        const stockPricesPromise = new Promise((resolve, reject) => {
            // Using a subquery or window function might be more efficient for "latest per ticker",
            // but a simple overall limit is easier for now.
            db.all("SELECT * FROM stock_prices ORDER BY date DESC, ticker LIMIT 200", [], (err, rows) => {
                if (err) {
                    console.error('[API /raw-data] DB error fetching stock prices:', err.message);
                    reject(new Error('Failed to fetch stock prices.'));
                } else {
                    console.log(`[API /raw-data] Fetched ${rows.length} stock prices.`);
                    resolve(rows);
                }
            });
        });

        // Wait for both queries to complete
        const [transactions, stockPrices] = await Promise.all([transactionsPromise, stockPricesPromise]);

        console.log('[API /raw-data] Sending raw data response.');
        res.json({
            transactions: transactions || [],
            stockPrices: stockPrices || []
        });

    } catch (error) {
        console.error('[API /raw-data] General error:', error);
        res.status(500).json({ error: 'Failed to fetch raw data.', details: error.message });
    }
});
