# Robinhood Dashboard - Quick Start Guide

## Getting Started

Follow these simple steps to start the Robinhood Dashboard application:

### First Time Setup

1. Make sure you have Node.js installed on your system (version 16 or higher recommended)
2. Install all required dependencies:
   "```"
   npm run install:all
   "```"

### Starting the Application

#### Option 1: Using start scripts (recommended)

- **Windows**: Double-click on `start.bat`
- **macOS/Linux**: Run `./start.sh` in your terminal (you may need to set execute permissions with `chmod +x start.sh`)

#### Option 2: Using npm

Run this command in the project root:
"```"
npm start
"```"

#### Option 3: Manual start

Run these commands in separate terminal windows:
"```"

#### Terminal 1 - Start backend

cd backend
node index.js

#### Terminal 2 - Start frontend

cd frontend
npm run dev
"```"

### Accessing the Application

Once started:

- **Frontend**: Open your browser at <http://localhost:5173>
- **Backend API**: Available at <http://localhost:3000>

### Stopping the Application

- If using the start scripts: Press `Ctrl+C` in the terminal window
- If running manually: Press `Ctrl+C` in each terminal window

## Troubleshooting

- **"Module not found" errors**: Make sure you've run `npm run install:all` first
- **Port already in use**: Make sure no other applications are using ports 3000 or 5173
- **Other issues**: Check the console output for specific error messages
