import sqlite3

conn = sqlite3.connect('portfolio.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = cursor.fetchall()
print('Tables in database:', tables)

# Check if transactions table exists and has data
if ('transactions',) in tables:
    cursor.execute('SELECT COUNT(*) FROM transactions')
    count = cursor.fetchone()[0]
    print(f'Transactions table has {count} rows')
else:
    print('Transactions table does not exist')

conn.close()
