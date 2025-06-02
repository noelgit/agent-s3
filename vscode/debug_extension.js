#!/usr/bin/env node

/**
 * Debug script to check if the extension is working properly
 */

const fs = require('fs');
const path = require('path');

console.log('🔍 Agent-S3 Extension Debug Check\n');

// Check if compiled files exist and have content
const outDir = path.join(__dirname, 'out');
const requiredFiles = [
    'extension.js',
    'backend-connection.js', 
    'webview-ui-loader.js',
    'websocket-client.js',
    'tree-providers.js',
    'constants.js'
];

console.log('📁 Checking compiled files:');
for (const file of requiredFiles) {
    const filePath = path.join(outDir, file);
    if (fs.existsSync(filePath)) {
        const stats = fs.statSync(filePath);
        const sizeKB = (stats.size / 1024).toFixed(1);
        console.log(`  ✅ ${file} (${sizeKB} KB)`);
    } else {
        console.log(`  ❌ ${file} - MISSING`);
    }
}

// Check package.json
console.log('\n📦 Checking package.json:');
const packagePath = path.join(__dirname, 'package.json');
if (fs.existsSync(packagePath)) {
    const pkg = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
    console.log(`  Name: ${pkg.name}`);
    console.log(`  Version: ${pkg.version}`);
    console.log(`  Main: ${pkg.main}`);
    console.log(`  Commands: ${pkg.contributes?.commands?.length || 0}`);
    console.log(`  Views: ${Object.keys(pkg.contributes?.views || {}).length}`);
} else {
    console.log('  ❌ package.json not found');
}

// Check VSIX file
console.log('\n📦 Checking VSIX file:');
const vsixPath = path.join(__dirname, 'agent-s3-fixed.vsix');
if (fs.existsSync(vsixPath)) {
    const stats = fs.statSync(vsixPath);
    const sizeMB = (stats.size / (1024 * 1024)).toFixed(1);
    console.log(`  ✅ agent-s3-fixed.vsix (${sizeMB} MB)`);
} else {
    console.log('  ❌ agent-s3-fixed.vsix not found');
}

// Check webview build
console.log('\n🌐 Checking webview build:');
const webviewBuildPath = path.join(__dirname, 'webview-ui', 'build');
if (fs.existsSync(webviewBuildPath)) {
    const indexPath = path.join(webviewBuildPath, 'index.html');
    const staticPath = path.join(webviewBuildPath, 'static');
    
    console.log(`  ✅ Build directory exists`);
    console.log(`  ${fs.existsSync(indexPath) ? '✅' : '❌'} index.html`);
    console.log(`  ${fs.existsSync(staticPath) ? '✅' : '❌'} static assets`);
} else {
    console.log('  ❌ Webview build directory not found');
}

console.log('\n🔧 Manual Installation Instructions:');
console.log('1. Open VS Code');
console.log('2. Go to Extensions (Ctrl+Shift+X / Cmd+Shift+X)');
console.log('3. Click the "..." menu → "Install from VSIX..."');
console.log('4. Select agent-s3-fixed.vsix from this directory');
console.log('5. Reload VS Code completely (close and reopen)');
console.log('6. Open a workspace folder');
console.log('7. Look for Agent-S3 icon in the left sidebar');

console.log('\n🐛 If commands show "not found":');
console.log('- Check the Developer Console: Help → Toggle Developer Tools → Console');
console.log('- Look for extension activation errors');
console.log('- Try: Ctrl+Shift+P → "Developer: Reload Window"');