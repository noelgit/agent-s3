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
- Ensure all updates pass lint, type, and syntax checks
- Never create duplicate code or content when updating files

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

### 4. Project Guidelines

#### Tech Stack Best Practices

##### TypeScript VS Code Extension Development
- Follow the VS Code Extension API guidelines for lifecycle management
- Use activation events appropriately to minimize startup impact
- Implement proper extension contribution points (commands, views, menus)
- Use WebviewPanel for rich UI components with proper message passing
- Implement proper error handling for VS Code commands and API calls
- Use the VS Code notification API for user feedback and errors
- Follow VS Code theming guidelines for UI consistency
- Implement proper command palette integration
- Use VS Code's built-in progress indicators for long-running operations
- Properly dispose of resources and event listeners to prevent memory leaks
- Implement proper workspace file system access using the VS Code API
- Use proper TypeScript typing for all VS Code API interactions

##### Python FastAPI Backend
- Follow FastAPI's dependency injection system for modular code
- Implement proper Pydantic models for request/response validation
- Use appropriate HTTP status codes for all API responses
- Implement proper exception handling with FastAPI's HTTPException
- Use async/await for I/O-bound operations to maximize throughput
- Implement proper rate limiting with appropriate headers
- Set up proper CORS configuration for extension communication
- Use FastAPI's built-in OpenAPI documentation
- Implement proper background task handling for long-running operations
- Use proper logging with structlog or similar libraries
- Implement proper middleware for authentication, request tracking, and error handling
- Set up health check endpoints for monitoring

##### AI Model Integration
- Implement proper token usage tracking and optimization
- Set up appropriate timeout handling for API calls to AI models
- Implement graceful fallback mechanisms when primary AI services fail
- Use streaming responses when appropriate to improve perceived performance
- Properly sanitize inputs to AI models to prevent prompt injection
- Cache common AI responses to reduce API costs and latency
- Implement proper retry logic with exponential backoff
- Set up proper error handling for AI model API responses
- Use appropriate context truncation strategies to stay within token limits
- Implement proper logging for AI interactions without exposing sensitive data

##### Vector Store and Repository Indexing
- Use chunking strategies appropriate for code repositories
- Implement incremental indexing to avoid full re-indexing
- Set up proper caching for frequently accessed embeddings
- Use appropriate similarity search algorithms for code retrieval
- Implement proper metadata storage alongside embeddings
- Set up proper index persistence and backup strategies
- Optimize vector dimensions for the specific use case
- Monitor vector store memory usage and implement sharding if necessary
- Implement proper error handling for embedding generation failures
- Provide fallback search mechanisms when vector search fails

##### Multimodal Processing
- Properly handle multiple image formats (PNG, JPEG, etc.)
- Implement proper image size validation and optimization
- Set up appropriate caching for processed images
- Ensure proper error handling for image processing failures
- Implement proper UI feedback during image processing
- Use appropriate compression for image transmission
- Ensure proper memory management when handling large images
- Implement proper validation for image inputs
- Use proper content type validation for image uploads
- Provide appropriate fallback when image processing fails

#### File Storage Best Practices
- Never store binary files (images, videos) directly in the database
- Always store files in the filesystem and save only paths in the database
- Implement secure file naming with timestamps and random IDs
- Use content-addressable storage when appropriate
- Implement proper backup strategies for file assets
- Consider CDN integration for global distribution
- Apply appropriate file compression techniques
- Implement access controls for sensitive files
- Use streaming for large file uploads/downloads

#### Error Handling Strategy
- Show proper error messages instead of silently failing
- Implement appropriate fallbacks for failed resource loading
- Return proper HTTP status codes with meaningful error messages
- Implement visually consistent error indicators across the application
- Avoid using fallback data for failed operations
- Implement proper logging with appropriate detail levels
- Use structured error objects with consistent formatting
- Implement graceful degradation for critical features
- Consider retry mechanisms with exponential backoff for transient failures
- Include troubleshooting information in error messages when appropriate

#### UI/UX Design Principles
- Create sleek, elegant, and modern interfaces
- Implement consistent layout patterns
- Design for both light and dark modes
- Use appropriate typography and components
- Design smooth, intuitive interactions
- Implement gradient fallbacks for imagery
- Never compromise non-functional requirements for design aesthetics
- Apply progressive disclosure for complex interfaces
- Maintain consistent visual hierarchy
- Implement skeleton screens during loading states
- Design mobile-first responsive layouts
- Provide clear feedback for user actions
- Maintain reasonable touch target sizes (at least 44x44 pixels)
- Apply appropriate empty states and zero-data states

#### Testing Approach
- Write unit tests for critical utility functions, API logic, and complex hooks
- Enable end-to-end testing for core user flows
- Test with accessibility tools 
- Ensure test coverage for public and authenticated functionality
- Implement snapshot testing for UI components
- Use test-driven development (TDD) where appropriate
- Set up continuous integration testing
- Test across multiple browsers and devices
- Implement visual regression testing
- Use contract testing for API integrations
- Perform stress testing and load testing for scalability
- Implement security penetration testing

#### Development Approach
- Check build errors before making changes
- Run appropriate type checking before submitting code
- Never modify files in dependency directories
- Validate assumptions by checking actual code and documentation
- Document issues, solutions, and progress
- Ensure responsive design for all screen sizes
- Follow gitflow or similar branching strategies
- Implement feature flags for controlled rollouts
- Practice continuous integration and continuous delivery (CI/CD)
- Conduct regular code reviews
- Apply refactoring techniques to improve existing code
- Monitor technical debt and address it systematically
- Document architectural decisions (ADRs)

#### DevOps Best Practices
- Implement infrastructure as code (IaC)
- Use containerization for consistent environments
- Apply proper environment separation (dev/staging/production)
- Implement comprehensive monitoring and alerting
- Use blue-green or canary deployments for reduced downtime
- Implement proper logging and observability
- Set up automated backup and recovery procedures
- Apply proper secret management
- Follow least privilege principle in all environments
- Implement chaos engineering practices where appropriate

## Issue Reporting Format
When reporting issues in code analysis, use this format:

Issue 1                   // Sequential number  
Category: Security           
Severity: High            // High | Medium | Low  
Confidence: High          // High | Medium | Low  
Description: This is a clear explanation of the issue  
Rationale: XSS vulnerability and lack of input validation could lead to attacks  
References: OWASP A03:2021 Injection, OWASP Input Validation Cheat Sheet  
Line Range: 45-46  
Suggested Fix:  
```--- /src/validation.ts
+++ /src/validation.ts
@@ -45,2 +45,2 @@
const validateInput = (input) => {
  -  return input;
  +  return sanitizeAndValidate(input);
```
