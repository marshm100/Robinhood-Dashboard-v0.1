#!/bin/bash

echo "===================================="
echo " Robinhood Dashboard Startup"
echo "===================================="
echo

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed or not in PATH."
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

echo "Starting Robinhood Dashboard..."
node start.js

# If we get here, the process has ended
echo
echo "Application has stopped." 