#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

// Determine the command based on OS
const isWindows = os.platform() === 'win32';
const npmCmd = isWindows ? 'npm.cmd' : 'npm';
const nodeCmd = isWindows ? 'node' : 'node';

// Keep track of processes
const processes = [];

// Check if necessary files exist
const backendIndexPath = path.join(__dirname, 'backend', 'index.js');
const frontendPackagePath = path.join(__dirname, 'frontend', 'package.json');

if (!fs.existsSync(backendIndexPath)) {
  console.error(`❌ Backend index.js not found at: ${backendIndexPath}`);
  console.error('Make sure you are running this script from the project root directory.');
  process.exit(1);
}

if (!fs.existsSync(frontendPackagePath)) {
  console.error(`❌ Frontend package.json not found at: ${frontendPackagePath}`);
  console.error('Make sure you are running this script from the project root directory.');
  process.exit(1);
}

// Function to start a process
function startProcess(command, args, options) {
  console.log(`Starting: ${command} ${args.join(' ')}`);
  
  const proc = spawn(command, args, {
    ...options,
    stdio: 'inherit',
    shell: isWindows
  });
  
  processes.push(proc);
  
  proc.on('error', (error) => {
    console.error(`Process error: ${error.message}`);
  });
  
  return proc;
}

// Handle cleanup on exit
function exitHandler() {
  console.log('\nShutting down all processes...');
  processes.forEach(proc => {
    if (!proc.killed) {
      try {
        proc.kill();
      } catch (err) {
        console.error(`Error killing process: ${err.message}`);
      }
    }
  });
}

// Set up cleanup handlers
process.on('SIGINT', () => {
  exitHandler();
  process.exit();
});
process.on('SIGTERM', () => {
  exitHandler();
  process.exit();
});
process.on('exit', exitHandler);

console.log('😄 Robinhood Dashboard is starting...');

// Start backend directly
console.log('🚀 Starting backend server...');
const backendProcess = startProcess(nodeCmd, ['index.js'], {
  cwd: path.resolve(__dirname, 'backend')
});

backendProcess.on('close', (code) => {
  if (code !== 0) {
    console.error(`⚠️ Backend process exited with code ${code}`);
  } else {
    console.log(`Backend process exited with code ${code}`);
  }
});

// Wait a moment before starting frontend to let backend initialize
setTimeout(() => {
  // Start frontend directly with vite
  console.log('🚀 Starting frontend development server...');
  const frontendProcess = startProcess(npmCmd, ['run', 'dev'], {
    cwd: path.resolve(__dirname, 'frontend')
  });
  
  frontendProcess.on('close', (code) => {
    if (code !== 0) {
      console.error(`⚠️ Frontend process exited with code ${code}`);
    } else {
      console.log(`Frontend process exited with code ${code}`);
    }
  });
  
  console.log('🌐 Frontend will be available at: http://localhost:5173');
  console.log('📡 Backend will be available at: http://localhost:3001');
  console.log('⚠️  Press Ctrl+C to stop all processes');
}, 2000); 