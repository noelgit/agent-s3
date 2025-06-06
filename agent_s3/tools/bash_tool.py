"""Executes shell commands in a sandboxed environment.

This module provides containerized command execution as specified in instructions.md.
"""

import os
import re
import subprocess
import tempfile
import time
import shutil
import uuid
import platform
import shlex
import logging
from typing import Tuple, Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class BashTool:
    """Tool for executing shell commands securely in containers."""

    def __init__(self,
                 sandbox: bool = True,
                 env_vars: Optional[Dict[str, str]] = None,
                 container_image: str = "python:3.10-slim",
                 resource_limits: Optional[Dict[str, str]] = None,
                 host_os_type: Optional[str] = None):
        """Initialize the bash tool.

        Args:
            sandbox: Whether to run commands in a sandboxed environment
            env_vars: Additional environment variables to set
            container_image: Docker image to use for sandboxed execution
            resource_limits: Resource limits for the container (e.g. memory, cpu)
            host_os_type: The host operating system type ('windows', 'darwin', 'linux', etc.)
        """
        self.sandbox = sandbox
        self.env_vars = env_vars or {}
        self.container_image = container_image
        self.resource_limits = resource_limits or {
            "memory": "512m",
            "cpu-shares": "1024"
        }

        # Store the host OS type
        self.host_os_type = host_os_type or platform.system().lower()

        # Define blocked commands for security (used as fallback if containerization fails)
        self.blocked_commands = [
            "rm -rf",  # Block dangerous file deletion
            "sudo",    # Block elevated privileges
            "chmod",   # Block permission changes
            "chown",   # Block ownership changes
            ":(){",    # Block fork bombs
            "dd if=",  # Block disk operations
            "> /dev",  # Block device writes
            "mkfs",    # Block filesystem formatting
            "mount",   # Block mounting filesystems
            "umount",  # Block unmounting filesystems
            "shutdown",# Block system shutdown
            "reboot"   # Block system reboot
        ]

        # Define allowed network domains when running in container
        self.allowed_domains = [
            "github.com",
            "pypi.org",
            "files.pythonhosted.org",
            "registry.npmjs.org"
        ]

        # Keep track of running containers
        self.containers: Dict[str, Dict[str, Any]] = {}

        # Create a workspace directory for file transfers
        self.workspace_dir = os.path.join(tempfile.gettempdir(), "agent_s3_sandbox")
        os.makedirs(self.workspace_dir, exist_ok=True)

        # Check if Docker is available
        self.docker_available = self._check_docker_available()
        if self.sandbox and not self.docker_available:
            logger.warning(
                "Docker not available. Falling back to restricted subprocess mode."
            )

    def run_command(self, command: str, timeout: int = 60) -> Tuple[int, str]:
        """Run a shell command and return the exit code and output.

        Args:
            command: The command to run
            timeout: Timeout in seconds

        Returns:
            Tuple of ``(exit_code, output)``
        """
        # Check if command is blocked (applies only when Docker is unavailable)
        if not self.docker_available and self._is_blocked(command):
            return 1, f"Error: Command '{command}' is blocked for security reasons"

        try:
            # Run in a container if sandbox mode is enabled and Docker is available
            if self.sandbox and self.docker_available:
                code, output = self._run_in_container(command, timeout)
            else:
                # Fallback to subprocess with restrictions
                code, output = self._run_with_subprocess(command, timeout)

            return code, output
        except Exception as e:
            return 1, f"Error executing command: {e}"

    def run_command_async(self, command: str, timeout: int = 3600) -> str:
        """Run a shell command asynchronously.

        Args:
            command: The command to run
            timeout: Timeout in seconds

        Returns:
            Container ID or process ID
        """
        container_id = str(uuid.uuid4())

        if self.sandbox and self.docker_available:
            # Run in detached mode in a container
            try:
                container_name = f"agent_s3_sandbox_{container_id}"

                # Create a script file with the command
                script_path = os.path.join(self.workspace_dir, f"{container_id}.sh")
                with open(script_path, "w") as f:
                    f.write("#!/bin/bash\n")
                    f.write(f"{command}\n")
                os.chmod(script_path, 0o755)

                # Create a log file
                log_path = os.path.join(self.workspace_dir, f"{container_id}.log")

                # Build the docker command
                docker_cmd = [
                    "docker", "run", "-d",
                    "--name", container_name,
                    "--memory", self.resource_limits["memory"],
                    "--cpu-shares", self.resource_limits["cpu-shares"]
                ]

                # Add environment variables
                for key, value in self.env_vars.items():
                    docker_cmd.extend(["-e", f"{key}={value}"])

                # Add network restrictions
                # PATCH: Use restricted network instead of host
                if self.allowed_domains:
                    docker_cmd.extend(["--network", "bridge", "--cap-add", "NET_ADMIN"])
                    allowed_ips: List[str] = []
                    import socket
                    for domain in self.allowed_domains:
                        try:
                            infos = socket.getaddrinfo(domain, None)
                            for info in infos:
                                ip = info[4][0]
                                if ip not in allowed_ips:
                                    allowed_ips.append(ip)
                        except socket.gaierror:
                            continue
                    firewall_cmds = ["iptables -P OUTPUT DROP", "iptables -A OUTPUT -d 127.0.0.1 -j ACCEPT"]
                    for ip in allowed_ips:
                        firewall_cmds.append(f"iptables -A OUTPUT -d {ip} -j ACCEPT")
                    firewall_cmds.append("/script.sh > /tmp/output.log 2>&1")
                    command_wrapper = " && ".join(firewall_cmds)
                else:
                    docker_cmd.extend(["--network", "none"])
                    command_wrapper = "/script.sh > /tmp/output.log 2>&1"

                # Add volume mount for the script
                docker_cmd.extend(["-v", f"{script_path}:/script.sh"])

                # Specify the image and command
                docker_cmd.extend([
                    self.container_image,
                    "/bin/bash", "-c", command_wrapper
                ])

                # Start the container
                process = subprocess.run(
                    docker_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )

                # Store container info
                self.containers[container_id] = {
                    "container_name": container_name,
                    "command": command,
                    "start_time": time.time(),
                    "timeout": timeout,
                    "log_path": log_path
                }

                return container_id

            except Exception as e:
                return f"Error starting async command: {e}"
        else:
            # Fallback to subprocess
            try:
                # Create a script file with the command
                script_path = os.path.join(self.workspace_dir, f"{container_id}.sh")
                with open(script_path, "w") as f:
                    f.write("#!/bin/bash\n")
                    f.write(f"{command} > {self.workspace_dir}/{container_id}.log 2>&1 &\n")
                os.chmod(script_path, 0o755)

                # Execute the script
                env = os.environ.copy()
                for key, value in self.env_vars.items():
                    env[key] = value

                process = subprocess.Popen([
                    script_path
                ],
                    env=env
                )

                # Store process info
                self.containers[container_id] = {
                    "process_id": process.pid,
                    "command": command,
                    "start_time": time.time(),
                    "timeout": timeout,
                    "log_path": os.path.join(self.workspace_dir, f"{container_id}.log")
                }

                return container_id

            except Exception as e:
                return f"Error starting async command: {e}"

    def get_command_output(self, container_id: str) -> Tuple[int, str]:
        """Get the output of an asynchronous command.

        Args:
            container_id: Container or process ID returned by run_command_async

        Returns:
            A tuple containing (return code, output)
        """
        if container_id not in self.containers:
            return 1, f"Error: No such container or process: {container_id}"

        container_info = self.containers[container_id]

        if self.sandbox and self.docker_available:
            # Check if container is still running
            try:
                container_name = container_info["container_name"]
                process = subprocess.run(
                    ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if process.stdout.strip():
                    # Container is still running
                    elapsed_time = time.time() - container_info["start_time"]
                    return 0, f"Command still running (elapsed: {int(elapsed_time)}s)"

                # Get the exit code
                exit_code_process = subprocess.run(
                    ["docker", "inspect", container_name, "--format", "{{.State.ExitCode}}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                exit_code = int(exit_code_process.stdout.strip()) if exit_code_process.stdout.strip().isdigit() else 1

                # Get the logs
                logs_process = subprocess.run(
                    ["docker", "logs", container_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                output = logs_process.stdout

                # Clean up the container
                subprocess.run(["docker", "rm", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Remove container info
                self.containers.pop(container_id, None)

                return exit_code, output

            except Exception as e:
                return 1, f"Error getting container output: {e}"
        else:
            # Check subprocess output
            log_path = container_info["log_path"]
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    output = f.read()

                # Check if process is still running
                try:
                    process_id = container_info.get("process_id", -1)
                    if process_id > 0:
                        os.kill(process_id, 0)  # Doesn't kill the process, just checks if it exists
                        elapsed_time = time.time() - container_info["start_time"]
                        return 0, f"Command still running (elapsed: {int(elapsed_time)}s)\n\nOutput so far:\n{output}"
                except OSError:
                    # Process has finished
                    pass

                # Remove process info
                self.containers.pop(container_id, None)

                # Assume exit code 0 unless output contains error patterns
                exit_code = 0
                if "error:" in output.lower() or "exception:" in output.lower():
                    exit_code = 1

                return exit_code, output
            else:
                return 1, f"Error: No output file found for process {container_id}"

    def stop_command(self, container_id: str) -> Tuple[bool, str]:
        """Stop an asynchronous command.

        Args:
            container_id: Container or process ID returned by run_command_async

        Returns:
            A tuple containing (success, message)
        """
        if container_id not in self.containers:
            return False, f"Error: No such container or process: {container_id}"

        container_info = self.containers[container_id]

        if self.sandbox and self.docker_available:
            try:
                container_name = container_info["container_name"]
                subprocess.run(
                    ["docker", "stop", container_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                subprocess.run(
                    ["docker", "rm", container_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                # Remove container info
                self.containers.pop(container_id, None)

                return True, f"Container {container_id} stopped and removed"
            except Exception as e:
                return False, f"Error stopping container: {e}"
        else:
            try:
                process_id = container_info.get("process_id", -1)
                if process_id > 0:
                    os.kill(process_id, 15)  # SIGTERM

                # Remove process info
                self.containers.pop(container_id, None)

                return True, f"Process {container_id} stopped"
            except Exception as e:
                return False, f"Error stopping process: {e}"

    def cleanup(self) -> None:
        """Clean up all containers and temporary files."""
        # Stop all running containers
        for container_id in list(self.containers.keys()):
            self.stop_command(container_id)

        # Clean up any leftover containers
        if self.docker_available:
            try:
                subprocess.run(
                    ["docker", "ps", "-a", "--filter", "name=agent_s3_sandbox_", "--format", "{{.Names}}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                for container_name in subprocess.run(["docker", "ps", "-a", "--filter", "name=agent_s3_sandbox_", "--format", "{{.Names}}"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout.splitlines():
                    subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        # Clean up workspace directory
        try:
            shutil.rmtree(self.workspace_dir)
        except Exception:
            pass

    def _run_in_container(self, command: str, timeout: int) -> Tuple[int, str]:
        """Run a command in a Docker container.

        Args:
            command: The command to run
            timeout: Timeout in seconds

        Returns:
            A tuple containing (return code, output)
        """
        container_id = str(uuid.uuid4())
        container_name = f"agent_s3_sandbox_{container_id}"

        script_path = None
        try:
            # Create a script file with the command
            script_path = os.path.join(self.workspace_dir, f"{container_id}.sh")
            with open(script_path, "w") as f:
                f.write("#!/bin/bash\n")
                f.write(f"{command}\n")
            os.chmod(script_path, 0o755)

            # Build the docker command
            docker_cmd = [
                "docker", "run", "--rm",
                "--name", container_name,
                "--memory", self.resource_limits["memory"],
                "--cpu-shares", self.resource_limits["cpu-shares"],
                "-v", f"{script_path}:/script.sh"
            ]

            # Add environment variables
            for key, value in self.env_vars.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

            # Add network restrictions
            # PATCH: Use restricted network instead of host
            if self.allowed_domains:
                docker_cmd.extend(["--network", "bridge", "--cap-add", "NET_ADMIN"])
                allowed_ips: List[str] = []
                import socket
                for domain in self.allowed_domains:
                    try:
                        infos = socket.getaddrinfo(domain, None)
                        for info in infos:
                            ip = info[4][0]
                            if ip not in allowed_ips:
                                allowed_ips.append(ip)
                    except socket.gaierror:
                        continue
                firewall_cmds = ["iptables -P OUTPUT DROP", "iptables -A OUTPUT -d 127.0.0.1 -j ACCEPT"]
                for ip in allowed_ips:
                    firewall_cmds.append(f"iptables -A OUTPUT -d {ip} -j ACCEPT")
                firewall_cmds.append("/script.sh")
                command_wrapper = " && ".join(firewall_cmds)
            else:
                docker_cmd.extend(["--network", "none"])
                command_wrapper = "/script.sh"

            # Specify the image and command
            docker_cmd.extend([
                self.container_image,
                "/bin/bash", "-c", command_wrapper
            ])

            # Run the container with timeout
            process = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout
            )

            return process.returncode, process.stdout

        except subprocess.TimeoutExpired:
            # Stop and remove the container
            subprocess.run(["docker", "stop", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["docker", "rm", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 1, f"Error: Command timed out after {timeout} seconds"

        except Exception as e:
            return 1, f"Error running command in container: {e}"
        
        finally:
            # Ensure script file cleanup
            if script_path and os.path.exists(script_path):
                try:
                    os.unlink(script_path)
                except OSError:
                    pass  # Ignore cleanup errors

    def _run_with_subprocess(self, command: str, timeout: int) -> Tuple[int, str]:
        """Run a command with subprocess (fallback method).

        Args:
            command: The command to run
            timeout: Timeout in seconds

        Returns:
            A tuple containing (return code, output)
        """
        try:
            # Prepare environment
            env = os.environ.copy()
            for key, value in self.env_vars.items():
                env[key] = value

            command_list = shlex.split(command)
            if self.host_os_type == 'windows' and not any(cmd in command for cmd in ['cmd', 'powershell']):
                command_list = ['cmd', '/c'] + command_list

            process = subprocess.Popen(
                command_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
                cwd=os.getcwd()
            )

            # Wait for the command to complete with timeout
            try:
                output, _ = process.communicate(timeout=timeout)
                return process.returncode, output
            except subprocess.TimeoutExpired:
                process.kill()
                return 1, f"Error: Command timed out after {timeout} seconds"

        except Exception as e:
            return 1, f"Error executing command: {e}"

    def _is_blocked(self, command: str) -> bool:
        """Check if a command is blocked or contains injection attempts.

        Args:
            command: The command to check

        Returns:
            True if the command is blocked, False otherwise
        """
        # Basic blocked commands check
        command_lower = command.lower()
        for block in self.blocked_commands:
            if re.search(rf"\b{re.escape(block)}\b", command_lower):
                return True
        
        # Enhanced injection detection
        return self._detect_command_injection(command)
    
    def _detect_command_injection(self, command: str) -> bool:
        """Detect potential command injection attempts.
        
        Args:
            command: The command to validate
            
        Returns:
            True if injection detected, False otherwise
        """
        # Dangerous shell metacharacters and patterns
        dangerous_patterns = [
            r';\s*\w',  # Command chaining with semicolon
            r'&&\s*\w',  # Command chaining with &&
            r'\|\|\s*\w',  # Command chaining with ||
            r'`[^`]*`',  # Command substitution with backticks
            r'\$\([^)]*\)',  # Command substitution with $()
            r'>\s*/\w',  # Redirection to system paths
            r'<\s*/\w',  # Input redirection from system paths
            r'\|\s*\w',  # Piping to other commands
            r'&\s*$',  # Background execution
            r'\x00',  # Null byte injection
            r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]',  # Control characters
        ]
        
        # Check for dangerous patterns
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE | re.MULTILINE):
                return True
        
        # Check for suspicious encoded content
        if self._contains_encoded_content(command):
            return True
            
        # Check for path traversal attempts
        if self._contains_path_traversal(command):
            return True
            
        return False
    
    def _contains_encoded_content(self, command: str) -> bool:
        """Check for encoded content that could hide malicious commands."""
        # Base64 detection
        if re.search(r'[A-Za-z0-9+/]{20,}={0,2}', command):
            return True
        
        # Hex encoding detection
        if re.search(r'\\x[0-9a-fA-F]{2}', command):
            return True
            
        # URL encoding detection
        if re.search(r'%[0-9a-fA-F]{2}', command):
            return True
            
        return False
    
    def _contains_path_traversal(self, command: str) -> bool:
        """Check for path traversal attempts."""
        # Directory traversal patterns
        traversal_patterns = [
            r'\.\./.*\.\.',  # Multiple directory traversal
            r'/\.\./\.\.',  # Absolute path traversal
            r'\.\.[\\/]',  # Basic traversal
            r'[\\/]\.\.[\\/]',  # Traversal in paths
        ]
        
        for pattern in traversal_patterns:
            if re.search(pattern, command):
                return True
                
        return False

    def _check_docker_available(self) -> bool:
        """Check if Docker is available.

        Returns:
            True if Docker is available, False otherwise
        """
        try:
            subprocess.run(
                ["docker", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
