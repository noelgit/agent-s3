# Agent-S3 Interactive WebView UI

This folder contains the React-based interactive UI components for Agent-S3 VS Code extension.

## Component Structure

### Main Components

- **App.tsx**: The main application component that handles routing messages to the appropriate interactive components.
- **index.tsx**: Entry point for the React application.

### Interactive Components

- **ApprovalRequest**: For interactive approval with options for user to choose from.
- **DiffViewer**: For displaying code changes with before/after views.
- **DebateVisualizer**: For displaying persona debates with structured phases.
- **ProgressIndicator**: For tracking task progress with steps and time estimation.

## Utilities

- **vscode.ts**: Utility for communicating with the VS Code extension.

## Message Protocol

The WebView and VS Code extension communicate using a structured message protocol:

### From VS Code Extension to WebView:

- `INTERACTIVE_APPROVAL`: Show an approval request dialog
- `INTERACTIVE_DIFF`: Show a diff viewer
- `DEBATE_VISUALIZATION`: Show a persona debate visualization
- `PROGRESS_INDICATOR`: Show a progress indicator

### From WebView to VS Code Extension:

- `APPROVAL_RESPONSE`: User's response to an approval request
- `DIFF_RESPONSE`: User's action on a diff view (approve, reject, open in editor)
- `DEBATE_RESPONSE`: User's action on a debate visualization
- `PROGRESS_RESPONSE`: User's action on a progress indicator (e.g., cancel)

## Development

To run the development server:

```bash
npm run watch-webview
```

To build for production:

```bash
npm run build-webview
```

## Integration with VS Code Extension

The UI components are integrated into the VS Code extension using the `InteractiveWebviewManager` class, which handles:

1. Loading the React application into a WebView panel
2. Managing communication between the extension and the WebView
3. Handling message events from the WebView

## WCAG 2.1 AA Compliance

These components are designed to be accessible and follow WCAG 2.1 AA standards:

- All interactive elements have proper keyboard navigation
- Color contrast meets AA requirements
- All components have appropriate ARIA attributes
- Text alternatives for non-text content
- Responsive design for different viewport sizes