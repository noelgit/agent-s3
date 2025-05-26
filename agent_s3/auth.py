"""Implements user authentication via GitHub SSO (OAuth integration)."""

import json
import logging
import os
import re
import secrets
import stat
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet, InvalidToken

from .logging_utils import redact_auth_headers

# Define required dependencies - use proper requirements.txt for actual dependency management
try:
    import requests
    import jwt
    from github import Github, GithubIntegration
except Exception as e:  # pragma: no cover - optional deps
    logging.error("Missing required dependency: %s", str(e))
    print(
        "ERROR: Missing required authentication dependencies: %s" % str(e),
        file=sys.stderr,
    )
    print("\nPlease install the missing dependencies with:", file=sys.stderr)
    print("  pip install -r requirements.txt", file=sys.stderr)

    Github = None  # type: ignore
    GithubIntegration = None  # type: ignore

# Import local modules
try:
    from .config import (
        DEV_MODE,
        DEV_GITHUB_TOKEN,
        GITHUB_APP_ID,
        GITHUB_PRIVATE_KEY,
        TARGET_ORG,
        HTTP_DEFAULT_TIMEOUT,
    )
except ImportError:
    # For standalone testing
    DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
    DEV_GITHUB_TOKEN = os.getenv("DEV_GITHUB_TOKEN", "")
    GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
    GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY", "")
    TARGET_ORG = os.getenv("TARGET_ORG", "")
    HTTP_DEFAULT_TIMEOUT = float(os.getenv("HTTP_DEFAULT_TIMEOUT", "30.0"))

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = "http://localhost:8000/callback"

# Initialize logger
logger = logging.getLogger(__name__)
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"


def _generate_secure_state() -> str:
    """Generate a cryptographically secure state parameter for OAuth.
    
    Returns:
        A secure random state string with timestamp and validation
    """
    # Generate base random state
    base_state = secrets.token_urlsafe(24)
    
    # Add timestamp for validation
    timestamp = str(int(time.time()))
    
    # Combine and encode
    state_data = f"{base_state}:{timestamp}"
    
    # Add additional entropy
    entropy = secrets.token_urlsafe(8)
    
    return f"{state_data}:{entropy}"


def _validate_state_security(received_state: str, expected_state: str) -> bool:
    """Validate OAuth state parameter with enhanced security checks.
    
    Args:
        received_state: State received from OAuth callback
        expected_state: Expected state we generated
        
    Returns:
        True if state is valid and secure
    """
    if not received_state or not expected_state:
        return False
        
    # Basic equality check
    if received_state != expected_state:
        return False
        
    # Parse state components
    try:
        parts = expected_state.split(':')
        if len(parts) != 3:
            return False
            
        _, timestamp_str, _ = parts
        timestamp = int(timestamp_str)
        
        # Check if state is not too old (5 minutes max)
        current_time = int(time.time())
        if current_time - timestamp > 300:
            logger.warning("OAuth state expired")
            return False
            
        return True
        
    except (ValueError, IndexError):
        logger.error("Invalid state format")
        return False

# Token storage location
TOKEN_FILE = os.path.expanduser("~/.agent_s3/github_token.json")

# Environment variable used to store the encryption key for the token file.
# The key should be generated with ``cryptography.fernet.Fernet.generate_key``
# and kept secret (e.g., via an OS keyring or environment management tool).
TOKEN_ENCRYPTION_KEY_ENV = "AGENT_S3_ENCRYPTION_KEY"


def save_token(token_data: Dict[str, Any]) -> None:
    """Save the GitHub token data to a file.

    Args:
        token_data: Dictionary containing the token and related information

    Raises:
        RuntimeError: If :data:`AGENT_S3_ENCRYPTION_KEY` is not set or the token
            cannot be encrypted.
    """
    # Create directory with secure permissions
    token_dir = os.path.dirname(TOKEN_FILE)
    os.makedirs(token_dir, exist_ok=True)

    key = os.environ.get(TOKEN_ENCRYPTION_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"{TOKEN_ENCRYPTION_KEY_ENV} must be set to store GitHub tokens"
        )

    token_json = json.dumps(token_data)

    try:
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        encrypted = fernet.encrypt(token_json.encode("utf-8"))
    except Exception as e:  # pragma: no cover - unexpected failures
        msg = redact_auth_headers(f"Failed to encrypt token: {e}")
        print(msg)
        raise RuntimeError("Token encryption failed") from e

    try:
        with open(TOKEN_FILE, "wb") as f:
            f.write(encrypted)
        if os.name == "posix":
            os.chmod(TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except IOError as e:
        msg = redact_auth_headers(f"Failed to write token file: {e}")
        print(msg)
        raise RuntimeError("Token storage failed") from e


def load_token() -> Optional[Dict[str, Any]]:
    """Load the GitHub token data from a file.

    Returns:
        The token data as a dictionary, or None if the file doesn't exist
    """
    if not os.path.exists(TOKEN_FILE):
        return None

    key = os.environ.get(TOKEN_ENCRYPTION_KEY_ENV)
    if not key:
        print("Warning: Encryption key not set; cannot decrypt token")
        return None

    try:
        with open(TOKEN_FILE, "rb") as f:
            content = f.read()
    except IOError as io_err:
        msg = redact_auth_headers(f"Error reading token file: {io_err}")
        print(msg)
        raise RuntimeError("Failed to read token file") from io_err

    try:
        fernet = Fernet(key.encode() if isinstance(key, str) else key)
        decrypted = fernet.decrypt(content)
    except (InvalidToken, ValueError) as err:
        msg = redact_auth_headers(f"Could not decrypt token: {err}")
        print(msg)
        raise RuntimeError("Token decryption failed") from err
    except Exception as err:  # pragma: no cover - unexpected failures
        msg = redact_auth_headers(f"Error decrypting token: {err}")
        print(msg)
        raise RuntimeError("Token decryption failed") from err

    try:
        return json.loads(decrypted.decode("utf-8"))
    except Exception as err:  # pragma: no cover - unexpected failures
        msg = redact_auth_headers(f"Could not load token: {err}")
        print(msg)
        raise RuntimeError("Token load failed") from err


def validate_token(token: str) -> bool:
    """Validate that the token is still valid with comprehensive checks.

    Args:
        token: The GitHub OAuth token to validate

    Returns:
        True if the token is valid, False otherwise
    """
    if not token or not isinstance(token, str) or len(token.strip()) == 0:
        return False
        
    # Validate token format (GitHub tokens are typically 40-50 chars alphanumeric)
    if not re.match(r'^[a-zA-Z0-9_]{20,50}$', token.strip()):
        return False
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    try:
        response = requests.get(
            f"{GITHUB_API_URL}/user",
            headers=headers,
            timeout=HTTP_DEFAULT_TIMEOUT,
        )
        
        # Check for successful authentication
        if response.status_code != 200:
            return False
            
        # Validate response content
        try:
            user_data = response.json()
            # Ensure we got valid user data
            if not isinstance(user_data, dict) or 'id' not in user_data:
                return False
        except (ValueError, KeyError):
            return False
            
        # Check token scopes if available
        scopes = response.headers.get('X-OAuth-Scopes', '')
        required_scopes = {'repo', 'user'}
        available_scopes = set(scope.strip() for scope in scopes.split(',') if scope.strip())
        
        # Warn if missing critical scopes but don't fail validation
        if not required_scopes.intersection(available_scopes):
            logger.warning("Token lacks required scopes for full functionality")
            
        return True
        
    except requests.RequestException as e:
        logger.error(f"Token validation failed: {e}")
        return False


class GitHubOAuthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for GitHub OAuth callback."""

    code: Optional[str] = None
    state: Optional[str] = None  # For CSRF protection
    expected_state: Optional[str] = None  # Static class variable

    def do_GET(self) -> None:  # BaseHTTPRequestHandler expects do_GET
        """Handle GET requests to the server."""
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/callback":
            # Extract the authorization code
            query = parse_qs(parsed_url.query)
            if "code" in query and "state" in query:
                # Verify state parameter to prevent CSRF attacks with enhanced validation
                received_state = query["state"][0]
                if not _validate_state_security(received_state, GitHubOAuthHandler.expected_state):
                    self._send_error_response(
                        "Authentication Failed",
                        "Invalid or expired state parameter - possible CSRF attack.",
                    )
                    return

                GitHubOAuthHandler.code = query["code"][0]
                GitHubOAuthHandler.state = received_state

                # Display success page
                self._send_success_response()
                return

            # Display error page
            self._send_error_response(
                "Authentication Failed",
                "Missing required parameters. Both code and state are required.",
            )
        else:
            # Handle other paths
            self.send_response(404)
            self.end_headers()

    def _send_error_response(self, title: str, message: str) -> None:
        """Send an error response to the client."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        error_html = (
            f"<html><body><h1>{title}</h1>" f"<p>{message}</p></body></html>"
        ).encode("utf-8")
        self.wfile.write(error_html)

    def _send_success_response(self) -> None:
        """Send a success response to the client."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        success_html = (
            "<html><body><h1>Authentication Successful</h1>"
            "<p>You can close this window now.</p></body></html>"
        ).encode("utf-8")
        self.wfile.write(success_html)


def authenticate_user() -> Optional[str]:
    """Authenticate the user with GitHub SSO.

    Returns:
        The GitHub OAuth token if authentication is successful, None otherwise
    """
    token = None

    if DEV_MODE:
        if DEV_GITHUB_TOKEN:
            print("DEV_MODE enabled, using DEV_GITHUB_TOKEN")
            return DEV_GITHUB_TOKEN
        print("DEV_MODE enabled but DEV_GITHUB_TOKEN not set.")
        return None

    # Check for existing valid token
    token_data = load_token()
    if token_data and "access_token" in token_data:
        token = token_data["access_token"]
        if validate_token(token) and _is_member_of_allowed_orgs(token):
            print("Using existing GitHub authentication")
            return token
        print("Error: GitHub token invalid or unauthorized")
        token = None

    # Start OAuth flow if no valid token
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        print(
            "Error: GitHub OAuth credentials not found.\n"
            "Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment "
            "variables."
        )
        return None

    # Get new token via OAuth with enhanced security
    state = _generate_secure_state()
    GitHubOAuthHandler.expected_state = state
    auth_params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "repo",
        "state": state,
    }
    auth_url = (
        f"{GITHUB_AUTH_URL}?" f"{'&'.join(f'{k}={v}' for k, v in auth_params.items())}"
    )

    print("Opening browser for GitHub authentication...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8000), GitHubOAuthHandler)
    print("Waiting for authentication...")
    server.handle_request()

    if not GitHubOAuthHandler.code:
        print("Authentication failed: No code received")
        return None

    # Exchange code for token
    response = requests.post(
        GITHUB_TOKEN_URL,
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": GitHubOAuthHandler.code,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "state": GitHubOAuthHandler.state,
        },
        headers={"Accept": "application/json"},
        timeout=HTTP_DEFAULT_TIMEOUT,
    )

    if response.status_code == 200:
        token_data = response.json()
        if "access_token" in token_data:
            try:
                save_token(token_data)
            except RuntimeError as e:
                print(redact_auth_headers(f"Error saving token: {e}"))
                return None
            print("GitHub authentication successful")
            token = token_data.get("access_token")
            if token and _is_member_of_allowed_orgs(token):
                return token
            print("Error: User is not a member of the allowed organization.")

    return None


def _is_member_of_allowed_orgs(token: str) -> bool:
    """Check if the user belongs to any of the allowed GitHub organizations."""
    orgs_env = os.getenv("GITHUB_ORG", "")
    allowed_orgs = [o.strip() for o in orgs_env.split(",") if o.strip()]
    if not allowed_orgs:
        return True

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        resp = requests.get(
            f"{GITHUB_API_URL}/user/orgs",
            headers=headers,
            timeout=HTTP_DEFAULT_TIMEOUT,
        )
        if resp.status_code == 200:
            user_orgs = [org.get("login") for org in resp.json()]
            return any(org in user_orgs for org in allowed_orgs)
    except requests.RequestException as e:
        print(redact_auth_headers(f"Error checking organization membership: {e}"))
    return False


def _validate_token_and_check_org(
    token: str, target_org: str = "", expected_username: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Validate token and check org membership in a single function.

    Args:
        token: GitHub OAuth token to validate
        target_org: Organization to check membership for (empty to skip check)
        expected_username: Username to verify (optional validation)

    Returns:
        Tuple of (is_valid_member, username)
    """
    if not token:
        return False, None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        # Get user info first
        user_response = requests.get(
            f"{GITHUB_API_URL}/user",
            headers=headers,
            timeout=HTTP_DEFAULT_TIMEOUT,
        )
        if user_response.status_code != 200:
            return False, None

        user_data = user_response.json()
        username = user_data.get("login")

        if expected_username and username != expected_username:
            return False, None

        if not target_org:
            return True, username

        # Check org membership
        org_check_url = f"{GITHUB_API_URL}/orgs/{target_org}/members/{username}"
        org_response = requests.get(
            org_check_url,
            headers=headers,
            timeout=HTTP_DEFAULT_TIMEOUT,
        )
        if org_response.status_code == 204:
            return True, username

        return False, None
    except requests.RequestException as e:
        print(redact_auth_headers(f"Error in token validation: {e}"))
        return False, None
    except Exception as e:  # pragma: no cover - unexpected errors
        print(redact_auth_headers(f"Unexpected error during token check: {e}"))
        return False, None


class AuthorizationError(Exception):
    """Raised when the user is not authorized to use Agent-S3."""


def get_current_user() -> str:
    """Retrieve the current GitHub user and verify org membership.

    Returns:
        The username of the authenticated user.

    Raises:
        AuthorizationError: If the user is not authorized.
    """
    if os.getenv("ENV") == "development" and DEV_MODE:
        token = DEV_GITHUB_TOKEN
        if not token:
            raise AuthorizationError("DEV_GITHUB_TOKEN not set in development mode.")
        gh = Github(token)
    else:
        # Create JWT for GitHub App authentication
        app_id = GITHUB_APP_ID
        private_key = GITHUB_PRIVATE_KEY
        if not app_id or not private_key:
            raise AuthorizationError("GitHub App credentials not configured.")

        # Generate JWT with proper security practices
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60 seconds ago for clock skew
            "exp": now + (10 * 60),  # Expires in 10 minutes
            "iss": app_id,
            "jti": secrets.token_hex(16),  # Unique JWT ID to prevent replay
        }

        try:
            encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
            # Verify the JWT if possible
            try:
                jwt.decode(
                    encoded_jwt,
                    private_key,
                    algorithms=["RS256"],
                    options={
                        "verify_signature": True,
                        "verify_exp": True,
                        "verify_iss": True,
                    },
                )
            except jwt.InvalidTokenError:
                # If verification fails, the token might still be valid
                # We'll let the GitHub API validate it instead
                pass
        except Exception as e:
            msg = f"Failed to create or verify JWT: {e}"
            raise AuthorizationError(msg) from e

        integration = GithubIntegration(app_id, private_key)
        installations = integration.get_installations()
        if not installations:
            raise AuthorizationError("No GitHub App installations found.")

        # Use first installation
        installation_id = installations[0].id
        token = integration.get_access_token(installation_id).token
        gh = Github(token)

    user = gh.get_user()
    username = user.login  # We need this username for verification

    # Verify org membership
    # Use combined validation to reduce API calls
    is_member, _ = _validate_token_and_check_org(token, TARGET_ORG, username)

    if not is_member:
        msg = f"User '{username}' is not a member of the organization '{TARGET_ORG}'"
        raise AuthorizationError(msg)

    return username
