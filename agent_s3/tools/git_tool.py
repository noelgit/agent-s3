"""Wraps Git commands and implements GitHub issue and PR creation."""

import os
import subprocess
import logging
import re
import time
import shlex
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List, Union

import requests


class GitTool:
    """Tool for Git operations and GitHub API interactions."""

    def __init__(self, github_token: Optional[str] = None,
                 org: Optional[str] = None,
                 repo: Optional[str] = None,
                 terminal_executor = None):
        """Initialize the Git tool.

        Args:
            github_token: GitHub OAuth token or dev token for API access
            org: Target GitHub organization (overrides auto-detection)
            repo: Target GitHub repository name (overrides auto-detection)
            terminal_executor: Optional terminal executor for secure command execution
        """
        self.github_token = github_token
        self.github_api_url = "https://api.github.com"
        self.org_override = org
        self.repo_override = repo
        self.terminal_executor = terminal_executor
        self.logger = logging.getLogger(__name__)

        # Rate limiting tracking
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0

        # Initialize cache
        self._repo_info_cache = None
        self._repo_info_cache_time = 0

        # Error categorization constants - used for more specific error handling
        self.ERROR_CATEGORIES = {
            'permission': ['permission denied', 'access denied', 'authentication failed', '403 forbidden'],
            'network': ['could not resolve host', 'connection refused', 'connection timed out', 'network unreachable'],
            'conflict': ['conflict', 'refusing to merge unrelated histories', 'failed to push', 'non-fast-forward updates'],
            'not_found': ['repository not found', 'path not found', 'reference not found', 'did not match any', '404 not found'],
            'rate_limit': ['rate limit', 'secondary rate limit', 'abuse detection'],
            'invalid_reference': ['invalid reference', 'bad revision', 'not a valid object name'],
        }

        # Default retry settings
        self.max_retries = 3
        self.retry_delay = 2  # Initial delay in seconds

    def run_git_command(self, command: str, max_retries: int = None, retry_delay: int = None)
         -> Tuple[int, str]:        """Run a Git command securely with improved error handling and retry logic.

        Args:
            command: The Git command to run (without 'git' prefix)
            max_retries: Maximum number of retries (defaults to self.max_retries)
            retry_delay: Initial delay between retries in seconds (defaults to self.retry_delay)

        Returns:
            A tuple containing (return code, output)
        """
        if max_retries is None:
            max_retries = self.max_retries
        if retry_delay is None:
            retry_delay = self.retry_delay

        retries = 0
        current_delay = retry_delay

        while retries <= max_retries:
            try:
                full_command = ['git'] + shlex.split(command)

                # If terminal executor is provided, use it for secure execution
                if self.terminal_executor:
                    return_code, output = self.terminal_executor.run_command(full_command)
                else:
                    # Otherwise fall back to subprocess
                    process = subprocess.Popen(
                        full_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    output, _ = process.communicate()
                    return_code = process.returncode

                # Check for specific error patterns that might benefit from retrying
                error_category = self._categorize_git_error(output)

                # If successful, return immediately
                if return_code == 0:
                    return return_code, output

                # Some errors should be retried
                if error_category == 'network' and retries < max_retries:
                    self.logger.warning("%s", Network error detected in Git command. Retrying in {current_delay}s: {output})
                    time.sleep(current_delay)
                    retries += 1
                    current_delay *= 2  # Exponential backoff
                    continue

                # For other errors, just return
                return return_code, output

            except Exception as e:
                error_msg = f"Error executing Git command: {e}"
                self.logger.error(error_msg)

                if retries < max_retries:
                    self.logger.warning("%s", Retrying Git command in {current_delay}s after error)
                    time.sleep(current_delay)
                    retries += 1
                    current_delay *= 2  # Exponential backoff
                else:
                    return 1, error_msg

        # If we get here, we've exhausted our retries
        return 1, f"Failed after {max_retries} retries: {output}"

    def _categorize_git_error(self, error_output: str) -> str:
        """Categorize Git error messages for more specific handling.

        Args:
            error_output: The error output from a Git command

        Returns:
            Error category string or None if not categorized
        """
        if not error_output:
            return None

        error_lower = error_output.lower()

        for category, patterns in self.ERROR_CATEGORIES.items():
            for pattern in patterns:
                if pattern in error_lower:
                    return category

        return 'unknown'

    def _make_github_request(self, method: str, endpoint: str,
                            data: Optional[Dict[str, Any]] = None,
                            params: Optional[Dict[str, Any]] = None,
                            max_retries: int = 3) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Make a GitHub API request with proper error handling, rate limiting, and retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/repos/{owner}/{repo}/issues")
            data: Optional request body
            params: Optional query parameters
            max_retries: Maximum number of retries for recoverable errors

        Returns:
            Tuple of (success, response_data_or_error_message)
        """
        if not self.github_token:
            return False, "GitHub token not provided. Cannot make API requests."

        # Check rate limit before proceeding
        if not self._check_rate_limit():
            return False, f"GitHub API rate limit exceeded. Try again after {datetime.fromtimestamp(self.rate_limit_reset).strftime('%H:%M:%S')}"

        # Format the endpoint with repository information if needed
        if "{owner}" in endpoint or "{repo}" in endpoint:
            repo_info = self.get_repository_info()
            owner = repo_info.get("owner")
            repo = repo_info.get("repo")

            if not owner or not repo:
                return False, "Could not determine repository owner and name."

            endpoint = endpoint.replace("{owner}", owner).replace("{repo}", repo)

        # Prepare the request
        url = f"{self.github_api_url}{endpoint}"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Agent-S3/1.0"
        }

        retries = 0
        retry_delay = 2  # Start with 2 second delay

        while retries <= max_retries:
            try:
                if method.upper() == "GET":
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                elif method.upper() == "POST":
                    response = requests.post(url, headers=headers, json=data, params=params, timeout=30)
                elif method.upper() == "PATCH":
                    response = requests.patch(url, headers=headers, json=data, params=params, timeout=30)
                elif method.upper() == "PUT":
                    response = requests.put(url, headers=headers, json=data, params=params, timeout=30)
                elif method.upper() == "DELETE":
                    response = requests.delete(url, headers=headers, params=params, timeout=30)
                else:
                    return False, f"Unsupported HTTP method: {method}"

                # Update rate limit tracking
                self._update_rate_limit(response)

                # Handle successful responses
                if 200 <= response.status_code < 300:
                    if response.content and len(response.content.strip()) > 0:
                        return True, response.json()
                    else:
                        return True, {}

                # Handle specific status codes
                if response.status_code == 404:
                    # 404 Not Found - No need to retry
                    error_data = self._parse_github_error(response)
                    return False, f"Resource not found: {error_data}"
                elif response.status_code == 403:
                    # Check if it's a rate limit issue
                    if "rate limit" in response.text.lower():
                        wait_time = 60  # Default wait time
                        if 'X-RateLimit-Reset' in response.headers:
                            reset_time = int(response.headers['X-RateLimit-Reset'])
                            wait_time = max(1, reset_time - time.time())

                        if retries < max_retries:
                            self.logger.warning("%s", Rate limit hit. Waiting {wait_time:.1f}s and retrying...)
                            time.sleep(min(wait_time, 60))  # Wait at most 60 seconds
                            retries += 1
                            retry_delay *= 2
                            continue

                    # Other 403 errors - likely permission issues
                    error_data = self._parse_github_error(response)
                    return False, f"Permission denied: {error_data}"
                elif response.status_code == 422:
                    # Validation error - no need to retry
                    error_data = self._parse_github_error(response)
                    return False, f"Validation error: {error_data}"
                elif response.status_code >= 500:
                    # Server error, may be transient
                    if retries < max_retries:
                        self.logger.warning("%s", GitHub server error {response.status_code}. Retrying in {retry_delay}s...)
                        time.sleep(retry_delay)
                        retries += 1
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        error_data = self._parse_github_error(response)
                        return False, f"GitHub server error ({response.status_code}): {error_data}"
                else:
                    # Other errors
                    error_data = self._parse_github_error(response)

                    # Only retry certain types of errors
                    if retries < max_retries and response.status_code in (408, 429, 502, 503, 504):
                        self.logger.warning("%s", GitHub API error {response.status_code}. Retrying in {retry_delay}s...)
                        time.sleep(retry_delay)
                        retries += 1
                        retry_delay *= 2  # Exponential backoff
                        continue

                    return False, f"GitHub API error ({response.status_code}): {error_data}"

            except requests.exceptions.Timeout:
                if retries < max_retries:
                    self.logger.warning("%s", GitHub API request timed out. Retrying in {retry_delay}s...)
                    time.sleep(retry_delay)
                    retries += 1
                    retry_delay *= 2  # Exponential backoff
                    continue
                return False, "GitHub API request timed out after multiple retries."
            except requests.exceptions.ConnectionError:
                if retries < max_retries:
                    self.logger.warning("%s", GitHub API connection error. Retrying in {retry_delay}s...)
                    time.sleep(retry_delay)
                    retries += 1
                    retry_delay *= 2  # Exponential backoff
                    continue
                return False, "GitHub API connection error after multiple retries."
            except Exception as e:
                error_message = f"GitHub API request error: {e}"
                self.logger.error(error_message)

                if retries < max_retries:
                    self.logger.warning("%s", Unexpected error. Retrying in {retry_delay}s...)
                    time.sleep(retry_delay)
                    retries += 1
                    retry_delay *= 2  # Exponential backoff
                    continue

                return False, error_message

        # If we get here, we've exhausted our retries
        return False, f"GitHub API request failed after {max_retries} retries"

    def _parse_github_error(self, response):
        """Parse GitHub API error response to extract meaningful information.

        Args:
            response: The response object from the GitHub API

        Returns:
            Formatted error message string
        """
        try:
            error_data = response.json()
            if 'message' in error_data:
                error_message = error_data['message']

                # Include validation errors if available
                if 'errors' in error_data and isinstance(error_data['errors'], list):
                    errors = []
                    for err in error_data['errors']:
                        if 'message' in err:
                            errors.append(err['message'])
                        elif 'code' in err and 'field' in err:
                            errors.append(f"{err['code']} on field '{err['field']}'")

                    if errors:
                        error_message += f" - {', '.join(errors)}"

                return error_message
            return "Unknown error"
        except ValueError:
            return response.text[:100] if response.text else "Unable to parse error response"

    def _format_error(self, error_type: str, message: str, details: Any = None) -> Dict[str, Any]:
        """Return a standardized error object for tool wrappers."""
        return {
            "success": False,
            "error_type": error_type,
            "message": message,
            "details": details
        }

    def create_branch(self, branch_name: str, source_branch: Optional[str] = None) -> Dict[str,
         Any]:        """Create a new Git branch with improved error handling.

        Args:
            branch_name: Name for the new branch
            source_branch: Branch to create from (defaults to current branch)

        Returns:
            Tuple of (success, message)
        """
        # Check if branch already exists
        branch_exists, output = self.branch_exists(branch_name)
        if branch_exists:
            self.logger.warning("%s", Branch {branch_name} already exists. Attempting to check it out.)
            checkout_code, checkout_output = self.run_git_command(f"checkout {branch_name}")
            if checkout_code == 0:
                return {"success": True, "message": f"Branch {branch_name} already exists and was checked out"}
            else:
                self.logger.warning("Cannot checkout existing branch. Attempting to delete and recreate.")
                self.run_git_command(f"branch -D {branch_name}")  # Forcefully delete local branch

        # First, make sure we're on the right source branch
        if source_branch:
            code, output = self.run_git_command(f"checkout {source_branch}")
            if code != 0:
                # Try to fetch the source branch if it doesn't exist locally
                self.logger.warning("%s", Source branch {source_branch} not found locally. Attempting to fetch.)
                fetch_code, fetch_output = self.run_git_command(f"fetch origin {source_branch}:{source_branch}")

                if fetch_code != 0:
                    error_category = self._categorize_git_error(fetch_output)
                    if error_category == 'not_found':
                        return self._format_error('not_found', f"Source branch '{source_branch}' does not exist in the remote repository", fetch_output)
                    else:
                        return self._format_error('fetch_failed', f"Failed to fetch source branch: {fetch_output}", fetch_output)

                # Try checkout again after fetch
                code, output = self.run_git_command(f"checkout {source_branch}")
                if code != 0:
                    return self._format_error('checkout_failed', f"Failed to checkout source branch after fetching: {output}", output)

        # Make sure we have the latest changes
        code, output = self.run_git_command("pull")
        if code != 0:
            error_category = self._categorize_git_error(output)
            if error_category == 'network':
                self.logger.warning("%s", Network issue during pull. Continuing without latest changes: {output})
            elif 'no tracking information' in output.lower() or 'no upstream branch' in output.lower():
                self.logger.warning("Current branch has no tracking information. Continuing without pulling.")
            else:
                self.logger.warning("%s", Git pull failed: {output})

        # Create the new branch
        code, output = self.run_git_command(f"checkout -b {branch_name}")
        if code != 0:
            return self._format_error('create_branch_failed', f"Failed to create branch: {output}", output)

        return {"success": True, "message": f"Successfully created and switched to branch {branch_name}"}

    def branch_exists(self, branch_name: str) -> Tuple[bool, str]:
        """Check if a branch exists locally or remotely.

        Args:
            branch_name: Name of the branch to check

        Returns:
            Tuple of (exists, message)
        """
        # Check local branches
        code, output = self.run_git_command(f"branch --list {branch_name}")
        if code == 0 and branch_name in output:
            return True, "Branch exists locally"

        # Check remote branches
        code, output = self.run_git_command("fetch --all")
        if code != 0:
            self.logger.warning("%s", Failed to fetch branches: {output})

        code, output = self.run_git_command(f"branch -r --list origin/{branch_name}")
        if code == 0 and f"origin/{branch_name}" in output:
            return True, "Branch exists remotely"

        return False, "Branch does not exist"

    def commit_changes(self, commit_message: str, add_all: bool = False,
         files: Optional[List[str]] = None) -> Dict[str, Any]:        """Commit changes to the repository with improved error handling.

        Args:
            commit_message: The commit message
            add_all: Whether to add all files
            files: Specific files to add

        Returns:
            Tuple of (success, message)
        """
        # Add files
        if add_all:
            code, output = self.run_git_command("add -A")
            if code != 0:
                error_category = self._categorize_git_error(output)
                if error_category == 'permission':
                    return self._format_error('permission', "Permission denied: Unable to add files. Check file permissions.", output)
                return self._format_error('add_failed', f"Failed to add files: {output}", output)
        elif files:
            for file in files:
                # Check if file exists
                if not os.path.exists(file):
                    return self._format_error('file_not_found', f"Failed to add file '{file}': File does not exist", file)

            file_list = " ".join([f'\"{f}\"' for f in files])  # Quote filenames to handle spaces
            code, output = self.run_git_command(f"add {file_list}")
            if code != 0:
                return self._format_error('add_failed', f"Failed to add files: {output}", output)

        # Check if there are changes to commit
        code, output = self.run_git_command("status --porcelain")
        if code != 0:
            return self._format_error('status_failed', f"Failed to check status: {output}", output)

        if not output.strip():
            return {"success": True, "message": "No changes to commit"}

        # Escape quotes in the commit message
        safe_message = commit_message.replace('"', '\\"')

        # Commit
        code, output = self.run_git_command(f'commit -m "{safe_message}"')
        if code != 0:
            if "nothing to commit" in output.lower():
                return {"success": True, "message": "No changes to commit"}
            if "please tell me who you are" in output.lower():
                return self._format_error('identity', "Git identity not configured. Please set user.name and user.email.", output)

            return self._format_error('commit_failed', f"Failed to commit: {output}", output)

        return {"success": True, "message": output}  # Return the actual commit message which may contain the commit hash

    def push_changes(self, branch: Optional[str] = None, force: bool = False,
         set_upstream: bool = True) -> Dict[str, Any]:        """Push changes to the remote repository with improved error handling.

        Args:
            branch: Branch name to push (defaults to current branch)
            force: Whether to force push
            set_upstream: Whether to set the upstream branch

        Returns:
            Tuple of (success, message)
        """
        # Get current branch if not specified
        if not branch:
            code, output = self.run_git_command("branch --show-current")
            if code != 0:
                return self._format_error('branch_failed', f"Failed to determine current branch: {output}", output)
            branch = output.strip()

        push_command = "push"

        if set_upstream:
            push_command = f"{push_command} --set-upstream origin {branch}"
        elif branch:
            push_command = f"{push_command} origin {branch}"

        if force:
            push_command = f"{push_command} --force"

        code, output = self.run_git_command(push_command, max_retries=2)
        if code != 0:
            error_category = self._categorize_git_error(output)

            if error_category == 'permission':
                return self._format_error('permission', "Permission denied: Unable to push to the repository. Check your access rights.", output)
            elif error_category == 'conflict':
                if not force:
                    # If there's a conflict and we didn't use force, suggest it
                    self.logger.warning("Push rejected due to conflict. Suggesting force push.")
                    return self._format_error('conflict', "Push rejected due to conflict. Use force push option if appropriate.", output)
                else:
                    return self._format_error('force_push_failed', f"Failed to force push changes: {output}", output)
            elif error_category == 'network':
                return self._format_error('network', f"Network error while pushing: {output}", output)
            elif "updates were rejected" in output.lower():
                return self._format_error('rejected', "Push rejected. Your local branch is behind the remote branch.", output)
            else:
                return self._format_error('push_failed', f"Failed to push changes: {output}", output)

        return {"success": True, "message": "Changes pushed successfully"}

    def get_repository_info(self) -> Dict[str, Any]:
        """Get information about the current Git repository.

        Determines the owner, repository name, and current branch using Git commands.
        Uses caching to avoid repeated lookups.

        Returns:
            Dictionary with keys: 'owner', 'repo', 'current_branch', and 'remote_url'
        """
        # Return cached info if available and not too old (10 min cache)
        cache_age = time.time() - self._repo_info_cache_time
        if self._repo_info_cache and cache_age < 600:
            return self._repo_info_cache

        # Use overrides if provided
        if self.org_override and self.repo_override:
            self._repo_info_cache = {
                'owner': self.org_override,
                'repo': self.repo_override,
                'current_branch': self._get_current_branch(),
                'remote_url': None  # Not needed when overrides are used
            }
            self._repo_info_cache_time = time.time()
            return self._repo_info_cache

        result = {
            'owner': None,
            'repo': None,
            'current_branch': None,
            'remote_url': None
        }

        # Get current branch
        result['current_branch'] = self._get_current_branch()

        # Get remote URL
        code, output = self.run_git_command("remote get-url origin")
        if code != 0:
            self.logger.warning("%s", Failed to get remote URL: {output})
            return result

        remote_url = output.strip()
        result['remote_url'] = remote_url

        # Parse owner and repo from remote URL
        # Handle SSH URL: git@github.com:owner/repo.git
        ssh_match = re.match(r'git@github\.com:([^/]+)/(.*?)(?:\.git)?$', remote_url)
        if ssh_match:
            result['owner'] = ssh_match.group(1)
            result['repo'] = ssh_match.group(2)
            self._repo_info_cache = result
            self._repo_info_cache_time = time.time()
            return result

        # Handle HTTPS URL: https://github.com/owner/repo.git
        https_match = re.match(r'https://github\.com/([^/]+)/(.*?)(?:\.git)?$', remote_url)
        if https_match:
            result['owner'] = https_match.group(1)
            result['repo'] = https_match.group(2)
            self._repo_info_cache = result
            self._repo_info_cache_time = time.time()
            return result

        self.logger.warning("%s", Failed to parse owner and repo from remote URL: {remote_url})
        return result

    def _get_current_branch(self) -> Optional[str]:
        """Get the current Git branch name.

        Returns:
            String with the branch name or None if it couldn't be determined
        """
        code, output = self.run_git_command("branch --show-current")
        if code != 0:
            self.logger.warning("%s", Failed to get current branch: {output})
            return None

        branch = output.strip()
        if not branch:
            self.logger.warning("Git did not return a branch name")
            return None

        return branch

    def create_github_issue(self, title: str, body: str, labels: Optional[List[str]] = None)
         -> Optional[str]:        """Create a GitHub issue in the current repository.

        Args:
            title: Issue title
            body: Issue body
            labels: Optional list of labels to apply to the issue

        Returns:
            Issue URL if successful, None otherwise
        """
        if not self.github_token:
            self.logger.error("GitHub token not provided. Cannot create issue.")
            return None

        # Build request data
        issue_data = {
            "title": title,
            "body": body
        }

        if labels:
            issue_data["labels"] = labels

        # Make the API request
        success, response = self._make_github_request(
            "POST",
            "/repos/{owner}/{repo}/issues",
            data=issue_data
        )

        if success and isinstance(response, dict):
            issue_url = response.get("html_url")
            self.logger.info("%s", Successfully created issue: {issue_url})
            return issue_url
        else:
            error_msg = response if isinstance(response, str) else "Unknown error"
            self.logger.error("%s", Failed to create issue: {error_msg})
            return None

    def create_pull_request(self, title: str, body: str, head_branch: Optional[str] = None,
                         base_branch: str = "main", draft: bool = False) -> Optional[str]:
        """Create a GitHub pull request from the current branch.

        Args:
            title: PR title
            body: PR description
            head_branch: Source branch (defaults to current branch)
            base_branch: Target branch (defaults to main)
            draft: Whether to create as draft PR

        Returns:
            Pull request URL if successful, None otherwise
        """
        if not self.github_token:
            self.logger.error("GitHub token not provided. Cannot create pull request.")
            return None

        # Get current branch if not specified
        if not head_branch:
            head_branch = self._get_current_branch()
            if not head_branch:
                self.logger.error("Failed to determine current branch")
                return None

        # Build request data
        pr_data = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "draft": draft
        }

        # Make the API request
        success, response = self._make_github_request(
            "POST",
            "/repos/{owner}/{repo}/pulls",
            data=pr_data
        )

        if success and isinstance(response, dict):
            pr_url = response.get("html_url")
            self.logger.info("%s", Successfully created pull request: {pr_url})
            return pr_url
        else:
            error_msg = response if isinstance(response, str) else "Unknown error"
            self.logger.error("%s", Failed to create pull request: {error_msg})
            return None

    def _check_rate_limit(self) -> bool:
        """Check if we're within GitHub API rate limits.

        Returns:
            True if we can make requests, False if rate limit exceeded
        """
        # If we have cached rate limit info
        if self.rate_limit_remaining <= 0 and time.time() < self.rate_limit_reset:
            wait_time = self.rate_limit_reset - time.time()
            if wait_time > 0:
                self.logger.warning("%s", GitHub API rate limit exceeded. Reset in {wait_time:.1f} seconds.)
                return False

        # Default to allowing the request if we don't have rate limit info yet
        return True

    def _update_rate_limit(self, response):
        """Update rate limit tracking from response headers.

        Args:
            response: The response object from the GitHub API
        """
        if 'X-RateLimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])

        if 'X-RateLimit-Reset' in response.headers:
            self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])

        if self.rate_limit_remaining <= 10:
            reset_time = datetime.fromtimestamp(self.rate_limit_reset)
            self.logger.warning(f"GitHub API rate limit low: {self.rate_limit_remaining} requests remaining. " +
                                                                               f"Resets at {reset_time.strftime('%H:%M:%S')}")
