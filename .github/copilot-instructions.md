# GitHub Copilot Instructions

You are an AI assistant for development projects. Help with code generation, analysis, troubleshooting, and project guidance.

## Core Development Criteria

The following criteria should be applied to both code generation and code analysis:

### Security
- OWASP Top 10 vulnerabilities
- Authentication/Authorization issues with proper session handling
- Data protection and sensitive information exposure
- Input validation and proper escaping using appropriate validation libraries
- Content Security Policy (CSP) implementation with nonces
- Proper file upload security (MIME validation, size limits, path validation)
- API key protection and secure credential storage
- Secure HTTP headers
- Rate limiting for sensitive operations
- Server-side verification of client security measures
- Implement principle of least privilege in all access controls
- Use parameterized queries to prevent SQL injection
- Apply defense in depth with multiple security layers
- Implement secure password handling with proper hashing (bcrypt/Argon2)
- Regular security audit procedures and dependency scanning

### Performance
- Time complexity (aim for O(n) or better where practical)
- Resource usage optimization, especially for media content
- Database query efficiency:
  - Avoid N+1 queries
  - Implement proper pagination
  - Use strategic indices
- Memory management
- Asset optimization
- Appropriate API caching headers
- Debounced or throttled user inputs where appropriate
- Enable code splitting and lazy loading for large applications
- Implement proper resource hints (preconnect, preload, prefetch)
- Optimize critical rendering path
- Use efficient state management approaches
- Implement proper request batching and memoization
- Consider server-side rendering (SSR) or static site generation (SSG) when appropriate

### Code Quality
- SOLID principles for modularity
- Clean code practices with clear naming conventions
- Comprehensive error handling with recovery strategies
- Thorough documentation for all exported functions
- Adherence to project-specific guidelines
- Alignment with defined user stories and acceptance criteria
- No fallback data for failed operations
- Testable code structure
- Apply DRY (Don't Repeat Yourself) principle while avoiding premature abstraction
- Use consistent code formatting with automated tools
- Implement proper versioning for APIs
- Follow semantic versioning for packages
- Use meaningful commit messages with conventional commits format
- Apply continuous integration best practices
- Prioritize immutability when appropriate

### Accessibility
- WCAG 2.1 Level AA compliance
- Semantic HTML elements
- Sufficient color contrast
- Keyboard navigation support
- Proper ARIA attributes
- Alternative text for images
- Focus management for interactive elements
- Support for screen readers and assistive technologies
- Proper heading hierarchy (h1-h6)
- Skip navigation links for keyboard users
- Appropriate text resizing and zooming support
- Reduced motion options for vestibular disorders
- Adequate timeout settings for form submissions
- Proper form labels and error states

## Assistance Categories

### 1. Code Generation
When generating code, apply all the core criteria above plus:

- Follow established project structure and naming conventions
- Use appropriate type definitions for strongly-typed languages
- Create comprehensive documentation comments for all exported functions
- Include file headers on all new files
- Use appropriate design patterns based on the framework in use
- Separate concerns by using appropriate architecture for the framework
- Organize by feature directories when appropriate
- Create reusable utilities and hooks
- Centralize constants and types
- Follow idiomatic patterns for the language/framework being used
- Consider backwards compatibility when updating existing code
- Apply progressive enhancement where appropriate
- Implement proper feature detection instead of browser detection
- Design for extension but closed for modification (Open/Closed principle)
- Use dependency injection where appropriate for testability

### 2. Code Analysis
When analyzing code, apply all the core criteria above and report issues according to the format below.

### 3. Troubleshooting Assistance
For troubleshooting, consider these common issues and solutions:

- Database connectivity issues
- Server connectivity issues
- Build errors and dependency problems
- Network and API connection issues
- Environment configuration problems
- Browser compatibility issues
- Memory leaks and performance degradation
- Version conflicts between dependencies
- Cross-origin resource sharing (CORS) issues
- Caching problems
- Asynchronous timing issues
- Environment-specific behavior differences


## Tech Stack Best Practices

### JavaScript
- Follow best practices for this technology
- Apply proper structure and patterns
- Implement appropriate error handling

### Python
- Follow best practices for this technology
- Apply proper structure and patterns
- Implement appropriate error handling

### TypeScript
- Follow best practices for this technology
- Apply proper structure and patterns
- Implement appropriate error handling

### react
- Follow best practices for this technology
- Apply proper structure and patterns
- Implement appropriate error handling

### aiohttp
- Follow best practices for this technology
- Apply proper structure and patterns
- Implement appropriate error handling

### fastapi
- Follow best practices for this technology
- Apply proper structure and patterns
- Implement appropriate error handling

### flask
- Follow best practices for this technology
- Apply proper structure and patterns
- Implement appropriate error handling

