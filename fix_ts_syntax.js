#!/usr/bin/env node
/**
 * Script to fix the TypeScript syntax issues with the concatenation operator
 * This script replaces:
 *   textContent +
 *       = 'value'
 * with:
 *   textContent += 'value'
 */

const fs = require("fs");
const path = require("path");

// Function to fix the syntax in a file
function fixSyntaxInFile(filePath) {
  try {
    let content = fs.readFileSync(filePath, "utf8");

    // Find all occurrences of the pattern
    const regex = /textContent \+\s*\n\s*=\s*/g;
    let match;
    let positions = [];

    while ((match = regex.exec(content)) !== null) {
      positions.push({
        start: match.index,
        end: match.index + match[0].length,
      });
    }

    // Replace from end to start to avoid offset issues
    positions.reverse().forEach((pos) => {
      content =
        content.substring(0, pos.start) +
        "textContent += " +
        content.substring(pos.end);
    });

    if (positions.length > 0) {
      fs.writeFileSync(filePath, content, "utf8");
      console.log(`Fixed ${positions.length} syntax issues in ${filePath}`);
      return true;
    }

    return false;
  } catch (error) {
    console.error(`Error processing ${filePath}:`, error.message);
    return false;
  }
}

// Main function
function main() {
  const files = [
    "./tests/playwright/fixtures.ts",
    "./tests/playwright/specs/story1-initialize-workspace.spec.ts",
    "./tests/playwright/specs/story2-code-change-request.spec.ts",
    "./tests/playwright/specs/story4-helper-commands.spec.ts",
  ];

  let fixedCount = 0;

  // Process each file
  for (const file of files) {
    const filePath = path.resolve(__dirname, file);
    if (fs.existsSync(filePath)) {
      const fixed = fixSyntaxInFile(filePath);
      if (fixed) {
        fixedCount++;
      }
    } else {
      console.warn(`File not found: ${filePath}`);
    }
  }

  console.log(`Fixed syntax issues in ${fixedCount} files.`);
}

main();

main();
