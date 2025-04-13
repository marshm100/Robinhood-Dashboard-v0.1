const sqlite3 = require('sqlite3');
sqlite3.verbose();

console.log('Starting transactions check...');

// Get real database path
const path = require('path');
const dbPath = path.join(__dirname, 'robinhood.db');
console.log(`Opening database at: ${dbPath}`);

// Open the real database
const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READWRITE, (err) => {
  if (err) {
    return console.error('Cannot open database:', err.message);
  }
  console.log('Connected to SQLite database');
  
  // Check if transactions table exists
  db.get("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'", (err, table) => {
    if (err) {
      console.error('Error checking for transactions table:', err.message);
      closeDb();
      return;
    }
    
    if (!table) {
      console.log('Transactions table does not exist yet');
      closeDb();
      return;
    }
    
    // Get transaction count
    db.get('SELECT COUNT(*) as count FROM transactions', (err, row) => {
      if (err) {
        console.error('Error counting transactions:', err.message);
        closeDb();
        return;
      }
      
      console.log(`Found ${row.count} transactions in the database`);
      
      // If we have transactions, show a sample
      if (row.count > 0) {
        db.all('SELECT * FROM transactions LIMIT 5', (err, transactions) => {
          if (err) {
            console.error('Error fetching sample transactions:', err.message);
          } else {
            console.log('\nSample transactions:');
            transactions.forEach(tx => {
              console.log(`ID: ${tx.id}, Date: ${tx.activity_date}, Ticker: ${tx.ticker || 'N/A'}, Type: ${tx.trans_code}, Quantity: ${tx.quantity}, Price: ${tx.price}, Amount: ${tx.amount}`);
            });
          }
          closeDb();
        });
      } else {
        closeDb();
      }
    });
  });
});

function closeDb() {
  db.close((err) => {
    if (err) {
      console.error('Error closing database:', err.message);
    } else {
      console.log('Database connection closed');
    }
  });
} 