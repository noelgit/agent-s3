// ESLint configuration for JavaScript and React projects
// See: https://eslint.org/docs/latest/use/configure/
module.exports = {
  root: true,
  env: {
    browser: true,
    node: true,
    es2021: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
  ],
  parserOptions: {
    ecmaVersion: 12,
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
  },
  plugins: [
    'react',
  ],
  rules: {
    // Add project-specific rules here
  },
  settings: {
    react: {
      version: 'detect',
    },
  },
};
