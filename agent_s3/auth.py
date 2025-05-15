"""Implements user authentication via GitHub SSO (OAuth integration)."""

import json
import os
import webbrowser
import platform
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Optional, Any, Tuple
from urllib.parse import parse_qs, urlparse
import secrets
import hashlib
import sys
import logging

# Define required dependencies - use proper requirements.txt for actual dependency management
try:
    import requests
    import jwt
    from github import Github, GithubIntegration
except ImportError as e:
    logging.error(f"Missing required dependency: {e}")
    print(f"ERROR: Missing required authentication dependencies: {e}", file=sys.stderr)
    print("\nPlease install the missing dependencies with:", file=sys.stderr)
    print("  pip install -r requirements.txt", file=sys.stderr)
    
    # Only raise if actually running the code (not during static analysis)
    if not any(analyzer in sys.modules for analyzer in ['pyright', 'pylance', 'jedi']):
        raise ImportError("Required dependencies missing. See above for installation instructions.")

# Import local modules
try:
    from .config import DEV_MODE, DEV_GITHUB_TOKEN, GITHUB_APP_ID, GITHUB_PRIVATE_KEY, TARGET_ORG
except ImportError:
    # For standalone testing
    DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
    DEV_GITHUB_TOKEN = os.getenv("DEV_GITHUB_TOKEN", "")
    GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
    GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY", "")
    TARGET_ORG = os.getenv("TARGET_ORG", "")

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = "http://localhost:8000/callback"
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"

# Token storage location
TOKEN_FILE = os.path.expanduser("~/.agent_s3/github_token.json")


def save_token(token_data: Dict[str, Any]) -> None:
    """Save the GitHub token data to a file.
    
    Args:
        token_data: Dictionary containing the token and related information
    """
    # Create directory with secure permissions
    token_dir = os.path.dirname(TOKEN_FILE)
    os.makedirs(token_dir, exist_ok=True)
    
    try:
        # Generate a machine-specific key based on username and hostname
        machine_id = f"{platform.node()}-{os.getlogin()}"
        key = hashlib.sha256(machine_id.encode()).digest()[:16]  # Use first 16 bytes as AES key
        
        # Convert token data to JSON string
        token_json = json.dumps(token_data)
        
        # Simple XOR-based obfuscation (not for high security, but prevents plaintext storage)
        obfuscated = bytearray()
        for i, char in enumerate(token_json.encode()):
            obfuscated.append(char ^ key[i % len(key)])
        
        # Save with restricted permissions
        with open(TOKEN_FILE, "wb") as f:
            f.write(obfuscated)
        
        # Set file permissions (POSIX only)
        if os.name == 'posix':
            import stat
            os.chmod(TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0o600 - owner read/write only
    except Exception as e:
        print(f"Warning: Could not securely save token: {e}")
        # Fallback to basic storage if encryption fails
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f)


def load_token() -> Optional[Dict[str, Any]]:
    """Load the GitHub token data from a file.
    
    Returns:
        The token data as a dictionary, or None if the file doesn't exist
    """
    if not os.path.exists(TOKEN_FILE):
        return None
    
    try:
        # Check if we're using the encrypted format or the old plaintext format
        with open(TOKEN_FILE, "rb") as f:
            content = f.read()
            
        try:
            # Try to parse as JSON (old format)
            return json.loads(content.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Not valid JSON, assume encrypted format
            # Generate key from machine-specific data
            machine_id = f"{platform.node()}-{os.getlogin()}"
            key = hashlib.sha256(machine_id.encode()).digest()[:16]
            
            # Decrypt using the same XOR method
            decrypted = bytearray()
            for i, byte in enumerate(content):
                decrypted.append(byte ^ key[i % len(key)])
            
            return json.loads(decrypted.decode('utf-8'))
    except Exception as e:
        print(f"Warning: Could not load token: {e}")
        return None


def validate_token(token: str) -> bool:
    """Validate that the token is still valid.
    
    Args:
        token: The GitHub OAuth token to validate
        
    Returns:
        True if the token is valid, False otherwise
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(f"{GITHUB_API_URL}/user", headers=headers)
    return response.status_code == 200


class GitHubOAuthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for GitHub OAuth callback."""
    
    code: Optional[str] = None
    state: Optional[str] = None  # For CSRF protection
    expected_state: Optional[str] = None  # Static class variable to hold the expected state
    
    def do_GET(self) -> None:
        """Handle GET requests to the server."""
        parsed_url = urlparse(self.path)
        
        if parsed_url.path == "/callback":
            # Extract the authorization code
            query = parse_qs(parsed_url.query)
            if "code" in query and "state" in query:
                # Verify state parameter to prevent CSRF attacks
                received_state = query["state"][0]
                if received_state != GitHubOAuthHandler.expected_state:
                    self.send_response(400)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<html><body><h1>Authentication Failed</h1><p>Invalid state parameter - possible CSRF attack.</p></body></html>")
                    return
                
                GitHubOAuthHandler.code = query["code"][0]
                GitHubOAuthHandler.state = received_state
                
                # Display success page
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Authentication Successful</h1><p>You can close this window now.</p></body></html>")
            else:
                # Display error page
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                error_msg = b"<html><body><h1>Authentication Failed</h1><p>Missing required parameters. Both code and state are required.</p></body></html>"
                self.wfile.write(error_msg)
        else:
            # Handle other paths
            self.send_response(404)
            self.end_headers()


def authenticate_user() -> Optional[str]:
    """Authenticate the user with GitHub SSO.
    
    Returns:
        The GitHub OAuth token if authentication is successful, None otherwise
    """
    # DEV_MODE bypass for local testing
    if DEV_MODE:
        if DEV_GITHUB_TOKEN:
            print("DEV_MODE enabled, using DEV_GITHUB_TOKEN")
            # Skip org membership check in dev mode
            return DEV_GITHUB_TOKEN
        else:
            print("DEV_MODE enabled but DEV_GITHUB_TOKEN not set.")
            return None

    # Check if we have a valid token already
    token_data = load_token()
    if token_data and "access_token" in token_data:
        if validate_token(token_data["access_token"]):
            print("Using existing GitHub authentication")
            token = token_data["access_token"]
            # Enforce org membership
            if _is_member_of_allowed_orgs(token):
                return token
            else:
                print("Error: GitHub token does not belong to an allowed organization.")
                return None
    
    # Check if we have the required environment variables
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        print("Error: GitHub OAuth credentials not found.")
        print("Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables.")
        return None
    
    # Start the OAuth flow
    # Generate a secure random state parameter for CSRF protection
    state = secrets.token_urlsafe(16)
    GitHubOAuthHandler.expected_state = state
    auth_url = f"{GITHUB_AUTH_URL}?client_id={GITHUB_CLIENT_ID}&redirect_uri={GITHUB_REDIRECT_URI}&scope=repo&state={state}"
    print("Opening browser for GitHub authentication...")
    webbrowser.open(auth_url)
    
    # Start a server to receive the callback
    server = HTTPServer(("localhost", 8000), GitHubOAuthHandler)
    print("Waiting for authentication...")
    
    # Handle one request (the callback from GitHub)
    server.handle_request()
    
    # Check if we received the code
    if not GitHubOAuthHandler.code:
        print("Authentication failed: No code received")
        return None
    
    # Exchange the code for a token
    response = requests.post(
        GITHUB_TOKEN_URL,
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": GitHubOAuthHandler.code,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "state": GitHubOAuthHandler.state  # Include state in token exchange
        },
        headers={"Accept": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Authentication failed: {response.text}")
        return None
    
    token_data = response.json()
    if "access_token" not in token_data:
        print("Authentication failed: No access token in response")
        return None
    
    # Save the token for future use
    save_token(token_data)
    print("GitHub authentication successful")
    # Enforce organization membership
    token = token_data.get("access_token")
    if token and _is_member_of_allowed_orgs(token):
        return token
    print("Error: Authenticated user is not a member of the allowed organization.")
    return None


def _is_member_of_allowed_orgs(token: str) -> bool:
    """Check if the user belongs to any of the allowed GitHub organizations."""
    orgs_env = os.getenv("GITHUB_ORG", "")
    allowed_orgs = [o.strip() for o in orgs_env.split(",") if o.strip()]
    if not allowed_orgs:
        # No org restriction set
        return True
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    try:
        resp = requests.get(f"{GITHUB_API_URL}/user/orgs", headers=headers)
        if resp.status_code == 200:
            user_orgs = [org.get("login") for org in resp.json()]
            return any(o in user_orgs for o in allowed_orgs)
    except Exception as e:
        print(f"Error checking organization membership: {e}")
    return False


def _validate_token_and_check_org(token: str, target_org: str = "", expected_username: str = None) -> Tuple[bool, Optional[str]]:
    """Validate token and check org membership in a single function to reduce API calls.
    
    Args:
        token: GitHub OAuth token to validate
        target_org: Organization to check membership for (can be empty to skip check)
        expected_username: Username to verify (optional validation)
        
    Returns:
        Tuple of (is_valid_member, username)
    """
    if not token:
        return False, None
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get user info first
    try:
        user_response = requests.get(f"{GITHUB_API_URL}/user", headers=headers)
        if user_response.status_code != 200:
            return False, None
            
        user_data = user_response.json()
        username = user_data.get("login")
        
        # Verify username if expected_username is provided
        if expected_username and username != expected_username:
            return False, None
            
        # If no organization check is needed, return success
        if not target_org:
            return True, username
            
        # Use the more efficient check for organization membership
        # Direct API call instead of the more expensive /user/orgs call
        org_check_url = f"{GITHUB_API_URL}/orgs/{target_org}/members/{username}"
        org_response = requests.get(org_check_url, headers=headers)
        
        # 204 status code indicates membership, 404 indicates not a member
        if org_response.status_code == 204:
            return True, username
            
        return False, None
            
    except Exception as e:
        print(f"Error in token validation: {e}")
        return False, None


class AuthorizationError(Exception):
    """Raised when the user is not authorized to use Agent-S3."""
    pass


def get_current_user():
    """
    Retrieve the current GitHub user, using DEV_MODE token or OAuth App flow.
    Verify that the user is a member of TARGET_ORG.
    
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
            "iat": now - 60,  # Issued 60 seconds ago to account for clock skew
            "exp": now + (10 * 60),  # Expires in 10 minutes
            "iss": app_id,
            "jti": secrets.token_hex(16)  # Add unique JWT ID to prevent replay attacks
        }
        
        try:
            # Explicitly specify algorithm to prevent algorithm switching attacks
            encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
            
            # Best practice: verify the token after generating to ensure it's valid
            # This catches issues with the private key format or encoding problems
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(
                jwt.api_jwk.get_key(private_key)
            ) if hasattr(jwt, 'algorithms') else None
            
            if public_key:
                jwt.decode(
                    encoded_jwt, 
                    public_key, 
                    algorithms=["RS256"],
                    options={"verify_signature": True, "verify_exp": True, "verify_iss": True}
                )
        except Exception as e:
            raise AuthorizationError(f"Failed to create or verify JWT: {e}")
        
        integration = GithubIntegration(app_id, private_key)
        # Get installation token
        installations = integration.get_installations()
        if not installations:
            raise AuthorizationError("No GitHub App installations found.")
        # Use first installation
        installation_id = installations[0].id
        token = integration.get_access_token(installation_id).token
        gh = Github(token)
    
    user = gh.get_user()
    username = user.login
    
    # Verify org membership
    # Use combined token validation and org membership check to reduce API calls
    is_member, verified_username = _validate_token_and_check_org(token, TARGET_ORG, username)
    
    if not is_member:
        raise AuthorizationError(f"User '{username}' is not a member of the organization '{TARGET_ORG}'")
    
    return username
