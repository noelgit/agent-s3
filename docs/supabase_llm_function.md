# Supabase LLM Function

## Overview
This serverless function provides secure access to large language model (LLM) services for Agent-S3. The function verifies the caller's GitHub organization membership before forwarding the request to the LLM provider. Only sanitized responses are returned to the client.

## Request Format
- **Method:** `POST`
- **Headers:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <GitHub token>`
- **Body:**
  ```json
  {
    "messages": [
      {"role": "user", "content": "..."}
    ],
    "model": "gpt-4",
    "temperature": 0.7
  }
  ```

## Token Validation
1. Extract the token from the `Authorization` header.
2. Query the GitHub API to check the caller's membership in the allowed organization:
   ```http
   GET https://api.github.com/user/memberships/orgs/<ORG>
   Authorization: Bearer <token>
   ```
3. Proceed only if the membership state is `active`.

## LLM Invocation
- Retrieve the LLM API key from the server's secure storage (environment variable or secret manager).
- Forward the validated request to the LLM provider.
- Sanitize the LLM output to remove any disallowed content before returning the JSON response.

## Security Tips
- Serve the function exclusively over **HTTPS**.
- Ensure the `SUPABASE_URL` (or `supabase_url` config) begins with `https://`.
- Use short-lived GitHub tokens with limited scopes (e.g., `read:org`).
- Do not persist incoming tokens on disk.
- Log only minimal metadata and avoid storing prompts or responses unless required.

