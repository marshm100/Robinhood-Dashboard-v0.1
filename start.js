#!/usr/bin/env node
// ====================================
//  Robinhood Dashboard Startup Script (start.js)
// ====================================
// Purpose: This Node.js script is executed by 'start.bat' (or run directly with 'node start.js').
//          It orchestrates the launch of the backend Express server and the frontend Vite development server.
//          It also handles graceful shutdown of these child processes when this script is terminated.
//
// Order of Operations:
// 1. Import necessary Node.js modules (child_process, path, os, fs).
// 2. Determine OS-specific commands (npm/npm.cmd, node/node).
// 3. Check if essential backend and frontend files exist to ensure the script runs from the correct directory.
// 4. Define a helper function ('startProcess') to spawn and manage child processes (backend/frontend).
// 5. Define a cleanup function ('exitHandler') to terminate all child processes when this script exits.
// 6. Set up event listeners (SIGINT, SIGTERM, exit) to trigger the cleanup handler.
// 7. Start the backend server ('node backend/index.js').
// 8. Wait for a short delay (2 seconds).
// 9. Start the frontend development server ('npm run dev' in 'frontend/').
// 10. Log relevant URLs and instructions to the console.
// ====================================

const { spawn } = require('child_process'); // Used to create child processes (backend, frontend).
const path = require('path'); // Used for creating platform-independent file paths.
const os = require('os'); // Used to detect the operating system (Windows vs. others).
const fs = require('fs'); // Used to check if files exist.

// --- Configuration & Setup ---

// Determine the correct command names based on the operating system.
// Windows requires '.cmd' suffix for npm commands run via spawn.
const isWindows = os.platform() === 'win32';
const npmCmd = isWindows ? 'npm.cmd' : 'npm';
const nodeCmd = isWindows ? 'node' : 'node';

// Array to keep track of all spawned child processes for cleanup.
const processes = [];

// --- Prerequisite File Checks ---
// Ensure the script is likely running from the project root by checking for key files.

// Path to the main backend server file.
const backendIndexPath = path.join(__dirname, 'backend', 'index.js');
// Path to the frontend package configuration file.
const frontendPackagePath = path.join(__dirname, 'frontend', 'package.json');

// Check if backend index.js exists.
if (!fs.existsSync(backendIndexPath)) {
  console.error(`❌ Backend index.js not found at: ${backendIndexPath}`);
  console.error('Make sure you are running this script from the project root directory.');
  process.exit(1); // Exit if not found.
}

// Check if frontend package.json exists.
if (!fs.existsSync(frontendPackagePath)) {
  console.error(`❌ Frontend package.json not found at: ${frontendPackagePath}`);
  console.error('Make sure you are running this script from the project root directory.');
  process.exit(1); // Exit if not found.
}

// --- Process Management Functions ---

/**
 * Starts a child process and adds it to the tracking array.
 * @param {string} command - The command to execute (e.g., 'node', 'npm.cmd').
 * @param {string[]} args - An array of arguments for the command.
 * @param {object} options - Options for child_process.spawn (e.g., cwd, env).
 * @returns {ChildProcess} The spawned child process object.
 */
function startProcess(command, args, options) {
  console.log(`Starting: ${command} ${args.join(' ')} in ${options.cwd}`);
  
  // Spawn the child process.
  const proc = spawn(command, args, {
    ...options,
    stdio: 'inherit', // Pipe child process's stdin, stdout, stderr to this script's streams.
    shell: isWindows // Use shell execution on Windows for compatibility.
  });
  
  // Add the process to our list for cleanup.
  processes.push(proc);
  
  // Basic error handling for the spawned process.
  proc.on('error', (error) => {
    console.error(`Process error (${command} ${args.join(' ')}): ${error.message}`);
  });
  
  // Return the process object.
  return proc;
}

/**
 * Gracefully terminates all tracked child processes.
 * This is called when the main script is about to exit.
 */
function exitHandler() {
  console.log('\nShutting down all processes...');
  // Iterate over the tracked processes.
  processes.forEach(proc => {
    // Check if the process hasn't already been killed.
    if (!proc.killed) {
      try {
        // Attempt to kill the process.
        // On Unix-like systems, this sends SIGTERM by default.
        // On Windows, it uses TerminateProcess.
        proc.kill();
      } catch (err) {
        // Log if there's an error during termination (process might already be gone).
        console.error(`Error killing process: ${err.message}`);
      }
    }
  });
}

// --- Setup Exit Handlers ---
// Ensure the exitHandler is called on common termination signals.

// Catches Ctrl+C (Interrupt signal).
process.on('SIGINT', () => {
  exitHandler();
  process.exit(); // Exit the main script.
});
// Catches termination signals (e.g., from task manager or 'kill' command).
process.on('SIGTERM', () => {
  exitHandler();
  process.exit(); // Exit the main script.
});
// Catches normal script exit.
process.on('exit', exitHandler);

// --- Main Execution Logic ---

console.log('😄 Robinhood Dashboard is starting...');

// 1. Start the backend server.
// This process runs 'backend/index.js', which contains the API endpoints.
// The actual CSV file analysis logic is within 'backend/index.js' (likely in an /upload endpoint handler)
// and is triggered when a file is uploaded via the frontend interface, NOT directly by this script.
console.log('🚀 Starting backend server...');
const backendProcess = startProcess(nodeCmd, ['index.js'], {
  // Set the working directory for the backend process.
  cwd: path.resolve(__dirname, 'backend')
});

// Optional: Log when the backend process exits.
backendProcess.on('close', (code) => {
  if (code !== 0) {
    console.error(`⚠️ Backend process exited unexpectedly with code ${code}`);
  } else {
    console.log(`✅ Backend process exited gracefully with code ${code}`);
  }
});

// 2. Wait briefly before starting the frontend.
// This gives the backend a moment to initialize, potentially preventing
// frontend requests from failing immediately on startup if it depends on the backend.
setTimeout(() => {
  // 3. Start the frontend development server using Vite.
  // This executes the 'dev' script defined in frontend/package.json.
  console.log('🚀 Starting frontend development server (Vite)...');
  const frontendProcess = startProcess(npmCmd, ['run', 'dev'], {
    // Set the working directory for the frontend process.
    cwd: path.resolve(__dirname, 'frontend')
  });
  
  // Optional: Log when the frontend process exits.
  frontendProcess.on('close', (code) => {
    if (code !== 0) {
      console.error(`⚠️ Frontend process exited unexpectedly with code ${code}`);
    } else {
       console.log(`✅ Frontend process exited gracefully with code ${code}`);
    }
  });
  
  // Provide useful information to the user.
  console.log('🌐 Frontend should be available at: http://localhost:5173 (Vite default)');
  console.log('📡 Backend API is running at: http://localhost:3001 (Check backend/index.js for actual port)');
  console.log('⚠️  Press Ctrl+C in this terminal to stop both servers.');

}, 2000); // 2000 milliseconds (2 seconds) delay. 