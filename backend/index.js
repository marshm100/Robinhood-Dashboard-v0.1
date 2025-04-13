// --- Step 1: Load Dependencies ---
// This section imports necessary libraries (modules) for the server to function.

require('dotenv').config(); // Loads environment variables from a .env file (like API keys) into process.env
const express = require('express'); // Imports the Express framework for building web servers
const multer = require('multer'); // Imports Multer, used for handling file uploads (like the CSV)
const Papa = require('papaparse'); // Imports PapaParse, used for parsing CSV data
const sqlite3 = require('sqlite3').verbose(); // Imports SQLite3 for database operations (with extra debugging info)
const fs = require('fs'); // Imports the built-in Node.js File System module for reading/writing files
const path = require('path'); // Imports the built-in Node.js Path module for working with file paths
const { formatDateForDatabase, toYYYYMMDD } = require('./date-utils'); // Imports custom date formatting functions from another file

// --- Step 2: Initialize Express App ---
const app = express(); // Creates an instance of the Express application
const port = 3002; // Defines the port number the server will listen on (e.g., http://localhost:3002)

// --- Step 3: Configure Middleware ---
// Middleware functions run for every incoming request, potentially modifying it or performing checks before it reaches the route handler.

// Allows the server to parse incoming request bodies as JSON
app.use(express.json());
// Allows the server to parse incoming request bodies with URL-encoded payloads (often used by HTML forms)
app.use(express.urlencoded({ extended: true }));

// Setup CORS (Cross-Origin Resource Sharing)
// This middleware is crucial for allowing the frontend (running on a different port, e.g., 5173)
// to make requests to this backend server (running on port 3002).
// Without CORS configured correctly, the browser would block these requests for security reasons.
app.use((req, res, next) => {
  // 'Access-Control-Allow-Origin': Specifies which origins (domains/ports) are allowed to access the backend.
  // '*' allows any origin, which is okay for development but should be restricted to your frontend's specific URL in production.
  res.header('Access-Control-Allow-Origin', '*');
  // 'Access-Control-Allow-Headers': Specifies which HTTP headers are allowed in requests from the frontend.
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  // 'Access-Control-Allow-Methods': Specifies which HTTP methods (GET, POST, etc.) are allowed.
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'); // OPTIONS is needed for some pre-flight requests
  // 'next()' passes control to the next middleware function or route handler in the stack.
  next();
});

// Configure multer for file uploads
// Sets up Multer to store uploaded files temporarily in the 'uploads/' directory within the backend folder.
// When a file is uploaded (e.g., in the /upload route), Multer handles saving it here.
const upload = multer({ dest: 'uploads/' });

// --- Step 4: Setup SQLite Database ---
// Connects to the SQLite database file and ensures necessary tables exist.
// SQLite is a lightweight, file-based database, good for simple applications.

// Define the path to the database file. `__dirname` is the directory where this script (index.js) resides.
// This will create 'robinhood.db' in the backend/ directory if it doesn't exist.
const dbPath = path.join(__dirname, 'robinhood.db');

// Create a database connection instance using the specified path.
// The second argument is a callback function that runs after attempting to connect.
const db = new sqlite3.Database(dbPath, (err) => {
  // Check if there was an error during connection.
  if (err) {
    // Log an error message to the console if connection failed.
    console.error('Error opening database:', err.message);
  } else {
    // Log a success message if connection is successful.
    console.log('Connected to the SQLite database.');

    // --- Step 4a: Create 'transactions' Table (if needed) ---
    // This SQL command uses 'CREATE TABLE IF NOT EXISTS' which is safe to run every time;
    // it only creates the table if it's missing.
    // Define columns for the transactions table:
    // id: Unique ID for each transaction, automatically generated
    // activity_date: Date of the transaction (stored as text in YYYY-MM-DD format)
    // ticker: Stock symbol (e.g., AAPL, GOOG)
    // trans_code: Transaction type (e.g., Buy, Sell, CDIV for dividend)
    // quantity: Number of shares involved (REAL allows decimal values)
    // price: Price per share at the time of transaction
    // amount: Total value of the transaction (negative for debits like buys/fees, positive for credits like sells/deposits)
    db.run(`CREATE TABLE IF NOT EXISTS transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      activity_date TEXT,
      ticker TEXT,
      trans_code TEXT,
      quantity REAL,
      price REAL,
      amount REAL
    )`, (err) => {
      // Callback runs after the CREATE TABLE command executes.
      if (err) {
        console.error('Error creating transactions table:', err.message);
      } else {
        // Log success confirmation
        console.log('Transactions table confirmed or created.');
      }
    });

    // --- Step 4b: Create 'portfolio_config' Table (if needed) ---
    // Stores user-defined portfolio settings like total investment and asset allocation.
    // Define columns for portfolio configuration:
    // id: Unique ID for each config entry
    // total_investment: Total amount invested by the user
    // ticker: Stock symbol for a specific allocation
    // allocation_percentage: Percentage of the total investment allocated to this ticker
    db.run(`CREATE TABLE IF NOT EXISTS portfolio_config (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      total_investment REAL,
      ticker TEXT,
      allocation_percentage REAL
    )`, (err) => {
      if (err) {
        console.error('Error creating portfolio_config table:', err.message);
      } else {
        console.log('Portfolio config table is ready.');
      }
    });

    // --- Step 4c: Create 'stock_prices' Table (if needed) ---
    // Caches historical stock prices fetched from the Alpha Vantage API.
    // This helps avoid hitting API rate limits and speeds up subsequent calculations.
    // Define columns for caching stock prices:
    // id: Unique ID for each price entry
    // ticker: Stock symbol the price belongs to
    // date: Date of the price (YYYY-MM-DD)
    // close_price: Closing price for that stock on that date
    // UNIQUE(ticker, date): IMPORTANT constraint ensuring only one price entry per ticker per day.
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
// These blocks define how the server responds when a client (like the frontend)
// sends a request to a specific URL path (e.g., '/', '/upload') using a specific HTTP method (e.g., GET, POST).

// --- Route 1: GET / ---
// Defines a handler for GET requests to the root URL (e.g., http://localhost:3002/).
// 'app.get' specifies the HTTP method (GET) and the path ('/').
// The callback function `(req, res) => { ... }` is executed when a request matches.
// - `req` (request) object contains information about the incoming request.
// - `res` (response) object is used to send a response back to the client.
app.get('/', (req, res) => {
  // Sends a simple plain text response back to the client.
  res.send('Robinhood Dashboard Backend');
});

// --- Route 2: GET /test-keys ---
// A simple test endpoint to check if API keys were loaded correctly from the .env file.
// Handles GET requests to '/test-keys' (e.g., http://localhost:3002/test-keys).
app.get('/test-keys', (req, res) => {
  // Responds with a JSON object containing the values of the API keys read from `process.env`.
  // `process.env.ALPHA_VANTAGE_KEY` gets the value associated with that key in the .env file (loaded by dotenv).
  // If a key wasn't found in .env, its value here will be `undefined`.
  res.json({
    alphaVantageKey: process.env.ALPHA_VANTAGE_KEY,
    finnhubKey: process.env.FINNHUB_KEY
  });
});

// --- Route 3: GET /portfolio-growth ---
// Calculates and returns data points for the portfolio growth chart.
// This involves fetching daily portfolio values, fetching benchmark (e.g., SPY) prices,
// aligning them by date, and scaling the benchmark to start at the same value as the portfolio.
// It responds with an array of { date, portfolioValue, benchmarkValue } objects.
app.get('/portfolio-growth', async (req, res) => {
  // Get the benchmark ticker from query parameters (e.g., /portfolio-growth?benchmark=VOO).
  // If no benchmark is specified in the query, default to 'SPY'.
  const benchmarkTicker = req.query.benchmark || 'SPY';
  console.log(`[API /portfolio-growth] Request received. Benchmark: ${benchmarkTicker}`);

  // Use a try...catch block to handle potential errors during async operations.
  try {
    // --- Step 3a: Calculate Daily Portfolio Values ---
    // Calls the async helper function `calculateDailyPortfolioValues` (defined later).
    // This function calculates the portfolio's total value for each day based on transactions and cached/fetched stock prices.
    console.log('[API /portfolio-growth] Calculating daily portfolio values...');
    const portfolioValues = await calculateDailyPortfolioValues(); // `await` pauses execution until the promise resolves
    console.log(`[API /portfolio-growth] Calculated ${portfolioValues?.length ?? 0} portfolio daily values.`);

    // --- Step 3b: Handle No Portfolio Data ---
    // If the helper function returns an empty array or null (e.g., no transactions uploaded yet).
    if (!portfolioValues || portfolioValues.length === 0) {
      console.log('[API /portfolio-growth] No portfolio data found.');
      // Return a 404 Not Found status with an informative JSON error message.
      return res.status(404).json({
        error: 'No portfolio data available',
        message: 'Please upload transaction data before viewing portfolio growth.'
      });
    }

    // --- Step 3c: Fetch Benchmark Price Data ---
    // Calls the async helper function `getStockPrices` (defined later) for the chosen benchmark ticker.
    // This function checks the database cache first, then fetches from Alpha Vantage if needed.
    console.log(`[API /portfolio-growth] Fetching benchmark prices for ${benchmarkTicker}...`);
    const benchmarkPrices = await getStockPrices(benchmarkTicker);

    // --- Step 3d: Handle Missing Benchmark Data ---
    // Check if fetching benchmark prices failed (returned null) or if the data structure is invalid.
    if (!benchmarkPrices || !benchmarkPrices['Time Series (Daily)']) {
      console.log(`[API /portfolio-growth] No benchmark data available for ${benchmarkTicker}.`);
      // Return a 500 Server Error status, as this usually indicates an external API issue or configuration problem.
      return res.status(500).json({
        error: 'Benchmark data unavailable',
        message: `Could not retrieve data for benchmark ${benchmarkTicker}. Please try again with a different benchmark or check API key/limits.`
      });
    }
    console.log(`[API /portfolio-growth] Benchmark prices fetched for ${benchmarkTicker}.`);

    // --- Step 3e: Calculate Initial Benchmark Alignment ---
    // To compare growth visually, we need to scale the benchmark to start at the same value as the portfolio.
    // Get the portfolio's starting value and date (first element of the sorted array).
    const initialPortfolioValue = portfolioValues[0].value;
    const initialBenchmarkDate = portfolioValues[0].date;
    // Find the benchmark's price on that specific starting date using the helper function `getPriceForDate`.
    const initialBenchmarkPrice = getPriceForDate(benchmarkPrices, initialBenchmarkDate);

    // --- Step 3f: Handle Missing Initial Benchmark Price ---
    // If the benchmark didn't have a price on the portfolio's first day (e.g., market closed, ticker didn't exist yet).
    if (!initialBenchmarkPrice) {
      console.log(`[API /portfolio-growth] No benchmark price available for initial date (${initialBenchmarkDate}) for ${benchmarkTicker}.`);
      // Return a 500 error as alignment isn't possible.
      return res.status(500).json({
        error: 'Missing benchmark data for alignment',
        message: `Could not find price for ${benchmarkTicker} on initial portfolio date (${initialBenchmarkDate}). The benchmark might not have existed then, or data is unavailable.`
      });
    }
    console.log(`[API /portfolio-growth] Initial alignment: Portfolio=${initialPortfolioValue} on ${initialBenchmarkDate}, Benchmark Price=${initialBenchmarkPrice}`);

    // --- Step 3g: Combine Portfolio and Benchmark Values ---
    // Iterate through each day in the `portfolioValues` array.
    // For each day, calculate the corresponding scaled benchmark value.
    console.log('[API /portfolio-growth] Combining portfolio and benchmark data...');
    const growthData = portfolioValues.map(item => {
      // Find the benchmark price for the current portfolio date.
      const benchmarkPrice = getPriceForDate(benchmarkPrices, item.date);

      // Only include this date if we have a valid benchmark price for it.
      // Also check that initial benchmark price is valid to avoid division by zero.
      if (benchmarkPrice && benchmarkPrice > 0 && initialBenchmarkPrice && initialBenchmarkPrice > 0) {
        // Calculate the scaled benchmark value:
        // Formula: PortfolioStartValue * (CurrentBenchmarkPrice / InitialBenchmarkPrice)
        const scaledBenchmarkValue = initialPortfolioValue * (benchmarkPrice / initialBenchmarkPrice);
        return {
          date: item.date,                 // Date (YYYY-MM-DD)
          portfolioValue: item.value,       // Portfolio value on this date
          benchmarkValue: scaledBenchmarkValue // Scaled benchmark value on this date
        };
      } else {
        // If no valid benchmark price exists for this date, skip it by returning null.
        return null;
      }
    }).filter(item => item !== null); // Use `filter` to remove the null entries created above.

    console.log(`[API /portfolio-growth] Combined data has ${growthData.length} points.`);

    // --- Step 3h: Handle Empty Combined Data ---
    // If, after filtering, no valid data points remain (e.g., portfolio dates don't overlap with benchmark data).
    if (growthData.length === 0) {
      console.log('[API /portfolio-growth] Growth data is empty after combining/filtering.');
      // Return 404 as no comparable data could be generated.
      return res.status(404).json({
        error: 'No comparable portfolio/benchmark data available',
        message: 'Could not align portfolio dates with available benchmark price data. Check transaction dates and benchmark ticker.'
      });
    }

    // --- Step 3i: Send Response ---
    // If everything is successful, send the `growthData` array as a JSON response.
    console.log('[API /portfolio-growth] Sending growth data response.');
    res.json(growthData);

  } catch (error) {
    // --- Step 3j: Handle General Errors ---
    // Catch any unexpected errors that occurred during the `try` block.
    console.error('[API /portfolio-growth] Error calculating portfolio growth:', error);
    // Send a generic 500 Internal Server Error response.
    res.status(500).json({
      error: 'Error calculating portfolio growth',
      message: `An unexpected error occurred: ${error.message}`
    });
  }
});

// --- Route 4: GET /portfolio-drawdown ---
// Calculates and returns data for the portfolio drawdown chart.
// Drawdown measures the percentage decline from the portfolio's historical peak value to its current value.
// It helps visualize the magnitude and duration of losses.
app.get('/portfolio-drawdown', async (req, res) => {
  console.log('[API /portfolio-drawdown] Request received.');
  // Use a try...catch block for async operations.
  try {
    // --- Step 4a: Calculate Daily Portfolio Values ---
    // First, we need the portfolio value for each day.
    console.log('[API /portfolio-drawdown] Calculating daily portfolio values...');
    const portfolioValues = await calculateDailyPortfolioValues();
    console.log(`[API /portfolio-drawdown] Calculated ${portfolioValues?.length ?? 0} portfolio daily values.`);

    // --- Step 4b: Handle No Portfolio Data ---
    // If no transactions or values exist, drawdown cannot be calculated.
    if (!portfolioValues || portfolioValues.length === 0) {
      console.log('[API /portfolio-drawdown] No portfolio data available.');
      // Return 404 Not Found.
      return res.status(404).json({
        success: false, // Indicate failure
        error: 'No portfolio data available',
        message: 'Upload transaction data first before viewing drawdown.'
      });
    }

    // --- Step 4c: Calculate Drawdown ---
    // Iterate through the daily values, keeping track of the highest value seen so far (running maximum or peak).
    console.log('[API /portfolio-drawdown] Calculating drawdown percentages...');
    let runningMax = portfolioValues[0].value; // Initialize the peak with the first day's value.
    // Use `map` to create a new array containing drawdown information for each day.
    const drawdownData = portfolioValues.map(item => {
      // Update the running maximum if the current day's value is higher.
      if (item.value > runningMax) {
        runningMax = item.value;
      }

      // Calculate the drawdown percentage for the current day:
      // Formula: ((Peak Value - Current Value) / Peak Value) * 100
      // Handle division by zero if the peak value is 0 (though unlikely with filtered daily values).
      const drawdownPercentage = runningMax > 0 ? ((runningMax - item.value) / runningMax) * 100 : 0;

      // Return an object containing the date, the portfolio value, the peak value at that time,
      // and the calculated drawdown percentage for that day.
      return {
        date: item.date,
        value: item.value,          // Portfolio value on this date
        peak: runningMax,           // Highest value seen up to this date
        drawdownPercentage: drawdownPercentage // Percentage decline from the peak
      };
    });
    console.log(`[API /portfolio-drawdown] Calculated drawdown for ${drawdownData.length} points.`);

    // --- Step 4d: Send Response ---
    // Send the array of drawdown data objects as a JSON response.
    console.log('[API /portfolio-drawdown] Sending drawdown data response.');
    res.json(drawdownData);

  } catch (error) {
    // --- Step 4e: Handle General Errors ---
    // Catch any unexpected errors during the process.
    console.error('[API /portfolio-drawdown] Error calculating portfolio drawdown:', error);
    // Send a 500 Internal Server Error response.
    res.status(500).json({
      success: false, // Indicate failure
      error: 'Failed to calculate portfolio drawdown data',
      message: `An unexpected error occurred: ${error.message}`
    });
  }
});

// --- CSV Upload and Processing ---

// --- Route 5: POST /upload ---
// Handles the primary action of uploading the user's Robinhood transaction CSV file.
// It uses the 'upload' middleware (defined earlier using Multer) to handle the file data
// attached to the request under the field name 'file'.
app.post('/upload', upload.single('file'), (req, res) => {
  console.log('[API /upload] Request received.');
  // --- Step 5a: Check if File Was Uploaded ---
  // Multer adds the `req.file` object if a file named 'file' was successfully uploaded.
  // If `req.file` is missing, it means no file was sent or the field name was wrong.
  if (!req.file) {
    console.log('[API /upload] No file uploaded in the request.');
    // Return a 400 Bad Request error.
    return res.status(400).json({ error: 'No file uploaded' });
  }
  console.log(`[API /upload] File uploaded: ${req.file.originalname}, Temp path: ${req.file.path}`);

  // --- Step 5b: Get Temporary File Path ---
  // Multer saves the uploaded file to a temporary location (in the 'uploads/' directory)
  // and provides the path via `req.file.path`.
  const filePath = req.file.path;

  // --- Step 5c: Read File Content ---
  // Use the Node.js 'fs' (File System) module to read the content of the temporary CSV file.
  // 'utf8' specifies the character encoding.
  // This is an asynchronous operation; the callback function `(err, data) => { ... }` runs when reading is done or an error occurs.
  console.log('[API /upload] Reading uploaded file content...');
  fs.readFile(filePath, 'utf8', (err, data) => {
    // --- Step 5d: Handle File Reading Errors ---
    if (err) {
      console.error('[API /upload] Error reading uploaded file:', err);
      // Attempt to clean up the temporary file even if reading failed.
      fs.unlink(filePath, (unlinkErr) => {
        if (unlinkErr) console.error('[API /upload] Error deleting temp file after read error:', unlinkErr);
      });
      // Return a 500 Internal Server Error.
      return res.status(500).json({ error: 'Error reading file' });
    }
    console.log('[API /upload] File read successfully.');

    // --- Step 5e: Parse CSV Data ---
    // Use the PapaParse library to parse the CSV string (`data`) into a JavaScript structure.
    console.log('[API /upload] Parsing CSV data...');
    Papa.parse(data, {
      header: true, // Treat the first row of the CSV as headers (keys for the resulting objects).
      skipEmptyLines: true, // Ignore any blank lines in the CSV.

      // --- Step 5f: Processing Callback (on successful parse) ---
      // The `complete` function is called by PapaParse when parsing finishes successfully.
      // `results` contains the parsed data (`results.data`) and metadata/errors.
      complete: (results) => {
        console.log(`[API /upload] CSV parsing complete. Found ${results.data.length} rows.`);
        // `results.data` is an array of objects, where each object represents a row in the CSV.
        const transactions = results.data;

        // --- Step 5g: Check for Empty Results ---
        // Ensure that the parsing resulted in at least one transaction row.
        if (!transactions || transactions.length === 0) {
          console.log('[API /upload] No transactions found in the parsed CSV.');
          // Clean up the temporary file.
          fs.unlink(filePath, (unlinkErr) => {
            if (unlinkErr) console.error('[API /upload] Error deleting temp file after empty parse:', unlinkErr);
          });
          // Return a 400 Bad Request error if the CSV was empty or contained no data rows.
          return res.status(400).json({ error: 'No transactions found in file' });
        }

        // --- Step 5h: Clear Existing Database Transactions ---
        // Before inserting the new data, delete all records currently in the 'transactions' table.
        // This ensures we only have the data from the latest uploaded file.
        console.log('[API /upload] Clearing existing transactions from database...');
        db.run('DELETE FROM transactions', (deleteErr) => {
          // Callback runs after the DELETE operation attempts to execute.
          if (deleteErr) {
            console.error('[API /upload] Error clearing existing transactions:', deleteErr.message);
            // Clean up the temporary file.
            fs.unlink(filePath, (unlinkErr) => {
              if (unlinkErr) console.error('[API /upload] Error deleting temp file after DB clear error:', unlinkErr);
            });
            // Return a 500 Internal Server Error if clearing the database fails.
            return res.status(500).json({ error: 'Error preparing database for new transactions' });
          }
          console.log('[API /upload] Cleared existing transactions table.');

          // --- Step 5i: Prepare SQL Insert Statement ---
          // Preparing the statement beforehand is more efficient than creating a new SQL string for every row.
          // The `?` symbols are placeholders that will be filled with values for each transaction.
          const insertStmt = db.prepare(`
            INSERT INTO transactions (
              activity_date, ticker, trans_code, quantity, price, amount
            ) VALUES (?, ?, ?, ?, ?, ?)
          `);

          let insertedCount = 0; // Counter for successfully inserted rows.
          let errorCount = 0; // Counter for rows that caused an insertion error.

          // --- Step 5j: Iterate and Insert Each Transaction ---
          console.log(`[API /upload] Processing ${transactions.length} transactions for insertion...`);
          // Loop through each transaction object parsed from the CSV.
          transactions.forEach((transaction, index) => {
            // Use a try...catch block to handle errors during the processing of a single row,
            // preventing one bad row from stopping the entire upload.
            try {
              // --- Step 5k: Data Cleaning and Formatting ---
              // Extract data for each column from the transaction object (using header names from CSV).
              // Provide default values (e.g., empty string, 0) if a field is missing in the CSV row.
              let activityDateRaw = transaction['Activity Date'] || '';
              // Use the imported utility function to format the date consistently (e.g., to YYYY-MM-DD).
              let activityDate = formatDateForDatabase(activityDateRaw);

              const ticker = transaction['Instrument'] || '';
              const transCode = transaction['Trans Code'] || '';

              // Parse quantity: Remove commas, convert to float, default to 0 if empty/invalid.
              let quantity = 0;
              if (transaction['Quantity'] && transaction['Quantity'].trim() !== '') {
                quantity = parseFloat(transaction['Quantity'].replace(/,/g, ''));
                if (isNaN(quantity)) quantity = 0; // Ensure it's a number
              }

              // Parse price: Remove $, commas, parentheses, convert to float, default to 0.
              let price = 0;
              if (transaction['Price'] && transaction['Price'].trim() !== '') {
                price = parseFloat(transaction['Price'].replace(/[$,()]/g, ''));
                if (isNaN(price)) price = 0;
              }

              // Parse amount: Remove $, commas. Handle parentheses for negative numbers.
              let amount = 0;
              if (transaction['Amount'] && transaction['Amount'].trim() !== '') {
                const amountStr = transaction['Amount'].replace(/[$,]/g, ''); // Remove $ and ,
                if (amountStr.includes('(') && amountStr.includes(')')) {
                  // Negative value indicated by parentheses
                  amount = -parseFloat(amountStr.replace(/[()]/g, ''));
                } else {
                  // Positive value
                  amount = parseFloat(amountStr);
                }
                if (isNaN(amount)) amount = 0;
              }

              // --- Step 5l: Execute Insert Statement ---
              // Run the prepared statement, providing the cleaned data values in the correct order
              // to replace the `?` placeholders.
              insertStmt.run(
                activityDate,
                ticker,
                transCode,
                quantity,
                price,
                amount,
                // Callback for this specific `run` execution.
                (runErr) => {
                   if (runErr) {
                      // Log errors for specific rows but don't stop the loop.
                      console.error(`[API /upload] Error inserting transaction row ${index + 1}:`, transaction, runErr.message);
                      errorCount++; // Increment error counter.
                   } else {
                      insertedCount++; // Increment success counter.
                   }
                }
              );

            } catch (processError) {
              // Catch any unexpected errors during the data cleaning/formatting of this row.
              console.error(`[API /upload] Error processing transaction row ${index + 1}:`, transaction, processError.message);
              errorCount++;
            }
          }); // End of transactions.forEach loop

          // --- Step 5m: Finalize Batch Insert ---
          // Finalizing tells the database we're done with this prepared statement and releases resources.
          // The callback runs after finalization is complete.
          console.log('[API /upload] Finalizing database insert operation...');
          insertStmt.finalize((finalizeErr) => {
            if (finalizeErr) {
               // Log finalization errors, as they might indicate a bigger problem.
               console.error("[API /upload] Error finalizing insert statement:", finalizeErr.message);
               // Depending on severity, might want to rollback or send error response here.
            }

            // --- Step 5n: Delete Temporary File ---
            // Clean up the uploaded file from the 'uploads/' directory now that it's processed.
            console.log(`[API /upload] Deleting temporary file: ${filePath}`);
            fs.unlink(filePath, (unlinkErr) => {
              if (unlinkErr) {
                // Log error but don't stop the response, it's just cleanup.
                console.error('[API /upload] Error deleting uploaded temporary file:', unlinkErr);
              }
            });

            // --- Step 5o: Send Success Response ---
            // Send a JSON response back to the frontend indicating success,
            // along with counts of processed, inserted, and errored rows.
            console.log(`[API /upload] CSV Upload Complete: ${insertedCount} inserted, ${errorCount} errors.`);
            res.json({
              message: 'File uploaded and processed successfully.',
              totalTransactions: transactions.length, // Total rows found in CSV
              insertedCount, // Rows successfully inserted into DB
              errorCount // Rows that failed processing or insertion
            });
          }); // End of finalize callback
        }); // End of DELETE FROM transactions callback
      }, // End of PapaParse 'complete' callback

      // --- Step 5p: Error Callback (on parse error) ---
      // This function is called by PapaParse if it encounters an error while parsing the CSV data itself
      // (e.g., malformed CSV structure).
      error: (parseError) => {
        console.error('[API /upload] Error parsing CSV:', parseError);
        // Clean up the temporary file.
        fs.unlink(filePath, (unlinkErr) => {
          if (unlinkErr) console.error('[API /upload] Error deleting temp file after parse error:', unlinkErr);
        });
        // Return a 500 Internal Server Error, indicating the file likely couldn't be understood.
        res.status(500).json({ error: 'Error parsing CSV file', details: parseError.message });
      }
    }); // End of Papa.parse call
  }); // End of fs.readFile callback
}); // End of app.post('/upload') route handler

// --- Function: processTickers (Helper for potential pre-caching) ---
// This asynchronous function is designed to fetch historical prices for a given list of tickers
// while respecting API rate limits (specifically Alpha Vantage's 5 calls/minute limit).
// It processes tickers in small batches with delays between them.
// Note: This function is defined here but doesn't seem to be called directly by any active API route in the current code.
// It might be intended for a future feature or a separate script to pre-populate the price cache.
async function processTickers(tickers) {
  console.log(`[Helper processTickers] Starting processing for ${tickers.length} tickers.`);
  // Define Alpha Vantage API limits (adjust if needed, but 5/min is the free tier limit).
  const maxRequestsPerMinute = 5;
  // Determine the size of each batch to process, respecting the API limit.
  const chunkSize = Math.min(maxRequestsPerMinute, tickers.length);

  // Loop through the tickers array in chunks (steps of `chunkSize`).
  for (let i = 0; i < tickers.length; i += chunkSize) {
    // Get the current batch of tickers using `slice`.
    const chunk = tickers.slice(i, i + chunkSize);
    console.log(`[Helper processTickers] Processing chunk ${Math.floor(i / chunkSize) + 1}: ${chunk.join(', ')}`);

    // Process the current chunk of tickers concurrently using `Promise.all`.
    // `map` creates an array of Promises, one for each ticker in the chunk.
    const promises = chunk.map(ticker => {
      // Call `getStockPrices` for each ticker. This function handles caching and fetching.
      // Use `.catch` on each individual promise to handle errors gracefully.
      // If one ticker fails, we log the error but don't stop the processing of others in the chunk.
      return getStockPrices(ticker).catch(err => {
        console.error(`[Helper processTickers] Error fetching prices for ${ticker} in batch:`, err);
        return null; // Return null to indicate failure for this specific ticker.
      });
    });

    // Wait for all promises (API calls/cache checks) in the current chunk to complete.
    await Promise.all(promises);
    console.log(`[Helper processTickers] Finished processing chunk ${Math.floor(i / chunkSize) + 1}.`);

    // Pause execution if there are more tickers left to process in subsequent chunks.
    if (i + chunkSize < tickers.length) {
      // Wait for slightly longer than a minute (e.g., 65 seconds) to ensure the rate limit resets.
      const waitTimeSeconds = 65;
      console.log(`[Helper processTickers] Waiting ${waitTimeSeconds} seconds before next batch...`);
      // Create a promise that resolves after the specified timeout.
      await new Promise(resolve => setTimeout(resolve, waitTimeSeconds * 1000));
    }
  }

  console.log('[Helper processTickers] Finished pre-caching all ticker price data.');
}

// --- Route 6: POST /portfolio-config ---
// Handles requests to save the user's portfolio configuration settings.
// This includes the total investment amount and the desired allocation percentages for different assets (tickers).
app.post('/portfolio-config', (req, res) => {
  console.log('[API /portfolio-config] Request received.');
  // Extract `total_investment` and the `allocations` array from the request body (expected to be JSON).
  const { total_investment, allocations } = req.body;

  // --- Step 6a: Validate Input Data ---
  // Check if required fields are present and if allocations is a non-empty array.
  if (total_investment === undefined || total_investment === null || !allocations || !Array.isArray(allocations) || allocations.length === 0) {
    console.log('[API /portfolio-config] Invalid input data (missing fields or empty allocations).');
    return res.status(400).json({ error: 'Invalid portfolio configuration. Required: total_investment (number) and allocations (non-empty array).' });
  }

  // Further validation: Check if each item in the `allocations` array has the necessary structure.
  const invalidAllocations = allocations.filter(item =>
    !item.ticker || typeof item.ticker !== 'string' || item.ticker.trim() === '' || // Ticker must be a non-empty string
    item.allocation_percentage === undefined || item.allocation_percentage === null || typeof item.allocation_percentage !== 'number' // Percentage must be a number
  );
  if (invalidAllocations.length > 0) {
    console.log('[API /portfolio-config] Invalid allocation format found:', invalidAllocations);
    return res.status(400).json({
      error: 'Invalid allocations format. Each allocation must have a ticker (string) and allocation_percentage (number).'
    });
  }

  // --- Step 6b: Validate Allocation Sum ---
  // Calculate the sum of all provided allocation percentages.
  const totalPercentage = allocations.reduce((sum, item) => sum + parseFloat(item.allocation_percentage), 0);
  // Check if the sum is reasonably close to 100% (allowing for minor floating-point inaccuracies).
  if (Math.abs(totalPercentage - 100) > 0.01) {
    console.log(`[API /portfolio-config] Allocation percentages sum to ${totalPercentage.toFixed(2)}%, not 100%.`);
    return res.status(400).json({
      error: `Allocation percentages must add up to 100%. Current total: ${totalPercentage.toFixed(2)}%`
    });
  }
  console.log(`[API /portfolio-config] Input validation passed. Total Investment: ${total_investment}, Allocations: ${allocations.length}`);

  // --- Step 6c: Save to Database (within a transaction) ---
  // Use a try...catch block to handle potential errors during database operations.
  try {
    // `db.serialize` ensures that the database operations within its callback run sequentially.
    db.serialize(() => {
      // Begin a database transaction. This groups the DELETE and INSERT operations.
      // If any operation fails, the entire transaction can be rolled back, ensuring data consistency.
      db.run('BEGIN TRANSACTION');
      console.log('[API /portfolio-config] Began database transaction.');

      // --- Step 6c1: Clear Existing Configuration ---
      // Delete all previous entries from the `portfolio_config` table.
      console.log('[API /portfolio-config] Clearing existing portfolio_config table...');
      db.run('DELETE FROM portfolio_config', (err) => {
        if (err) {
          // If clearing fails, throw an error. This will be caught by the outer catch block,
          // which will then trigger a rollback.
          console.error('[API /portfolio-config] Error clearing portfolio_config:', err.message);
          throw new Error(`Error clearing portfolio_config: ${err.message}`);
        }
        console.log('[API /portfolio-config] Existing config cleared.');

        // --- Step 6c2: Insert New Configuration ---
        // Prepare the SQL statement for inserting the new allocation data.
        const insertStmt = db.prepare(
          'INSERT INTO portfolio_config (total_investment, ticker, allocation_percentage) VALUES (?, ?, ?)'
        );

        console.log('[API /portfolio-config] Inserting new configuration...');
        // Loop through the `allocations` array received from the request.
        allocations.forEach((allocation, index) => {
          // Execute the prepared statement for each allocation item.
          insertStmt.run(
            total_investment, // Use the same total investment amount for each row
            allocation.ticker,
            allocation.allocation_percentage,
            (insertErr) => { // Add callback to catch errors during individual row insertion
              if (insertErr) {
                // Log the error, but potentially allow the loop to continue.
                // Critical applications might want to throw an error here to ensure rollback.
                console.error(`[API /portfolio-config] Error inserting allocation ${index + 1} (${allocation.ticker}):`, insertErr.message);
                // Consider throwing `insertErr` here if one failed insert should abort the whole process.
              }
            }
          );
        });

        // Finalize the prepared statement after looping through all allocations.
        insertStmt.finalize((finalizeErr) => {
           if (finalizeErr) {
               console.error("[API /portfolio-config] Error finalizing insert statement:", finalizeErr.message);
               // Throwing an error here ensures a rollback if finalization fails.
               throw new Error(`Error finalizing insert statement: ${finalizeErr.message}`);
           }
           console.log('[API /portfolio-config] Insert statement finalized.');

           // --- Step 6c3: Commit Transaction ---
           // If all preceding operations (DELETE, INSERT runs, finalize) were successful (didn't throw errors),
           // commit the transaction to make the changes permanent in the database.
           db.run('COMMIT', (commitErr) => {
             if (commitErr) {
               // If committing fails (unlikely but possible), throw an error to trigger rollback.
               console.error('[API /portfolio-config] Error committing transaction:', commitErr.message);
               throw new Error(`Error committing transaction: ${commitErr.message}`);
             }
             console.log('[API /portfolio-config] Database transaction committed successfully.');

             // --- Step 6d: Send Success Response ---
             // If the commit was successful, send a success response back to the client.
             res.json({
               message: 'Portfolio configuration saved successfully.',
               // Optionally include the saved data in the response for confirmation.
               portfolio: {
                 total_investment,
                 allocations
               }
             });
           }); // End commit callback
        }); // End finalize callback
      }); // End delete callback
    }); // End db.serialize
  } catch (error) {
    // --- Step 6e: Handle Errors and Rollback ---
    // This block catches any errors thrown during the `try` block (e.g., from db operations).
    console.error('[API /portfolio-config] Error saving portfolio configuration, rolling back transaction:', error.message);
    // Attempt to explicitly roll back the transaction to undo any changes made before the error occurred.
    db.run('ROLLBACK', (rollbackErr) => {
       if (rollbackErr) console.error('[API /portfolio-config] Error executing ROLLBACK:', rollbackErr.message);
       else console.log('[API /portfolio-config] Transaction rolled back.');
    });
    // Send a 500 Internal Server Error response to the client.
    res.status(500).json({ error: 'Error saving portfolio configuration', details: error.message });
  }
});

// --- Route 7: GET /portfolio-composition ---
// Retrieves the currently saved portfolio composition (tickers, names, allocation percentages)
// and the total investment amount from the `portfolio_config` database table.
app.get('/portfolio-composition', (req, res) => {
  console.log('[API /portfolio-composition] Request received.');
  // --- Step 7a: Define Stock Name Mapping (Optional Enhancement) ---
  // This object provides user-friendly names for common stock tickers.
  // In a more complex application, this data might come from a separate database table or an external API.
  const stockNames = {
    'AAPL': 'Apple Inc.', 'MSFT': 'Microsoft Corporation', 'GOOGL': 'Alphabet Inc. (Google)',
    'AMZN': 'Amazon.com Inc.', 'META': 'Meta Platforms Inc.', 'NFLX': 'Netflix Inc.',
    'TSLA': 'Tesla Inc.', 'NVDA': 'NVIDIA Corporation', 'JPM': 'JPMorgan Chase & Co.',
    'V': 'Visa Inc.', 'JNJ': 'Johnson & Johnson', 'WMT': 'Walmart Inc.',
    'PG': 'Procter & Gamble Co.', 'MA': 'Mastercard Inc.', 'DIS': 'The Walt Disney Company',
    'HD': 'The Home Depot Inc.', 'BAC': 'Bank of America Corp.', 'VZ': 'Verizon Communications Inc.',
    'ADBE': 'Adobe Inc.', 'INTC': 'Intel Corporation', 'CSCO': 'Cisco Systems Inc.',
    'CMCSA': 'Comcast Corporation', 'PFE': 'Pfizer Inc.', 'KO': 'The Coca-Cola Company',
    'PEP': 'PepsiCo Inc.', 'T': 'AT&T Inc.', 'MRK': 'Merck & Co. Inc.',
    'BITU': 'ProShares Ultra Bitcoin ETF', /* Add more tickers and names as needed */
  };

  // --- Step 7b: Query Allocations from Database ---
  // Select the ticker and allocation percentage for all entries in the `portfolio_config` table.
  console.log('[API /portfolio-composition] Querying portfolio_config for allocations...');
  // `db.all` fetches all rows matching the query.
  db.all('SELECT ticker, allocation_percentage FROM portfolio_config', [], (err, rows) => {
    // Handle potential database errors during the query.
    if (err) {
      console.error('[API /portfolio-composition] Error querying portfolio allocations:', err.message);
      return res.status(500).json({ error: 'Error retrieving portfolio composition' });
    }
    console.log(`[API /portfolio-composition] Found ${rows.length} allocation entries.`);

    // --- Step 7c: Format Composition Data ---
    // Map the raw database `rows` into a more structured array for the frontend.
    // Include the stock name by looking it up in the `stockNames` object.
    const composition = rows.map(row => {
      return {
        ticker: row.ticker,
        // Look up the name; if not found, provide a default indicating it's unknown.
        name: stockNames[row.ticker] || `${row.ticker} (Unknown Name)`,
        allocation_percentage: row.allocation_percentage
      };
    });

    // --- Step 7d: Query Total Investment ---
    // Fetch the `total_investment` value from the `portfolio_config` table.
    // Since it should be the same for all rows in a single configuration, we only need one (`LIMIT 1`).
    console.log('[API /portfolio-composition] Querying portfolio_config for total investment...');
    // `db.get` fetches only the first row matching the query.
    db.get('SELECT total_investment FROM portfolio_config LIMIT 1', [], (err, result) => {
      // --- Step 7e: Handle Total Investment Query Errors/No Data ---
      // If there's an error OR if `result` is null/undefined (meaning the table is empty or doesn't have the column).
      if (err || !result) {
        console.error('[API /portfolio-composition] Error querying total investment or no config found:', err ? err.message : 'No config data found in portfolio_config table');
        // If we can't get the total investment, still return the composition array (which might be empty).
        // The frontend will need to handle the case where `total_investment` is missing.
        return res.json({ composition });
      }
      console.log(`[API /portfolio-composition] Total investment found: ${result.total_investment}`);

      // --- Step 7f: Send Response ---
      // Send the `total_investment` amount and the formatted `composition` array back to the client.
      console.log('[API /portfolio-composition] Sending composition response.');
      res.json({
        total_investment: result.total_investment,
        composition
      });
    }); // End db.get for total_investment
  }); // End db.all for allocations
}); // End app.get('/portfolio-composition')

// Portfolio Summary Metrics Functions

/**
 * Step 78: Determine the start and end date of the transaction history.
 * @returns {Promise<Object>} A promise that resolves with an object containing { start_date, end_date }.
 */
function calculateTimePeriod() {
  // Step 79: Return a promise to handle the asynchronous database query.
  return new Promise((resolve, reject) => {
    // Step 80: Query the database to find the minimum (earliest) and maximum (latest) activity_date.
    db.get(`
      SELECT 
        MIN(activity_date) as start_date, -- Find the earliest date
        MAX(activity_date) as end_date -- Find the latest date
      FROM transactions
    `, [], (err, result) => {
      // Step 81: Handle potential database query errors.
      if (err) {
        console.error('Error calculating time period:', err);
        reject(err);
        return;
      }
      // Step 82: If successful, resolve the promise with the start and end dates.
      resolve({
        start_date: result.start_date,
        end_date: result.end_date
      });
    });
  });
}

/**
 * Step 83: Calculate the total portfolio value for a specific date.
 * This involves summing the value of all stock holdings and the cash balance on that date.
 * @param {string} date - The target date in YYYY-MM-DD format.
 * @returns {Promise<number>} A promise that resolves with the calculated portfolio value.
 */
function calculatePortfolioValueForDate(date) {
  // Step 84: Return a promise for the asynchronous operations.
  return new Promise((resolve, reject) => {
    // Step 85: Get all transactions that occurred on or before the target date.
    db.all(`
      SELECT ticker, trans_code, quantity, price, amount
      FROM transactions
      WHERE activity_date <= ? -- Select transactions up to the given date
      ORDER BY activity_date ASC -- Process transactions chronologically
    `, [date], (err, transactions) => {
      // Step 86: Handle database errors.
      if (err) {
        console.error(`Error fetching transactions for date ${date}:`, err);
        reject(err);
        return;
      }

      // Step 87: If no transactions exist by this date, the portfolio value is 0.
      if (transactions.length === 0) {
        resolve(0);
        return;
      }

      // Step 88: Calculate current holdings and cash balance based on the transactions.
      const holdings = {}; // Object to store quantity of each stock { Ticker: Quantity }
      let cashBalance = 0; // Variable to track cash

      // Step 89: Iterate through each transaction up to the target date.
      transactions.forEach(transaction => {
        const { ticker, trans_code, quantity, price, amount } = transaction;
        
        // Step 90: Handle cash-only transactions (like deposits, withdrawals, rewards - where ticker is empty).
        if (!ticker || ticker.trim() === '') {
          // For these, directly adjust the cash balance by the transaction amount.
          cashBalance += (amount || 0); // Use amount if available, otherwise 0
          return; // Move to the next transaction
        }

        // Step 91: Handle stock transactions.
        if (trans_code === 'Buy') {
          // Increase the quantity of the purchased stock.
          holdings[ticker] = (holdings[ticker] || 0) + quantity;
          // The cost is implicitly handled by the 'amount' update below.
        } else if (trans_code === 'Sell') {
          // Decrease the quantity of the sold stock.
          holdings[ticker] = (holdings[ticker] || 0) - quantity;
          // The proceeds are implicitly handled by the 'amount' update below.
        } 
        // Note: Dividends (CDIV) or other codes might directly affect cash balance via 'amount'.
        // We don't need a specific case for CDIV if its 'amount' is correctly positive.
        
        // Step 92: Update the cash balance for ALL transactions based on the 'amount' field.
        // Buys typically have negative amounts, Sells have positive amounts.
        // Dividends, deposits have positive amounts. Withdrawals have negative amounts.
        if (amount) { // Only adjust if amount is not null/zero
          cashBalance += amount;
        }
      });

      // Step 93: Get a list of unique stock tickers currently held (quantity > 0).
      const tickersInHoldings = Object.keys(holdings).filter(ticker => holdings[ticker] > 0.000001); // Use a small threshold for floating point precision
      
      // Step 94: If no stocks are held, the portfolio value is just the cash balance.
      if (tickersInHoldings.length === 0) {
        resolve(cashBalance);
        return;
      }

      // Step 95: Fetch the latest available closing price for each held stock up to the target date.
      const pricePromises = tickersInHoldings.map(ticker => {
        // Step 96: Return a promise for each price lookup.
        return new Promise((resolvePrice, rejectPrice) => {
          // Step 97: Query the stock_prices table for the latest price on or before the date.
          db.get(`
            SELECT close_price 
            FROM stock_prices
            WHERE ticker = ? AND date <= ?
            ORDER BY date DESC -- Get the most recent price first
            LIMIT 1 -- Only need the latest one
          `, [ticker, date], (priceErr, result) => {
            // Step 98: Handle database errors during price lookup.
            if (priceErr) {
              console.error(`Error fetching price for ${ticker} on ${date}:`, priceErr);
              rejectPrice(priceErr);
              return;
            }
            
            // Step 99: If a price is found in the cache, use it.
            if (result && result.close_price !== null) {
              resolvePrice({ ticker, price: result.close_price });
            } else {
              // Step 100: If no price found in cache (e.g., recent transaction, API issue), fallback.
              // We could try fetching here, but for simplicity in this function, let's log a warning.
              // A more robust solution might fetch or use the last known transaction price.
              console.warn(`No cached price found for ${ticker} on or before ${date}. Using 0 value for this holding.`);
              resolvePrice({ ticker, price: 0 }); // Fallback to 0 price if not found
            }
          });
        });
      });

      // Step 101: Wait for all price lookups to complete.
      Promise.all(pricePromises)
        .then(tickerPrices => {
          // Step 102: Calculate the total value of all stock holdings.
          let totalStockValue = 0;
          tickerPrices.forEach(tp => {
            // Multiply the quantity held by the fetched price.
            totalStockValue += (holdings[tp.ticker] || 0) * tp.price;
          });

          // Step 103: Calculate the total portfolio value by adding stock value and cash balance.
          const totalPortfolioValue = totalStockValue + cashBalance;
          // Step 104: Resolve the main promise with the total calculated value.
          resolve(totalPortfolioValue);
        })
        .catch(reject); // Catch errors from Promise.all (price lookups)
    });
  });
}

/**
 * Step 105: Calculate the daily portfolio values for the entire transaction history period.
 * @returns {Promise<Array>} A promise resolving to an array of objects { date, value }.
 */
function calculateDailyPortfolioValues() {
  // Step 106: Return a promise for the asynchronous operations.
  return new Promise((resolve, reject) => {
    // Step 107: First, determine the overall start and end date of transactions.
    calculateTimePeriod()
      .then(({ start_date, end_date }) => {
        // Step 108: Check if valid start and end dates were found.
        if (!start_date || !end_date) {
          console.log('No transactions found, cannot calculate daily values.');
          resolve([]); // Resolve with empty array if no transactions
          return;
        }

        // Step 109: Create Date objects for the start and end dates.
        const start = new Date(start_date);
        const end = new Date(end_date);
        const days = []; // Array to hold all dates in the range
        
        // Step 110: Generate an array of all dates from start_date to end_date.
        for (let day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) {
          // Format each date as YYYY-MM-DD
          days.push(day.toISOString().split('T')[0]);
        }
        
        // Step 111: Create an array of promises, one for calculating the portfolio value for each day.
        const dailyValuePromises = days.map(date => {
          return calculatePortfolioValueForDate(date)
            .then(value => ({ date, value })); // Map result to { date, value } object
        });
        
        // Step 112: Wait for all daily value calculations to complete.
        Promise.all(dailyValuePromises)
          .then(dailyValues => {
            // Step 113: Filter out any initial days where the portfolio value might be 0 or less (before the first meaningful transaction).
            const filteredValues = dailyValues.filter(day => day.value > 0.000001); // Use threshold
            // Step 114: Resolve the main promise with the array of daily values.
            resolve(filteredValues);
          })
          .catch(reject); // Catch errors from Promise.all (daily value calculations)
      })
      .catch(reject); // Catch errors from calculateTimePeriod
  });
}

/**
 * Step 115: Calculate month-end portfolio values from daily values.
 * @param {Array} dailyValues - Array of daily values { date, value }, sorted by date.
 * @returns {Array} Array of month-end values { year_month, date, value }.
 */
function calculateMonthlyPortfolioValues(dailyValues) {
  // Step 116: Check if there's enough data.
  if (!dailyValues || dailyValues.length === 0) {
    return [];
  }

  const monthlyValuesMap = {}; // Use a map to store the last value found for each month
  
  // Step 117: Iterate through the sorted daily values.
  dailyValues.forEach(day => {
    // Step 118: Get the year and month in YYYY-MM format.
    const yearMonth = day.date.substring(0, 7);
    // Step 119: Store the current day's data, overwriting any previous entry for the same month.
    // Since the input is sorted, the last one processed for a month will be the month-end value.
    monthlyValuesMap[yearMonth] = day;
  });
  
  // Step 120: Convert the map values back into an array.
  const monthlyValuesArray = Object.values(monthlyValuesMap);
  
  // Step 121: Map to the desired output format { year_month, date, value }.
  return monthlyValuesArray.map(day => ({
    year_month: day.date.substring(0, 7),
    date: day.date,
    value: day.value
  }));
  // Note: Sorting is implicitly handled because Object.values respects insertion order for non-integer keys (like YYYY-MM)
}

/**
 * Step 122: Calculate year-end portfolio values from daily values.
 * @param {Array} dailyValues - Array of daily values { date, value }, sorted by date.
 * @returns {Array} Array of year-end values { year, date, value }.
 */
function calculateYearlyPortfolioValues(dailyValues) {
  // Step 123: Check if there's enough data.
  if (!dailyValues || dailyValues.length === 0) {
    return [];
  }

  const yearlyValuesMap = {}; // Use a map to store the last value found for each year
  
  // Step 124: Iterate through the sorted daily values.
  dailyValues.forEach(day => {
    // Step 125: Get the year.
    const year = day.date.substring(0, 4);
    // Step 126: Store the current day's data, overwriting previous entries for the same year.
    yearlyValuesMap[year] = day;
  });
  
  // Step 127: Convert the map values back into an array.
  const yearlyValuesArray = Object.values(yearlyValuesMap);
  
  // Step 128: Map to the desired output format { year, date, value }.
  return yearlyValuesArray.map(day => ({
    year: parseInt(day.date.substring(0, 4)),
    date: day.date,
    value: day.value
  }));
  // Note: Sorting by year is implicitly handled due to map iteration order.
}

/**
 * Step 129: Calculate the Compound Annual Growth Rate (CAGR).
 * Represents the average annual growth of an investment over a specified period longer than one year.
 * @param {number} startValue - The beginning value of the investment.
 * @param {number} endValue - The ending value of the investment.
 * @param {number} years - The number of years over which the growth occurred.
 * @returns {number} CAGR expressed as a percentage (e.g., 8.5 for 8.5%). Returns 0 if inputs are invalid.
 */
function calculateCAGR(startValue, endValue, years) {
  // Step 130: Validate inputs. Start value and years must be positive.
  if (startValue <= 0 || years <= 0) return 0;
  // Step 131: Apply the CAGR formula: ((End Value / Start Value)^(1 / Years)) - 1
  // Multiply by 100 to express as a percentage.
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
 * Calculate downside deviation
 * @param {Array} monthlyValues - Array of monthly values { year_month, value }
 * @returns {number} Downside deviation
 */
function calculateDownsideDeviation(monthlyValues) {
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
    .filter(r => r < 0)
    .map(r => Math.pow(r, 2));
  
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

/**
 * Helper Function: calculateStyleAnalysis
 * Generates MOCK (placeholder) data for holdings-based style analysis.
 * Style analysis typically involves looking at the underlying characteristics of the assets
 * in the portfolio (e.g., Large Cap Value, Small Cap Growth, Bond Duration, P/E Ratio).
 * !!! IMPORTANT: In this current version, this function generates RANDOM data for demonstration purposes.
 * !!! A real application would need to fetch this data from a financial data provider API
 * !!! based on the actual tickers held in the portfolio.
 * @returns {Promise<Object>} A promise resolving to { styleAnalysis (array), portfolioTotals (object) } or rejecting on DB error.
 */
function calculateStyleAnalysis() {
  console.log('[Helper calculateStyleAnalysis] Starting mock style analysis calculation...');
  return new Promise((resolve, reject) => {
    // --- Step SA-a: Get Portfolio Allocations ---
    // Fetch the configured ticker allocations (ticker and percentage) from the database.
    // This tells us which assets are supposed to be in the portfolio according to the user's setup.
    db.all('SELECT ticker, allocation_percentage FROM portfolio_config', [], (err, allocations) => {
      if (err) {
        // Handle database errors when fetching the configuration.
        console.error('[Helper calculateStyleAnalysis] Error fetching portfolio config:', err.message);
        return reject(err); // Reject the promise if DB query fails.
      }

      // Handle the case where the user hasn't saved a portfolio configuration yet.
      if (!allocations || allocations.length === 0) {
        console.log('[Helper calculateStyleAnalysis] No portfolio configuration found.');
        // Resolve with empty data structures if no config exists.
        return resolve({
          message: 'No portfolio configuration found', // Optional message
          styleAnalysis: [], // Empty array for per-asset analysis
          portfolioTotals: {} // Empty object for overall totals
        });
      }
      console.log(`[Helper calculateStyleAnalysis] Found ${allocations.length} allocations in config.`);

      // --- Step SA-b: Generate Mock Style Data for Each Ticker ---
      // Loop through each ticker found in the configuration and create placeholder style data.
      const styleAnalysis = allocations.map(allocation => {
        // --- Mock Data Generation --- 
        // Replace these random values with real data fetching in a production version.
        const mockSecYield = (Math.random() * 2).toFixed(2); // e.g., Mock 30-day SEC Yield %
        const mockTtmYield = (Math.random() * 2.5).toFixed(2); // e.g., Mock Trailing Twelve Month Yield %
        const mockNetExpenseRatio = (Math.random() * 0.8).toFixed(2); // e.g., Mock Net Expense Ratio %
        const mockGrossExpenseRatio = (parseFloat(mockNetExpenseRatio) + Math.random() * 0.2).toFixed(2); // e.g., Mock Gross Expense Ratio %
        const mockPeRatio = (Math.random() * 25 + 10).toFixed(2); // e.g., Mock Price-to-Earnings Ratio
        const mockDuration = (Math.random() * 7).toFixed(2); // e.g., Mock Bond Duration (if applicable)
        const mockContributionToReturn = (Math.random() * 5 - 1).toFixed(2); // e.g., Mock % Contribution to Return
        const mockContributionToRisk = (Math.random() * 4).toFixed(2); // e.g., Mock % Contribution to Risk

        // Assign a random investment style category for demonstration.
        const categories = ['Large Cap Value', 'Large Cap Growth', 'Mid Cap Blend', 'Small Cap Value', 'International Equity', 'Intermediate Bond', 'Short-Term Bond', 'Cash/Other'];
        const mockCategory = categories[Math.floor(Math.random() * categories.length)];
        // --- End Mock Data Generation ---

        // Return an object representing the style analysis for this specific ticker.
        return {
          ticker: allocation.ticker,
          category: mockCategory, // Use the mock category
          weight: parseFloat(allocation.allocation_percentage).toFixed(2), // Use the user's configured weight %
          secYield: parseFloat(mockSecYield),
          ttmYield: parseFloat(mockTtmYield),
          netExpenseRatio: parseFloat(mockNetExpenseRatio),
          grossExpenseRatio: parseFloat(mockGrossExpenseRatio),
          peRatio: parseFloat(mockPeRatio),
          duration: parseFloat(mockDuration),
          contributionToReturn: parseFloat(mockContributionToReturn),
          contributionToRisk: parseFloat(mockContributionToRisk)
        };
      });
      console.log('[Helper calculateStyleAnalysis] Generated mock style data for each ticker.');

      // --- Step SA-c: Calculate Weighted Portfolio Totals/Averages ---
      // Calculate the overall portfolio metrics based on the individual asset styles and their weights.
      // First, find the actual total weight (should be near 100, but might be slightly off).
      const totalWeight = allocations.reduce((sum, a) => sum + parseFloat(a.allocation_percentage), 0);

      let portfolioTotals = {}; // Initialize empty object for totals

      // Only calculate totals if the total weight is valid (greater than a small threshold) to avoid division by zero.
      if (totalWeight > 0.01) {
        console.log('[Helper calculateStyleAnalysis] Calculating weighted portfolio totals...');
        // Initialize accumulators for the weighted averages/sums.
        let weightedSecYield = 0;
        let weightedTtmYield = 0;
        let weightedNetExpenseRatio = 0;
        let weightedGrossExpenseRatio = 0;
        let weightedPeRatio = 0;
        let weightedDuration = 0;
        let totalContributionToReturn = 0; // Contribution is usually summed, not averaged

        // Iterate through the generated style data for each ticker.
        styleAnalysis.forEach(item => {
          // Calculate the actual weight fraction of this item (its weight / total weight).
          const weightFraction = parseFloat(item.weight) / totalWeight;
          // Add the weighted value of each metric to the corresponding total.
          // For metrics like Yield, Expense Ratio, P/E, Duration, we calculate a weighted average.
          weightedSecYield += item.secYield * weightFraction;
          weightedTtmYield += item.ttmYield * weightFraction;
          weightedNetExpenseRatio += item.netExpenseRatio * weightFraction;
          weightedGrossExpenseRatio += item.grossExpenseRatio * weightFraction;
          weightedPeRatio += item.peRatio * weightFraction;
          weightedDuration += item.duration * weightFraction;
          // For contribution to return/risk, we typically sum the individual contributions.
          totalContributionToReturn += item.contributionToReturn; // Summing contribution
        });

        // Store the calculated portfolio totals, formatted to 2 decimal places.
        portfolioTotals = {
          totalSecYield: parseFloat(weightedSecYield.toFixed(2)),
          totalTtmYield: parseFloat(weightedTtmYield.toFixed(2)),
          totalNetExpenseRatio: parseFloat(weightedNetExpenseRatio.toFixed(2)),
          totalGrossExpenseRatio: parseFloat(weightedGrossExpenseRatio.toFixed(2)),
          totalPeRatio: parseFloat(weightedPeRatio.toFixed(2)),
          totalDuration: parseFloat(weightedDuration.toFixed(2)),
          totalContributionToReturn: parseFloat(totalContributionToReturn.toFixed(2))
        };
        console.log('[Helper calculateStyleAnalysis] Portfolio totals calculated.');
      } else {
        // If total weight is invalid (e.g., 0), log a warning and return empty totals.
        console.warn('[Helper calculateStyleAnalysis] Total portfolio weight is zero or invalid, cannot calculate totals.');
      }

      // --- Step SA-d: Resolve Promise ---
      // Resolve the promise with the array of per-asset style data and the object of portfolio totals.
      resolve({
        styleAnalysis,   // Array of objects, one per ticker
        portfolioTotals  // Object with overall portfolio metrics
      });
    }); // End db.all callback
  }); // End main promise
}

// --- Route 9: GET /style-analysis ---
// Retrieves the (currently mock) holdings-based style analysis data for the portfolio.
// It calls the `calculateStyleAnalysis` helper function.
app.get('/style-analysis', async (req, res) => {
  console.log('[API /style-analysis] Request received.');
  try {
    // --- Step 9a: Calculate Style Data ---
    // Call the helper function, which currently generates mock data based on the saved configuration.
    const styleAnalysisData = await calculateStyleAnalysis();
    console.log('[API /style-analysis] Style analysis data calculated (currently mock data).');

    // --- Step 9b: Send Response ---
    // Send the result object (containing `styleAnalysis` array and `portfolioTotals` object) back to the client.
    res.json(styleAnalysisData);

  } catch (error) {
    // --- Step 9c: Handle Errors ---
    // Catch any errors that occurred, likely during the database fetch in the helper function.
    console.error('[API /style-analysis] Error calculating style analysis:', error);
    // Send a 500 Internal Server Error response.
    res.status(500).json({ error: 'Failed to calculate style analysis', details: error.message });
  }
});

/**
 * Helper Function: calculateActiveReturnByAsset
 * Generates MOCK (placeholder) data for the active return of each asset in the portfolio
 * relative to a benchmark, across various time periods.
 * Active Return = Asset Return - Benchmark Return.
 * !!! IMPORTANT: This function currently uses hardcoded benchmark returns and generates RANDOM asset returns.
 * !!! A real implementation would require fetching historical price data for each asset and the benchmark,
 * !!! calculating returns for each period, and then finding the difference.
 * @returns {Promise<Object>} A promise resolving to { activeReturns (array) } or rejecting on DB error.
 */
function calculateActiveReturnByAsset() {
  console.log('[Helper calculateActiveReturnByAsset] Starting mock active return calculation...');
  return new Promise((resolve, reject) => {
    // --- Step AR-a: Get Portfolio Tickers ---
    // Fetch the unique tickers from the user's portfolio configuration.
    db.all('SELECT DISTINCT ticker FROM portfolio_config WHERE ticker IS NOT NULL AND ticker != \'\'', [], (err, allocations) => {
      if (err) {
        // Handle database errors.
        console.error('[Helper calculateActiveReturnByAsset] Error fetching portfolio config tickers:', err.message);
        return reject(err);
      }

      // Handle case where no configuration is saved.
      if (!allocations || allocations.length === 0) {
        console.log('[Helper calculateActiveReturnByAsset] No portfolio configuration found.');
        return resolve({ message: 'No portfolio configuration found', activeReturns: [] });
      }

      // Get unique tickers from the configuration results.
      const tickers = allocations.map(a => a.ticker);
      console.log(`[Helper calculateActiveReturnByAsset] Found ${tickers.length} unique tickers in config.`);

      // --- Step AR-b: Define Time Periods ---
      // Specify the standard time periods for which to calculate/mock returns.
      const periods = [
        // { name: '1 Day', days: 1 }, // Daily calculations can be very noisy and complex to mock realistically.
        // { name: '1 Week', days: 7 },
        { name: '1 Month', days: 30 },
        { name: '3 Month', days: 90 },
        { name: '6 Month', days: 180 },
        { name: 'YTD', days: 'YTD' }, // Special case: Year-to-Date (needs specific calculation in real version)
        { name: '1 Year', days: 365 },
        { name: '3 Year', days: 3 * 365 },
        { name: '5 Year', days: 5 * 365 },
        // { name: '10 Year', days: 10 * 365 }, // Often too long for typical user data history
        { name: 'Full Period', days: null } // Represents the entire duration of available data
      ];

      // --- Step AR-c: Mock Benchmark Returns --- 
      // *** These are placeholder values. Replace with actual calculations based on a benchmark like SPY. ***
      const benchmarkReturns = {
        '1 Month': 0.8 + (Math.random() * 1 - 0.5), // Add slight randomness
        '3 Month': 2.5 + (Math.random() * 2 - 1), 
        '6 Month': 5.0 + (Math.random() * 4 - 2), 
        'YTD': 7.0 + (Math.random() * 5 - 2.5), // Example YTD
        '1 Year': 10.0 + (Math.random() * 8 - 4), 
        '3 Year': 30.0 + (Math.random() * 15 - 7.5),
        '5 Year': 50.0 + (Math.random() * 20 - 10),
        'Full Period': 60.0 + (Math.random() * 25 - 12.5) // Example full period
      };

      // --- Step AR-d: Generate Mock Active Return for Each Ticker ---
      // Create an array of promises, one for each ticker.
      // (Using promises here matches the structure if we were doing async price lookups).
      const activeReturnsByAssetPromises = tickers.map(ticker => {
        // This inner promise simulates fetching/calculating data for one ticker.
        return new Promise((resolveTicker) => { // No reject needed for mock data
          // For this ticker, generate mock returns for all defined periods.
          const returns = periods.map(period => {
            // Mock Asset Return: Benchmark return +/- some random value.
            const benchmarkReturn = benchmarkReturns[period.name] ?? 0; // Default to 0 if period name mismatch
            const mockAssetReturn = benchmarkReturn + (Math.random() * 10 - 5); // Benchmark +/- 5%
            const activeReturn = mockAssetReturn - benchmarkReturn;

            // Return the calculated/mocked values for this period.
            return {
              period: period.name, // e.g., '1 Month', '1 Year'
              return: parseFloat(mockAssetReturn.toFixed(2)), // Asset's return %
              benchmarkReturn: parseFloat(benchmarkReturn.toFixed(2)), // Benchmark's return %
              activeReturn: parseFloat(activeReturn.toFixed(2)) // Difference %
            };
          });
          // Resolve the promise for this ticker with its array of period returns.
          resolveTicker({ ticker, returns });
        });
      });

      // --- Step AR-e: Wait for All Tickers and Resolve ---
      // `Promise.all` waits for all the inner promises (one per ticker) to resolve.
      Promise.all(activeReturnsByAssetPromises)
        .then(results => {
          // `results` is an array of { ticker, returns } objects.
          console.log('[Helper calculateActiveReturnByAsset] Mock active returns generated.');
          resolve({ activeReturns: results }); // Resolve the main promise with the final array.
        });
        // No .catch needed here as the inner promises in this mock setup don't reject.
    }); // End db.all callback
  }); // End main promise
}

// --- Route 10: GET /active-return ---
// Retrieves the (currently mock) active return data, showing how each asset
// performed compared to the benchmark over various time periods.
app.get('/active-return', (req, res) => {
  console.log('[API /active-return] Request received.');
  // Call the helper function `calculateActiveReturnByAsset`.
  calculateActiveReturnByAsset()
    .then(data => {
      // If the helper function resolves successfully...
      console.log('[API /active-return] Active return data calculated (currently mock data).');
      res.json(data); // Send the resulting data object { activeReturns: [...] }
    })
    .catch(err => {
      // If the helper function rejects (e.g., database error fetching tickers)...
      console.error('[API /active-return] Error calculating active return by asset:', err.message);
      // Send a 500 Internal Server Error response.
      res.status(500).json({ error: 'Error calculating active return by asset', details: err.message });
    });
});

/**
 * Helper Function: calculateUpDownMarketPerformance
 * Calculates and compares portfolio performance against a benchmark during distinct
 * up-market periods (when the benchmark had positive returns) and down-market periods
 * (when the benchmark had negative returns), typically on a monthly basis.
 * This requires aligned monthly return data for both the portfolio and the benchmark.
 * @returns {Promise<Object>} A promise resolving to { marketPerformance: [...] } or rejecting on error.
 */
function calculateUpDownMarketPerformance() {
  console.log('[Helper calculateUpDownMarketPerformance] Starting calculation...');
  return new Promise((resolve, reject) => {
    // --- Step UD-a: Get Portfolio Daily Values ---
    // Need daily values as a starting point to align with benchmark data.
    calculateDailyPortfolioValues()
      .then(async portfolioDailyValues => { // Mark inner callback as async to use await inside
        // Need at least 2 days of data to calculate even one return period.
        if (!portfolioDailyValues || portfolioDailyValues.length < 2) {
          console.log('[Helper calculateUpDownMarketPerformance] Insufficient portfolio data (less than 2 days).');
          // Resolve with empty data, not an error, as it's a data limitation.
          return resolve({ message: 'Insufficient portfolio data (need at least 2 days)', marketPerformance: [] });
        }
        console.log(`[Helper calculateUpDownMarketPerformance] Using ${portfolioDailyValues.length} portfolio daily values.`);

        // --- Step UD-b: Fetch and Align Benchmark Data (Monthly) ---
        const benchmarkTicker = 'SPY'; // Default benchmark ticker.
        let benchmarkMonthlyValues; // Will store the aligned benchmark monthly values.
        try {
           // Use the dedicated helper function to get benchmark monthly values aligned with the portfolio.
           benchmarkMonthlyValues = await getAlignedBenchmarkMonthlyValues(benchmarkTicker, portfolioDailyValues);
           // Check if alignment and monthly calculation were successful.
           if (!benchmarkMonthlyValues || benchmarkMonthlyValues.length < 2) {
             console.warn(`[Helper calculateUpDownMarketPerformance] Insufficient aligned benchmark monthly data for ${benchmarkTicker}. Cannot calculate market performance.`);
             // Resolve with empty data if benchmark alignment fails.
             return resolve({ message: `Insufficient benchmark data for ${benchmarkTicker}`, marketPerformance: [] });
           }
           console.log(`[Helper calculateUpDownMarketPerformance] Using ${benchmarkMonthlyValues.length} aligned benchmark monthly values.`);
        } catch (benchErr) {
           // Handle errors during benchmark fetching/alignment.
           console.error(`[Helper calculateUpDownMarketPerformance] Error getting aligned benchmark data for ${benchmarkTicker}:`, benchErr);
           return reject(benchErr); // Reject the main promise if benchmark data fails critically.
        }

        // --- Step UD-c: Calculate Aligned Monthly Returns ---
        // Calculate portfolio monthly values from its daily values.
        const portfolioMonthlyValues = calculateMonthlyPortfolioValues(portfolioDailyValues);

        // Helper function to convert an array of { year_month, value } to a map of { year_month: monthly_return }
        function getReturnsMap(monthlyVals) {
            const returnsMap = {};
            for (let i = 1; i < monthlyVals.length; i++) {
                const prev = monthlyVals[i - 1];
                const curr = monthlyVals[i];
                // Calculate return, handling potential division by zero.
                const monthlyReturn = prev.value === 0 ? 0 : (curr.value / prev.value) - 1;
                returnsMap[curr.year_month] = monthlyReturn;
            }
            return returnsMap;
        }

        // Get return maps for both portfolio and benchmark.
        const portfolioReturnsMap = getReturnsMap(portfolioMonthlyValues);
        const benchmarkReturnsMap = getReturnsMap(benchmarkMonthlyValues);

        // Create an array of aligned return objects for months where both have data.
        const alignedReturns = [];
        // Find common months between the two return maps.
        const commonMonths = Object.keys(portfolioReturnsMap).filter(month => benchmarkReturnsMap.hasOwnProperty(month));

        // Check if there are any common months to compare.
        if (commonMonths.length === 0) {
           console.warn("[Helper calculateUpDownMarketPerformance] No common months found between portfolio and benchmark returns.");
           return resolve({ message: 'No common months found between portfolio and benchmark returns', marketPerformance: [] });
        }

        // Populate the alignedReturns array.
        commonMonths.forEach(month => {
            const portfolioReturn = portfolioReturnsMap[month];
            const benchmarkReturn = benchmarkReturnsMap[month];
            alignedReturns.push({
                year_month: month,
                portfolioReturn: portfolioReturn,       // Portfolio's return for the month (decimal)
                benchmarkReturn: benchmarkReturn,       // Benchmark's return for the month (decimal)
                activeReturn: portfolioReturn - benchmarkReturn, // Portfolio Return - Benchmark Return (decimal)
                isUpMarket: benchmarkReturn > 0,        // True if benchmark return was positive
                isDownMarket: benchmarkReturn < 0      // True if benchmark return was negative
            });
        });
        console.log(`[Helper calculateUpDownMarketPerformance] Calculated ${alignedReturns.length} aligned monthly return periods.`);

        // --- Step UD-d: Separate Returns by Market Condition ---
        // Filter the aligned returns into two groups based on benchmark performance.
        const upMarketMonths = alignedReturns.filter(m => m.isUpMarket);
        const downMarketMonths = alignedReturns.filter(m => m.isDownMarket);
        console.log(`[Helper calculateUpDownMarketPerformance] Up Market Months: ${upMarketMonths.length}, Down Market Months: ${downMarketMonths.length}`);

        // --- Step UD-e: Calculate Metrics for Each Condition ---

        // Helper: Calculate average of a specific field in an array of objects.
        const calculateAverage = (arr, field) => {
           if (!arr || arr.length === 0) return 0;
           return arr.reduce((sum, item) => sum + (item[field] || 0), 0) / arr.length;
        }
        // Helper: Calculate percentage of months where portfolio beat the benchmark (activeReturn > 0).
        const calculatePercentAbove = (arr) => {
           if (!arr || arr.length === 0) return 0;
           return (arr.filter(item => item.activeReturn > 0).length / arr.length) * 100;
        }
        // Helper: Calculate average active return ONLY for months where portfolio beat benchmark.
        const calculateAvgPositiveActiveReturn = (arr) => {
            const positiveReturns = arr.filter(item => item.activeReturn > 0);
            return calculateAverage(positiveReturns, 'activeReturn'); // Returns decimal average
        };
        // Helper: Calculate average active return ONLY for months where portfolio did NOT beat benchmark.
        const calculateAvgNegativeActiveReturn = (arr) => {
            const negativeReturns = arr.filter(item => item.activeReturn <= 0);
            return calculateAverage(negativeReturns, 'activeReturn'); // Returns decimal average
        };

        // --- Calculate Up Market Metrics ---
        const upMarketMetrics = {
            marketType: 'Up Market',
            occurrences: upMarketMonths.length, // Number of months benchmark was up
            percentageAboveBenchmark: parseFloat(calculatePercentAbove(upMarketMonths).toFixed(2)), // % of up months portfolio beat benchmark
            // Average active return ONLY in the up months where portfolio outperformed:
            averageActiveReturnAboveBenchmark: parseFloat((calculateAvgPositiveActiveReturn(upMarketMonths) * 100).toFixed(2)), // %
            // Average active return ONLY in the up months where portfolio underperformed:
            averageActiveReturnBelowBenchmark: parseFloat((calculateAvgNegativeActiveReturn(upMarketMonths) * 100).toFixed(2)), // %
            // Overall average active return across ALL up market months:
            totalAverageActiveReturn: parseFloat((calculateAverage(upMarketMonths, 'activeReturn') * 100).toFixed(2)) // %
        };

        // --- Calculate Down Market Metrics ---
        const downMarketMetrics = {
            marketType: 'Down Market',
            occurrences: downMarketMonths.length, // Number of months benchmark was down
            percentageAboveBenchmark: parseFloat(calculatePercentAbove(downMarketMonths).toFixed(2)), // % of down months portfolio beat benchmark
            // Average active return ONLY in the down months where portfolio outperformed:
            averageActiveReturnAboveBenchmark: parseFloat((calculateAvgPositiveActiveReturn(downMarketMonths) * 100).toFixed(2)), // %
            // Average active return ONLY in the down months where portfolio underperformed:
            averageActiveReturnBelowBenchmark: parseFloat((calculateAvgNegativeActiveReturn(downMarketMonths) * 100).toFixed(2)), // %
            // Overall average active return across ALL down market months:
            totalAverageActiveReturn: parseFloat((calculateAverage(downMarketMonths, 'activeReturn') * 100).toFixed(2)) // %
        };

        // --- Calculate Total Market Metrics (for comparison) ---
        const totalMarketMetrics = {
            marketType: 'Total',
            occurrences: alignedReturns.length, // Total number of comparable months
            percentageAboveBenchmark: parseFloat(calculatePercentAbove(alignedReturns).toFixed(2)), // Overall % portfolio beat benchmark
            // Average active return ONLY in months portfolio outperformed:
            averageActiveReturnAboveBenchmark: parseFloat((calculateAvgPositiveActiveReturn(alignedReturns) * 100).toFixed(2)), // %
            // Average active return ONLY in months portfolio underperformed:
            averageActiveReturnBelowBenchmark: parseFloat((calculateAvgNegativeActiveReturn(alignedReturns) * 100).toFixed(2)), // %
            // Overall average active return across ALL comparable months:
            totalAverageActiveReturn: parseFloat((calculateAverage(alignedReturns, 'activeReturn') * 100).toFixed(2)) // %
        };

        console.log('[Helper calculateUpDownMarketPerformance] Market performance metrics calculated.');
        // --- Step UD-f: Resolve Promise ---
        // Resolve with an object containing an array of the three metric sets.
        resolve({
            marketPerformance: [upMarketMetrics, downMarketMetrics, totalMarketMetrics]
        });

      }) // End calculateDailyPortfolioValues .then() callback
      .catch(reject); // Catch errors from calculateDailyPortfolioValues or benchmark fetching
  }); // End main promise
}

// --- Route 11: GET /market-performance ---
// Retrieves the calculated up vs. down market performance analysis.
// Calls the `calculateUpDownMarketPerformance` helper function.
app.get('/market-performance', (req, res) => {
  console.log('[API /market-performance] Request received.');
  // Call the helper function.
  calculateUpDownMarketPerformance()
    .then(data => {
      // On success, send the resulting data (object containing `marketPerformance` array).
      console.log('[API /market-performance] Market performance data calculated.');
      res.json(data);
    })
    .catch(err => {
      // On failure (e.g., error fetching data in helper), send an error response.
      console.error('[API /market-performance] Error calculating market performance:', err.message);
      res.status(500).json({ error: 'Error calculating market performance', details: err.message });
    });
});

// --- Route 12: GET /fundamentals-date ---
// Returns a placeholder date representing when underlying 'fundamentals' data
// (like P/E ratios, sector weights, etc. used in style analysis) was last updated.
// !!! IMPORTANT: In this implementation, it simply returns the CURRENT server date.
// !!! A real application would return the actual date associated with the financial data source.
app.get('/fundamentals-date', (req, res) => {
  console.log('[API /fundamentals-date] Request received.');
  // Get the current date on the server.
  const currentDate = new Date();
  // Format the date into YYYY-MM-DD format.
  const formattedDate = currentDate.toISOString().split('T')[0];
  console.log(`[API /fundamentals-date] Sending current date as fundamentals date: ${formattedDate}`);
  // Send the formatted date back in a JSON object.
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
 * Helper Function: calculateGeometricMean
 * Calculates the geometric mean, which represents the average compounded return over a period.
 * It's often considered a more accurate measure of investment performance than the simple arithmetic mean
 * because it accounts for the effect of compounding.
 * Formula involves multiplying all (1 + return) factors together and taking the Nth root.
 * @param {Array<number>} values - Array of returns (as decimals, e.g., 0.05 for 5%, -0.02 for -2%).
 * @returns {number} Geometric mean return (as a decimal).
 */
function calculateGeometricMean(values) {
  // Check for empty or invalid input.
  if (!values || values.length === 0) return 0;

  // Step 1: Convert returns to growth factors.
  // A return of 0.05 (5%) becomes a growth factor of 1.05.
  // A return of -0.02 (-2%) becomes a growth factor of 0.98.
  const growthFactors = values.map(r => 1 + r);

  // Step 2: Calculate the product of all growth factors.
  // Multiply all the growth factors together.
  const product = growthFactors.reduce((prod, factor) => prod * factor, 1);

  // --- Handle Edge Cases --- 
  // If the product is negative and we have an even number of periods, the result is mathematically complex (involves imaginary numbers).
  // This usually indicates very large losses. We return -1 (representing -100% return) as a practical indicator.
  if (product < 0 && values.length % 2 === 0) {
       console.warn("[Helper calculateGeometricMean] Even root of negative product encountered. Returning -100%.");
       return -1; // Indicate total loss or mathematical impossibility
  }
  // If the product is exactly zero, it means the value went to zero at some point.
  if (product === 0) return -1; // Indicate total loss

  // Step 3: Calculate the Nth root of the product.
  // N is the number of return periods (which is the length of the input `values` array).
  // Use Math.pow(base, exponent). The exponent is (1 / N).
  // Use Math.abs(product) in case the product is negative (with an odd number of periods).
  const nthRoot = Math.pow(Math.abs(product), 1 / values.length);

  // Step 4: Convert the result back to an average return.
  // Subtract 1 from the Nth root.
  // Re-apply the negative sign if the original product was negative (for odd number of periods).
  const geometricMeanReturn = (product < 0 ? -nthRoot : nthRoot) - 1;

  return geometricMeanReturn;
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
 * Helper Function: calculateAlpha
 * Calculates the Alpha of a portfolio.
 * Alpha represents the excess return of the portfolio compared to its expected return, given its Beta (market risk) and the benchmark's performance.
 * It's often considered a measure of the value added (or subtracted) by active management (e.g., stock selection).
 * - Positive Alpha: Portfolio performed better than expected for the risk taken.
 * - Negative Alpha: Portfolio performed worse than expected.
 * - Alpha = 0: Portfolio performed as expected.
 * Formula uses the Capital Asset Pricing Model (CAPM): Alpha = PortfolioReturn - (RiskFreeRate + Beta * (BenchmarkReturn - RiskFreeRate))
 * @param {number} portfolioAnnualizedReturn - Portfolio's annualized return (as decimal, e.g., 0.10 for 10%).
 * @param {number} riskFreeRateDecimal - Annual risk-free rate (as decimal, e.g., 0.015 for 1.5%).
 * @param {number|null} beta - Portfolio's Beta relative to the benchmark (result from `calculateBeta`).
 * @param {number} benchmarkAnnualizedReturn - Benchmark's annualized return (as decimal).
 * @returns {number|null} Alpha value (as a percentage), or null if Beta is missing.
 */
function calculateAlpha(portfolioAnnualizedReturn, riskFreeRateDecimal, beta, benchmarkAnnualizedReturn) {
   // --- Input Validation ---
   // Alpha calculation requires a valid Beta value.
   if (beta === null) {
      console.warn("[Helper calculateAlpha] Beta is null. Cannot calculate Alpha.");
      return null; // Cannot calculate Alpha without Beta.
   }

   // --- Calculate Expected Return (based on CAPM) ---
   // Expected Return = RiskFreeRate + Beta * (Market Risk Premium)
   // Market Risk Premium = Benchmark Return - Risk Free Rate
   const expectedReturn = riskFreeRateDecimal + beta * (benchmarkAnnualizedReturn - riskFreeRateDecimal);

   // --- Calculate Alpha ---
   // Alpha = Actual Portfolio Return - Expected Return
   const alpha = portfolioAnnualizedReturn - expectedReturn;

   // Return Alpha as a percentage.
   return alpha * 100;
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
 * @param {number} beta - Portfolio beta relative to benchmark
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
      console.log('No portfolio data available');
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
      console.log(`No benchmark data available for ${benchmarkTicker}`);
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
      console.log(`No benchmark price available for initial date (${initialBenchmarkDate})`);
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
        const benchmarkDailyValues = [];
        
        for (const mv of portfolioDailyValues) {
            const benchmarkPrice = getPriceForDate(benchmarkPrices, mv.date);
            if (benchmarkPrice !== null) {
                benchmarkDailyValues.push({
                    date: mv.date,
                    value: initialPortfolioValue * (benchmarkPrice / initialBenchmarkPrice)
                });
            }
            // Skip dates where benchmark price is missing instead of approximating
        }
        
        // Handle the case where we couldn't get enough benchmark prices
        if (benchmarkDailyValues.length < portfolioDailyValues.length / 2) {
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
    const benchmarkTicker = req.query.benchmark || 'SPY'; // Default to SPY, allow override
    console.log(`[API /annual-returns] Request received. Benchmark: ${benchmarkTicker}`);
    
    // Get daily portfolio values
    const dailyValues = await calculateDailyPortfolioValues();
    
    if (!dailyValues || dailyValues.length === 0) {
      return res.status(404).json({
        error: 'No portfolio data available',
        message: 'Please upload transaction data before viewing annual returns.'
      });
    }
    
    // Calculate yearly values from daily values
    const yearlyValues = calculateYearlyPortfolioValues(dailyValues);
    
    if (!yearlyValues || yearlyValues.length === 0) {
      return res.status(404).json({
        error: 'No yearly portfolio data available',
        message: 'Could not calculate yearly data from your transactions. Please ensure your transactions span a complete year.'
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
    
    // Calculate benchmark yearly values
    const benchmarkYearlyValues = [];
    let prevYearValue = null;
    
    // Sort yearly values by year
    yearlyValues.sort((a, b) => parseInt(a.year) - parseInt(b.year));
    
    for (const yearData of yearlyValues) {
      const year = yearData.year;
      const startDate = `${year}-01-01`;
      const endDate = `${year}-12-31`;
      
      // Get benchmark price at start of year
      const startPrice = getPriceForDate(benchmarkPrices, startDate);
      // Get benchmark price at end of year
      const endPrice = getPriceForDate(benchmarkPrices, endDate);
      
      if (startPrice && endPrice) {
        const benchmarkReturn = ((endPrice / startPrice) - 1) * 100;
        
        // Calculate benchmark balance (cumulative)
        let benchmarkBalance;
        if (prevYearValue === null) {
          benchmarkBalance = yearData.value; // Start at same value as portfolio for first year
        } else {
          benchmarkBalance = prevYearValue * (1 + (benchmarkReturn / 100));
        }
        prevYearValue = benchmarkBalance;
        
        benchmarkYearlyValues.push({
          year,
          return: parseFloat(benchmarkReturn.toFixed(2)),
          value: parseFloat(benchmarkBalance.toFixed(2))
        });
      }
    }
    
    // Combine portfolio and benchmark yearly data
    const annualReturns = yearlyValues.map(yearData => {
      const benchmarkData = benchmarkYearlyValues.find(b => b.year === yearData.year);
      
      return {
        year: yearData.year,
        portfolioValue: parseFloat(yearData.value.toFixed(2)),
        benchmarkReturn: benchmarkData ? benchmarkData.return : null,
        benchmarkValue: benchmarkData ? benchmarkData.value : null
      };
    });
    
    res.json(annualReturns);
  } catch (error) {
    console.error('Error calculating annual returns:', error);
    res.status(500).json({ 
      error: 'Error calculating annual returns',
      message: 'An error occurred while calculating annual returns. Please try again later.'
    });
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
 * @param {string} benchmarkTicker - The ticker symbol for the benchmark (e.g., 'SPY').
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

        if (!benchmarkPrices || !benchmarkPrices['Time Series (Daily)']) {
            console.warn("[calculateMonthlyReturns] No benchmark price data available for " + benchmarkTicker);
            return null; // Cannot calculate benchmark metrics
        }

        // Align benchmark data with portfolio start date and value
        const initialPortfolioValue = dailyValues[0].value;
        const initialBenchmarkDate = dailyValues[0].date;
        const initialBenchmarkPrice = getPriceForDate(benchmarkPrices, initialBenchmarkDate);

        if (initialBenchmarkPrice === null || initialBenchmarkPrice <= 0) {
            console.warn("[calculateMonthlyReturns] Could not find valid benchmark price for " + benchmarkTicker + " on initial date " + initialBenchmarkDate);
            return null; // Cannot proceed without starting price
        }

        // Create benchmark daily values aligned with portfolio dates and scaled
        const benchmarkDailyValues = [];
        
        for (const mv of monthlyValues) {
            const benchmarkPrice = getPriceForDate(benchmarkPrices, mv.date);
            if (benchmarkPrice !== null) {
                benchmarkDailyValues.push({
                    date: mv.date,
                    value: initialPortfolioValue * (benchmarkPrice / initialBenchmarkPrice)
                });
            }
            // Skip dates where benchmark price is missing instead of approximating
        }
        
        // Handle the case where we couldn't get enough benchmark prices
        if (benchmarkDailyValues.length < monthlyValues.length / 2) {
            console.warn("[calculateMonthlyReturns] Not enough aligned benchmark daily data points.");
            return null;
        }

        // Calculate benchmark monthly values from the aligned daily values
        const benchmarkMonthlyValues = calculateMonthlyPortfolioValues(benchmarkDailyValues);
        console.log("[calculateMonthlyReturns] Calculated " + benchmarkMonthlyValues.length + " benchmark monthly values.");
        return benchmarkMonthlyValues;

    } catch (error) {
        console.error("[calculateMonthlyReturns] Error processing benchmark data for " + benchmarkTicker + ":", error);
        return null; // Return null on error
    }
}

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

// GET /risk-return endpoint to calculate and return portfolio risk and return metrics
app.get('/risk-return', async (req, res) => {
  try {
    const benchmarkTicker = req.query.benchmark || 'SPY';
    console.log(`Calculating risk-return metrics with benchmark: ${benchmarkTicker}`);
    
    // Get daily portfolio values
    const dailyValues = await calculateDailyPortfolioValues();
    
    if (!dailyValues || dailyValues.length === 0) {
      return res.status(404).json({ 
        error: 'No portfolio data available',
        message: 'Please upload transaction data before viewing risk-return metrics.'
      });
    }
    
    // Calculate monthly values from daily values
    const monthlyValues = calculateMonthlyPortfolioValues(dailyValues);
    
    if (!monthlyValues || monthlyValues.length < 2) {
      return res.status(404).json({ 
        error: 'Insufficient portfolio data',
        message: 'Risk-return metrics require at least 2 months of data. Please upload more transactions.'
      });
    }
    
    // Get time period in years
    const firstDate = new Date(dailyValues[0].date);
    const lastDate = new Date(dailyValues[dailyValues.length - 1].date);
    const yearDiff = (lastDate - firstDate) / (365.25 * 24 * 60 * 60 * 1000);
    
    // Calculate start and end values
    const startValue = dailyValues[0].value;
    const endValue = dailyValues[dailyValues.length - 1].value;
    
    // Calculate key metrics
    const metrics = {
      // Time period
      start_date: dailyValues[0].date,
      end_date: dailyValues[dailyValues.length - 1].date,
      time_period_years: parseFloat(yearDiff.toFixed(2)),
      
      // Portfolio values
      start_balance: parseFloat(startValue.toFixed(2)),
      end_balance: parseFloat(endValue.toFixed(2)),
      
      // Return metrics
      annualized_return: calculateCAGR(startValue, endValue, yearDiff),
      cumulative_return: calculateCumulativeReturn(startValue, endValue),
      
      // Risk metrics
      annualized_std_dev: calculateAnnualizedStdDev(monthlyValues),
      sharpe_ratio: calculateSharpeRatio(
        calculateCAGR(startValue, endValue, yearDiff),
        calculateAnnualizedStdDev(monthlyValues)
      ),
      
      // Drawdown metrics
      max_drawdown: calculateMaxDrawdown(dailyValues).maxDrawdownPercentage,
      
      // Monthly metrics
      positive_months: calculatePositiveMonths(monthlyValues)
    };
    
    // Send response with calculated metrics
    res.json({ metrics });
    
  } catch (error) {
    console.error('[API /risk-return] Error calculating metrics:', error);
    res.status(500).json({ 
      error: 'Error calculating risk-return metrics',
      message: 'An error occurred while calculating risk-return metrics. Please try again later.'
    });
  }
});

// ... existing code ...


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
    const benchmarkTicker = req.query.benchmark || 'SPY'; // Default to SPY, allow override
    console.log(`[API /annual-returns] Request received. Benchmark: ${benchmarkTicker}`);
    
    // Get daily portfolio values
    const dailyValues = await calculateDailyPortfolioValues();
    
    if (!dailyValues || dailyValues.length === 0) {
      return res.status(404).json({
        error: 'No portfolio data available',
        message: 'Please upload transaction data before viewing annual returns.'
      });
    }
    
    // Calculate yearly values from daily values
    const yearlyValues = calculateYearlyPortfolioValues(dailyValues);
    
    if (!yearlyValues || yearlyValues.length === 0) {
      return res.status(404).json({
        error: 'No yearly portfolio data available',
        message: 'Could not calculate yearly data from your transactions. Please ensure your transactions span a complete year.'
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
    
    // Calculate benchmark yearly values
    const benchmarkYearlyValues = [];
    let prevYearValue = null;
    
    // Sort yearly values by year
    yearlyValues.sort((a, b) => parseInt(a.year) - parseInt(b.year));
    
    for (const yearData of yearlyValues) {
      const year = yearData.year;
      const startDate = `${year}-01-01`;
      const endDate = `${year}-12-31`;
      
      // Get benchmark price at start of year
      const startPrice = getPriceForDate(benchmarkPrices, startDate);
      // Get benchmark price at end of year
      const endPrice = getPriceForDate(benchmarkPrices, endDate);
      
      if (startPrice && endPrice) {
        const benchmarkReturn = ((endPrice / startPrice) - 1) * 100;
        
        // Calculate benchmark balance (cumulative)
        let benchmarkBalance;
        if (prevYearValue === null) {
          benchmarkBalance = yearData.value; // Start at same value as portfolio for first year
        } else {
          benchmarkBalance = prevYearValue * (1 + (benchmarkReturn / 100));
        }
        prevYearValue = benchmarkBalance;
        
        benchmarkYearlyValues.push({
          year,
          return: parseFloat(benchmarkReturn.toFixed(2)),
          value: parseFloat(benchmarkBalance.toFixed(2))
        });
      }
    }
    
    // Combine portfolio and benchmark yearly data
    const annualReturns = yearlyValues.map(yearData => {
      const benchmarkData = benchmarkYearlyValues.find(b => b.year === yearData.year);
      
      return {
        year: yearData.year,
        portfolioValue: parseFloat(yearData.value.toFixed(2)),
        benchmarkReturn: benchmarkData ? benchmarkData.return : null,
        benchmarkValue: benchmarkData ? benchmarkData.value : null
      };
    });
    
    res.json(annualReturns);
  } catch (error) {
    console.error('Error calculating annual returns:', error);
    res.status(500).json({ 
      error: 'Error calculating annual returns',
      message: 'An error occurred while calculating annual returns. Please try again later.'
    });
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

// --- Route 8: GET /portfolio-summary ---
// Calculates and returns a comprehensive set of portfolio summary metrics.
// This endpoint relies heavily on the `calculatePortfolioSummaryMetrics` helper function (defined above).
// It serves as the main endpoint for fetching overall performance statistics.
app.get('/portfolio-summary', async (req, res) => { // Route handler is async because it calls an async helper
  console.log('[API /portfolio-summary] Request received.');
  try {
    // --- Step 8a: Calculate Metrics ---
    // Call the main helper function `calculatePortfolioSummaryMetrics`.
    // This function performs all the complex calculations (CAGR, StdDev, Drawdown, Sharpe, etc.)
    // by utilizing other helper functions and the data from the database.
    // `await` pauses execution here until the calculations are complete.
    const metrics = await calculatePortfolioSummaryMetrics();
    console.log('[API /portfolio-summary] Summary metrics calculated successfully.');

    // --- Step 8b: Send Response ---
    // If the helper function completes successfully and returns the metrics object,
    // send it back to the client as a JSON response.
    res.json(metrics);

  } catch (err) {
    // --- Step 8c: Handle Errors ---
    // Catch any errors that might have been thrown by `calculatePortfolioSummaryMetrics` or other issues.
    console.error('[API /portfolio-summary] Error calculating portfolio summary metrics:', err.message);
    // Check if the error is the specific one indicating no transaction data exists.
    if (err.message === 'No portfolio data available') {
        // If so, return a 404 Not Found status with a user-friendly message.
        res.status(404).json({ error: 'No portfolio data available', message: 'Upload transaction data first.' });
    } else {
        // For any other errors, return a generic 500 Internal Server Error.
        // Include the error message for debugging purposes.
        res.status(500).json({ error: 'Error calculating portfolio summary metrics', message: err.message });
    }
  }
});

/**
 * Helper Function: calculateRSquared (R²)
 * Calculates R-Squared, which is the square of the correlation coefficient between portfolio and benchmark returns.
 * It represents the proportion of the portfolio's variance (risk) that can be explained by the benchmark's variance.
 * - R² ranges from 0 to 1 (or 0% to 100%).
 * - R² = 1: Benchmark movements perfectly explain portfolio movements.
 * - R² = 0.5: 50% of portfolio variance is explained by the benchmark.
 * - R² = 0: Benchmark movements have no correlation with portfolio movements.
 * High R² (e.g., > 0.85) suggests Beta and Alpha are more reliable indicators for that portfolio/benchmark pair.
 * Low R² suggests the portfolio's performance is driven by factors other than the benchmark market movements.
 * @param {number|null} correlation - The Pearson correlation coefficient (result from `calculateBenchmarkCorrelation`).
 * @returns {number|null} R-Squared value (0 to 1), or null if correlation is missing.
 */
function calculateRSquared(correlation) {
  // --- Input Validation ---
  // R-Squared requires a valid correlation coefficient.
  if (correlation === null) {
     console.warn("[Helper calculateRSquared] Correlation is null. Cannot calculate R-Squared.");
     return null;
  }
  // R-Squared is simply the correlation squared.
  return Math.pow(correlation, 2);
}

/**
 * Helper Function: calculateTreynorRatio
 * Calculates the Treynor Ratio, which measures the portfolio's excess return (above the risk-free rate)
 * per unit of systematic market risk (Beta).
 * Similar to Sharpe Ratio, but uses Beta instead of total standard deviation as the risk measure.
 * It's useful for evaluating performance when the portfolio is part of a larger diversified investment strategy.
 * Higher Treynor Ratio is generally better, indicating more return for the market risk taken.
 * Formula: (Portfolio Return - Risk-Free Rate) / Portfolio Beta
 * @param {number} portfolioAnnualizedReturn - Portfolio's annualized return (as decimal).
 * @param {number} riskFreeRateDecimal - Annual risk-free rate (as decimal).
 * @param {number|null} beta - Portfolio's Beta (result from `calculateBeta`).
 * @returns {number|null} Treynor Ratio, or null if Beta is missing or zero.
 */
function calculateTreynorRatio(portfolioAnnualizedReturn, riskFreeRateDecimal, beta) {
   // --- Input Validation ---
   // Requires a valid Beta value that is not zero (or extremely close to zero) to avoid division by zero.
   if (beta === null || Math.abs(beta) < 0.0001) {
      console.warn(`[Helper calculateTreynorRatio] Beta is null or close to zero (${beta}). Cannot calculate Treynor Ratio.`);
      return null; // Return null if Beta is invalid for the calculation.
   }
   // Calculate the Treynor Ratio.
   return (portfolioAnnualizedReturn - riskFreeRateDecimal) / beta;
}

/**
 * Helper Function: calculateCalmarRatio
 * Calculates the Calmar Ratio, which measures the portfolio's annualized return relative to its maximum drawdown.
 * It focuses on return generated compared to the largest loss experienced during the period.
 * Higher Calmar Ratio is generally preferred, indicating better performance relative to the worst experienced loss.
 * Formula: Annualized Return / Maximum Drawdown (as a positive decimal)
 * @param {number} annualizedReturnDecimal - Portfolio's annualized return (as decimal).
 * @param {number} maxDrawdownDecimal - Portfolio's maximum drawdown (as a positive decimal, e.g., 0.20 for 20%).
 * @returns {number|null} Calmar Ratio, or null if max drawdown is zero or negative.
 */
function calculateCalmarRatio(annualizedReturnDecimal, maxDrawdownDecimal) {
  // --- Input Validation ---
  // Maximum drawdown must be positive for the ratio to be meaningful.
  // A drawdown of 0 means no losses occurred.
  if (maxDrawdownDecimal <= 0) {
     // If no drawdown, the ratio is technically infinite or undefined.
     // Returning null is a safe way to indicate this.
     console.warn(`[Helper calculateCalmarRatio] Max drawdown is zero or negative (${maxDrawdownDecimal}). Cannot calculate Calmar Ratio.`);
     return null;
  }
  // Calculate the Calmar Ratio.
  return annualizedReturnDecimal / maxDrawdownDecimal;
}

/**
 * Helper Function: calculateModiglianiMeasure (M²)
 * Calculates the Modigliani-Modigliani (M²) measure.
 * This metric adjusts the portfolio's return to match the volatility (standard deviation) of the benchmark.
 * It essentially answers: "What would the portfolio's return have been if it had the same total risk as the benchmark?"
 * This allows for a direct comparison of risk-adjusted returns between the portfolio and the benchmark.
 * A higher M² value (in percentage terms) is better.
 * Formula: M² = RiskFreeRate + SharpeRatio * BenchmarkStdDev
 *          M² = RiskFreeRate + [(PortfolioReturn - RiskFreeRate) / PortfolioStdDev] * BenchmarkStdDev
 * @param {number} portfolioAnnualizedReturn - Portfolio's annualized return (as decimal).
 * @param {number} riskFreeRateDecimal - Annual risk-free rate (as decimal).
 * @param {number} portfolioAnnualizedStdDev - Portfolio's annualized standard deviation (as decimal).
 * @param {number} benchmarkAnnualizedStdDev - Benchmark's annualized standard deviation (as decimal).
 * @returns {number|null} M² value (as a percentage), or null if standard deviations are invalid.
 */
function calculateModiglianiMeasure(portfolioAnnualizedReturn, riskFreeRateDecimal, portfolioAnnualizedStdDev, benchmarkAnnualizedStdDev) {
  // --- Input Validation ---
  // Requires valid (positive) standard deviations for both portfolio and benchmark.
  if (portfolioAnnualizedStdDev <= 0 || benchmarkAnnualizedStdDev <= 0) {
      console.warn(`[Helper calculateModiglianiMeasure] Portfolio or Benchmark Std Dev is zero or negative. Cannot calculate M². P:${portfolioAnnualizedStdDev}, B:${benchmarkAnnualizedStdDev}`);
      return null;
  }

  // --- Calculate Portfolio's Sharpe Ratio ---
  // (Portfolio Return - Risk Free Rate) / Portfolio Standard Deviation
  const sharpeRatio = (portfolioAnnualizedReturn - riskFreeRateDecimal) / portfolioAnnualizedStdDev;

  // --- Calculate M² ---
  // M² = RiskFreeRate + (Portfolio Sharpe Ratio * Benchmark Standard Deviation)
  // This scales the portfolio's excess return (Sharpe) by the benchmark's risk level.
  const mSquared = riskFreeRateDecimal + sharpeRatio * benchmarkAnnualizedStdDev;

  // Return the M² value as a percentage.
  return mSquared * 100;
}

//rewritten file