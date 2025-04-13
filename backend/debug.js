const sqlite3 = require('sqlite3');
sqlite3.verbose();

console.log('Starting SQLite test...');

// Create an in-memory database
const db = new sqlite3.Database(':memory:', (err) => {
  if (err) {
    return console.error('Cannot open database:', err.message);
  }
  console.log('Connected to in-memory SQLite database');
  
  // Create a test table
  db.run(`CREATE TABLE test (
    id INTEGER PRIMARY KEY,
    name TEXT,
    value INTEGER
  )`, (err) => {
    if (err) {
      return console.error('Cannot create table:', err.message);
    }
    console.log('Test table created');
    
    // Insert data
    const stmt = db.prepare('INSERT INTO test (name, value) VALUES (?, ?)');
    stmt.run('item1', 100);
    stmt.run('item2', 200);
    stmt.run('item3', 300);
    stmt.finalize();
    console.log('Data inserted');
    
    // Query data
    db.all('SELECT * FROM test', [], (err, rows) => {
      if (err) {
        return console.error('Query failed:', err.message);
      }
      console.log('Query results:');
      rows.forEach(row => {
        console.log(`${row.id}: ${row.name} = ${row.value}`);
      });
      
      // Close the database
      db.close(err => {
        if (err) {
          return console.error('Error closing database:', err.message);
        }
        console.log('Database connection closed');
      });
    });
  });
});

// Now try with the real database
console.log('\nTrying with the real database...');
const path = require('path');
const dbPath = path.join(__dirname, 'robinhood.db');
console.log(`Opening database at: ${dbPath}`);

const realDb = new sqlite3.Database(dbPath, sqlite3.OPEN_READWRITE, (err) => {
  if (err) {
    return console.error('Cannot open real database:', err.message);
  }
  console.log('Connected to real database');
  
  // Try to query the portfolio_config table
  realDb.all('SELECT * FROM portfolio_config', [], (err, rows) => {
    if (err) {
      console.error('Error querying portfolio_config:', err.message);
    } else {
      console.log(`Found ${rows.length} rows in portfolio_config table`);
      rows.forEach(row => {
        console.log(`ID: ${row.id}, Investment: $${row.total_investment}, Ticker: ${row.ticker}, Allocation: ${row.allocation_percentage}%`);
      });
    }
    
    // Close the database
    realDb.close(err => {
      if (err) {
        return console.error('Error closing real database:', err.message);
      }
      console.log('Real database connection closed');
    });
  });
}); 