"""Wraps Git commands and implements GitHub issue and PR creation."""

import os
import subprocess
import json
import logging
import re
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List, Union

import requests
from requests.exceptions import RequestException


class GitTool:
    """Tool for Git operations and GitHub API interactions."""
    
    def __init__(self, token: Optional[str] = None, 
                 org: Optional[str] = None, 
                 repo: Optional[str] = None,
                 terminal_executor = None):
        """Initialize the Git tool.
        
        Args:
            token: GitHub OAuth token or dev token for API access
            org: Target GitHub organization (overrides auto-detection)
            repo: Target GitHub repository name (overrides auto-detection)
            terminal_executor: Optional terminal executor for secure command execution
        """
        self.github_token = token
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
    
    def run_git_command(self, command: str) -> Tuple[int, str]:
        """Run a Git command securely.
        
        Args:
            command: The Git command to run (without 'git' prefix)
            
        Returns:
            A tuple containing (return code, output)
        """
        try:
            full_command = f"git {command}"
            
            # If terminal executor is provided, use it for secure execution
            if self.terminal_executor:
                return self.terminal_executor.run_command(full_command)
            
            # Otherwise fall back to subprocess
            process = subprocess.Popen(
                full_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            output, _ = process.communicate()
            return process.returncode, output
        except Exception as e:
            self.logger.error(f"Error executing Git command: {e}")
            return 1, f"Error executing Git command: {e}"
    
    def get_repository_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get information about the current Git repository.
        
        Args:
            force_refresh: Force refresh of cached repository info
        
        Returns:
            Dictionary containing repository information
        """
        # Check cache if not forcing refresh
        current_time = time.time()
        if not force_refresh and self._repo_info_cache and current_time - self._repo_info_cache_time < 300:  # 5 minute cache
            return self._repo_info_cache
            
        info = {
            "remote_url": None,
            "owner": self.org_override,
            "repo": self.repo_override,
            "current_branch": None
        }
        
        # If owner and repo are not provided, try to detect from git config
        if not self.org_override or not self.repo_override:
            # Get remote URL
            code, output = self.run_git_command("config --get remote.origin.url")
            if code == 0:
                remote_url = output.strip()
                info["remote_url"] = remote_url
                
                # Extract owner and repo from URL
                # Format could be https://github.com/owner/repo.git or git@github.com:owner/repo.git
                if "github.com" in remote_url:
                    if remote_url.startswith("https"):
                        parts = remote_url.split("/")
                        if len(parts) >= 5:
                            info["owner"] = self.org_override or parts[-2]
                            info["repo"] = self.repo_override or parts[-1].replace(".git", "")
                    else:  # SSH format
                        parts = remote_url.split(":")
                        if len(parts) == 2:
                            repo_parts = parts[1].split("/")
                            if len(repo_parts) == 2:
                                info["owner"] = self.org_override or repo_parts[0]
                                info["repo"] = self.repo_override or repo_parts[1].replace(".git", "")
        
        # Get current branch
        code, output = self.run_git_command("branch --show-current")
        if code == 0:
            info["current_branch"] = output.strip()
        
        # Get current commit
        code, output = self.run_git_command("rev-parse HEAD")
        if code == 0:
            info["current_commit"] = output.strip()
            
        # Get current user
        code, output = self.run_git_command("config user.name")
        if code == 0:
            info["user_name"] = output.strip()
            
        code, output = self.run_git_command("config user.email")
        if code == 0:
            info["user_email"] = output.strip()
            
        # Cache the result
        self._repo_info_cache = info
        self._repo_info_cache_time = current_time
        
        return info
    
    def _check_rate_limit(self) -> bool:
        """Check if we're about to hit GitHub's rate limit.
        
        Returns:
            True if we can proceed, False if we should wait
        """
        if self.rate_limit_remaining > 10:
            return True
            
        current_time = time.time()
        if current_time > self.rate_limit_reset:
            # Reset time has passed, we should be good to go
            return True
            
        # We need to wait until reset time
        wait_time = self.rate_limit_reset - current_time
        self.logger.warning(f"GitHub API rate limit nearly exhausted. Waiting for {wait_time:.1f} seconds before proceeding.")
        return False
        
    def _update_rate_limit(self, response: requests.Response) -> None:
        """Update rate limit tracking from GitHub API response headers.
        
        Args:
            response: The response from a GitHub API request
        """
        if 'X-RateLimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
            
        if 'X-RateLimit-Reset' in response.headers:
            self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])
        
        if self.rate_limit_remaining < 100:
            reset_time = datetime.fromtimestamp(self.rate_limit_reset).strftime('%H:%M:%S')
            self.logger.warning(f"GitHub API rate limit running low. {self.rate_limit_remaining} requests remaining, resets at {reset_time}")
    
    def _make_github_request(self, method: str, endpoint: str, 
                            data: Optional[Dict[str, Any]] = None, 
                            params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Make a GitHub API request with proper error handling and rate limiting.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/repos/{owner}/{repo}/issues")
            data: Optional request body
            params: Optional query parameters
            
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
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, params=params)
            elif method.upper() == "PATCH":
                response = requests.patch(url, headers=headers, json=data, params=params)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data, params=params)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, params=params)
            else:
                return False, f"Unsupported HTTP method: {method}"
                
            # Update rate limit tracking
            self._update_rate_limit(response)
            
            # Handle response
            if 200 <= response.status_code < 300:
                if response.content and len(response.content.strip()) > 0:
                    return True, response.json()
                else:
                    return True, {}
            else:
                error_message = f"GitHub API request failed: {response.status_code} - {response.reason}"
                try:
                    error_data = response.json()
                    error_message += f"\n{error_data.get('message', '')}"
                except ValueError:
                    pass
                    
                self.logger.error(error_message)
                return False, error_message
                
        except RequestException as e:
            error_message = f"GitHub API request error: {e}"
            self.logger.error(error_message)
            return False, error_message
    
    def create_github_issue(self, title: str, body: str, 
                           labels: Optional[List[str]] = None, 
                           assignees: Optional[List[str]] = None) -> Tuple[bool, Union[str, Dict[str, Any]]]:
        """Create a GitHub issue.
        
        Args:
            title: The issue title
            body: The issue body
            labels: Optional list of labels to apply
            assignees: Optional list of users to assign
            
        Returns:
            Tuple of (success, issue_url_or_error_message)
        """
        data = {
            "title": title,
            "body": body
        }
        
        if labels:
            data["labels"] = labels
            
        if assignees:
            data["assignees"] = assignees
        
        success, response = self._make_github_request(
            "POST", 
            "/repos/{owner}/{repo}/issues", 
            data=data
        )
        
        if success:
            issue_url = response.get("html_url")
            issue_number = response.get("number")
            return True, {
                "url": issue_url,
                "number": issue_number,
                "id": response.get("id"),
                "created_at": response.get("created_at")
            }
        else:
            return False, response
    
    def get_issues(self, state: str = "open", 
                  labels: Optional[str] = None, 
                  since: Optional[str] = None,
                  per_page: int = 30) -> Tuple[bool, List[Dict[str, Any]]]:
        """Get GitHub issues for the repository.
        
        Args:
            state: Issue state ("open", "closed", or "all")
            labels: Comma-separated list of label names
            since: Only issues updated at or after this time (ISO 8601 format)
            per_page: Number of results per page
            
        Returns:
            Tuple of (success, list_of_issues_or_error_message)
        """
        params = {
            "state": state,
            "per_page": min(per_page, 100)  # GitHub API limit
        }
        
        if labels:
            params["labels"] = labels
            
        if since:
            params["since"] = since
        
        success, response = self._make_github_request(
            "GET", 
            "/repos/{owner}/{repo}/issues", 
            params=params
        )
        
        if success:
            return True, response
        else:
            return False, []

    def create_pull_request(self, 
                           title: str, 
                           body: str, 
                           head: Optional[str] = None, 
                           base: Optional[str] = None,
                           draft: bool = False,
                           maintainer_can_modify: bool = True) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Create a GitHub pull request.

        Args:
            title: The PR title
            body: The PR body
            head: The name of the branch where changes are implemented (defaults to current branch)
            base: The name of the branch for changes to be pulled into (defaults to main/master)
            draft: Whether to create as a draft PR
            maintainer_can_modify: Whether repo maintainers can modify the PR

        Returns:
            Tuple of (success, pull_request_data_or_error_message)
        """
        repo_info = self.get_repository_info()
        current_branch = repo_info.get("current_branch")
        head = head or current_branch
        base = base or os.getenv("GITHUB_BASE_BRANCH") or "main"
        
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": draft,
            "maintainer_can_modify": maintainer_can_modify
        }
        
        success, response = self._make_github_request(
            "POST", 
            "/repos/{owner}/{repo}/pulls",
            data=data
        )
        
        if success:
            pr_url = response.get("html_url")
            pr_number = response.get("number")
            self.logger.info(f"Created pull request #{pr_number}: {pr_url}")
            return True, {
                "url": pr_url,
                "number": pr_number,
                "id": response.get("id"),
                "created_at": response.get("created_at"),
                "state": response.get("state")
            }
        else:
            self.logger.error(f"Failed to create pull request: {response}")
            return False, response
            
    def list_pull_requests(self, state: str = "open", 
                          head: Optional[str] = None,
                          base: Optional[str] = None,
                          sort: str = "created",
                          direction: str = "desc") -> Tuple[bool, List[Dict[str, Any]]]:
        """List pull requests for the repository.
        
        Args:
            state: PR state ("open", "closed", "all")
            head: Filter by head branch (e.g., "username:branch-name")
            base: Filter by base branch name
            sort: What to sort by ("created", "updated", "popularity", "long-running")
            direction: Sort direction ("asc" or "desc")
            
        Returns:
            Tuple of (success, list_of_pulls_or_error_message)
        """
        params = {
            "state": state,
            "sort": sort,
            "direction": direction
        }
        
        if head:
            params["head"] = head
            
        if base:
            params["base"] = base
        
        success, response = self._make_github_request(
            "GET", 
            "/repos/{owner}/{repo}/pulls", 
            params=params
        )
        
        if success:
            return True, response
        else:
            return False, []
            
    def get_commits(self, branch: Optional[str] = None, 
                   path: Optional[str] = None,
                   author: Optional[str] = None,
                   since: Optional[str] = None,
                   until: Optional[str] = None) -> Tuple[bool, List[Dict[str, Any]]]:
        """Get commits for the repository.
        
        Args:
            branch: Branch name to filter commits by
            path: Only commits containing changes to this file path
            author: GitHub username or email address to filter commits
            since: Only commits after this date (ISO 8601 format)
            until: Only commits before this date (ISO 8601 format)
            
        Returns:
            Tuple of (success, list_of_commits_or_error_message)
        """
        params = {}
        
        if branch:
            params["sha"] = branch
            
        if path:
            params["path"] = path
            
        if author:
            params["author"] = author
            
        if since:
            params["since"] = since
            
        if until:
            params["until"] = until
        
        success, response = self._make_github_request(
            "GET", 
            "/repos/{owner}/{repo}/commits", 
            params=params
        )
        
        if success:
            return True, response
        else:
            return False, []
            
    def create_branch(self, branch_name: str, 
                     source_branch: Optional[str] = None) -> Tuple[bool, str]:
        """Create a new Git branch.
        
        Args:
            branch_name: Name for the new branch
            source_branch: Branch to create from (defaults to current branch)
            
        Returns:
            Tuple of (success, message)
        """
        # First, make sure we're on the right source branch
        if source_branch:
            code, output = self.run_git_command(f"checkout {source_branch}")
            if code != 0:
                return False, f"Failed to checkout source branch: {output}"
                
        # Make sure we have the latest changes
        code, output = self.run_git_command("pull")
        if code != 0:
            self.logger.warning(f"Git pull failed: {output}")
        
        # Create the new branch
        code, output = self.run_git_command(f"checkout -b {branch_name}")
        if code != 0:
            return False, f"Failed to create branch: {output}"
            
        return True, f"Successfully created and switched to branch {branch_name}"
            
    def commit_changes(self, commit_message: str, 
                      add_all: bool = False, 
                      files: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Commit changes to the repository.
        
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
                return False, f"Failed to add files: {output}"
        elif files:
            file_list = " ".join(files)
            code, output = self.run_git_command(f"add {file_list}")
            if code != 0:
                return False, f"Failed to add files: {output}"
        
        # Commit
        code, output = self.run_git_command(f'commit -m "{commit_message}"')
        if code != 0:
            return False, f"Failed to commit: {output}"
            
        return True, "Changes committed successfully"
        
    def push_changes(self, branch: Optional[str] = None, 
                    force: bool = False) -> Tuple[bool, str]:
        """Push changes to the remote repository.
        
        Args:
            branch: Branch name to push (defaults to current branch)
            force: Whether to force push
            
        Returns:
            Tuple of (success, message)
        """
        push_command = "push"
        
        if branch:
            push_command = f"{push_command} origin {branch}"
            
        if force:
            push_command = f"{push_command} --force"
            
        code, output = self.run_git_command(push_command)
        if code != 0:
            return False, f"Failed to push changes: {output}"
            
        return True, "Changes pushed successfully"
