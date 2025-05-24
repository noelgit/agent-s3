#!/usr/bin/env node
/**
 * Script to fix common TypeScript and JavaScript linting issues.
 * This script handles:
 * 1. Running Prettier for consistent formatting
 * 2. Running ESLint (if available) and fixing auto-fixable issues
 * 3. Checking for and fixing common TypeScript type issues
 */

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

// Check if a command is available
function commandExists(command) {
  try {
    execSync(`which ${command}`, { stdio: "ignore" });
    return true;
  } catch (e) {
    return false;
  }
}

// Run prettier on all TS/JS files
function runPrettier(directory) {
  console.log("Running Prettier on TypeScript and JavaScript files...");

  try {
    // Check if prettier is installed
    if (!commandExists("npx")) {
      console.error("npx is not available. Please install Node.js and npm.");
      return false;
    }

    // Run prettier in write mode
    const command = `cd ${directory} && npx prettier --write "**/*.{ts,js}"`;
    execSync(command, { stdio: "inherit" });
    console.log("Prettier formatting completed successfully.");
    return true;
  } catch (error) {
    console.error("Prettier failed:", error.message);
    return false;
  }
}

// Run ESLint on all TS/JS files
function runEslint(directory) {
  console.log("Running ESLint on TypeScript and JavaScript files...");

  try {
    // Check if eslint is installed
    const eslintConfig = path.join(directory, ".eslintrc.js");
    const eslintConfigJson = path.join(directory, ".eslintrc.json");

    if (!fs.existsSync(eslintConfig) && !fs.existsSync(eslintConfigJson)) {
      console.log("No ESLint config found. Skipping ESLint.");
      return false;
    }

    // Run eslint in fix mode
    const command = `cd ${directory} && npx eslint --fix "**/*.{ts,js}"`;
    execSync(command, { stdio: "inherit" });
    console.log("ESLint fixes completed successfully.");
    return true;
  } catch (error) {
    console.log("ESLint completed with warnings/errors.");
    return true; // Still consider this a success as it may have fixed some issues
  }
}

// Check for and fix common TS/JS issues
function checkForCommonIssues(directory) {
  console.log("Checking for common TypeScript/JavaScript issues...");

  // Fix tsconfig.json if it exists
  const tsConfigPath = path.join(directory, "tsconfig.json");
  if (fs.existsSync(tsConfigPath)) {
    try {
      const tsConfig = JSON.parse(fs.readFileSync(tsConfigPath, "utf8"));

      // Ensure strict mode is enabled
      if (!tsConfig.compilerOptions) {
        tsConfig.compilerOptions = {};
      }

      // Set recommended compiler options
      Object.assign(tsConfig.compilerOptions, {
        strict: true,
        noImplicitAny: true,
        strictNullChecks: true,
        forceConsistentCasingInFileNames: true,
        esModuleInterop: true,
      });

      fs.writeFileSync(tsConfigPath, JSON.stringify(tsConfig, null, 2), "utf8");
      console.log("Updated tsconfig.json with recommended settings.");
    } catch (error) {
      console.error("Error updating tsconfig.json:", error.message);
    }
  }

  // Check for and update any package.json
  const packageJsonPath = path.join(directory, "package.json");
  if (fs.existsSync(packageJsonPath)) {
    try {
      const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));

      // Check if TypeScript is installed
      if (!packageJson.devDependencies?.typescript) {
        console.log("TypeScript is not installed as a dev dependency.");
      }

      // Add script for type checking
      if (!packageJson.scripts) {
        packageJson.scripts = {};
      }

      if (!packageJson.scripts["typecheck"]) {
        packageJson.scripts["typecheck"] = "tsc --noEmit";
        console.log("Added typecheck script to package.json.");
        fs.writeFileSync(
          packageJsonPath,
          JSON.stringify(packageJson, null, 2),
          "utf8",
        );
      }
    } catch (error) {
      console.error("Error updating package.json:", error.message);
    }
  }

  return true;
}

// Main function
function main() {
  const rootDir = path.resolve(__dirname);
  console.log(`Running linting fixes for TypeScript/JavaScript in ${rootDir}`);

  let success = true;

  // Run fixes
  if (!runPrettier(rootDir)) {
    success = false;
  }

  if (!runEslint(rootDir)) {
    // This is informational, not an error
    console.log("ESLint skipped or not configured.");
  }

  if (!checkForCommonIssues(rootDir)) {
    success = false;
  }

  if (success) {
    console.log("TypeScript/JavaScript linting fixes completed successfully!");
  } else {
    console.error(
      "Some TypeScript/JavaScript linting fixes failed. See errors above.",
    );
    process.exit(1);
  }
}

main();
