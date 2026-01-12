import subprocess

try:
    import yfinance as yf
    print(f"yfinance version: {yf.__version__}")
except ImportError:
    subprocess.run(['pip', 'install', 'yfinance'], check=True)
    import yfinance as yf
    print("Installed yfinance")

subprocess.run(['pip', 'install', 'pysqlite3'], check=True)
print("Installed pysqlite3 for SQLite")
