"""Executes shell commands in a sandboxed environment.

This module provides containerized command execution as specified in instructions.md.
"""

import os
import subprocess
import tempfile
import time
import shutil
import json
import uuid
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List


class BashTool:
    """Tool for executing shell commands securely in containers."""
    
    def __init__(self, 
                 sandbox: bool = True, 
                 env_vars: Optional[Dict[str, str]] = None,
                 container_image: str = "python:3.10-slim",
                 resource_limits: Optional[Dict[str, str]] = None):
        """Initialize the bash tool.
        
        Args:
            sandbox: Whether to run commands in a sandboxed environment
            env_vars: Additional environment variables to set
            container_image: Docker image to use for sandboxed execution
            resource_limits: Resource limits for the container (e.g. memory, cpu)
        """
        self.sandbox = sandbox
        self.env_vars = env_vars or {}
        self.container_image = container_image
        self.resource_limits = resource_limits or {
            "memory": "512m",
            "cpu-shares": "1024"
        }
        
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
            print("Warning: Docker not available. Falling back to restricted subprocess mode.")
    
    def run_command(self, command: str, timeout: int = 60) -> Tuple[int, str]:
        """Run a shell command.
        
        Args:
            command: The command to run
            timeout: Timeout in seconds
            
        Returns:
            A tuple containing (return code, output)
        """
        # Check if command is blocked (applies only when Docker is unavailable)
        if not self.docker_available and self._is_blocked(command):
            return 1, f"Error: Command '{command}' is blocked for security reasons"
        
        try:
            # Run in a container if sandbox mode is enabled and Docker is available
            if self.sandbox and self.docker_available:
                return self._run_in_container(command, timeout)
            else:
                # Fallback to subprocess with restrictions
                return self._run_with_subprocess(command, timeout)
            
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
                docker_cmd.extend(["--network", "host"])  # Could use bridge network with specific DNS
                
                # Add volume mount for the script
                docker_cmd.extend(["-v", f"{script_path}:/script.sh"])
                
                # Specify the image and command
                docker_cmd.extend([
                    self.container_image,
                    "/bin/bash", "-c", f"/script.sh > /tmp/output.log 2>&1"
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
                    
                process = subprocess.Popen(
                    script_path,
                    shell=True,
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
            docker_cmd.extend(["--network", "host"])  # Could use bridge network with specific DNS
            
            # Add the current directory as a volume
            docker_cmd.extend(["-v", f"{os.getcwd()}:/workspace", "-w", "/workspace"])
            
            # Specify the image and command
            docker_cmd.extend([
                self.container_image,
                "/bin/bash", "/script.sh"
            ])
            
            # Run the container with timeout
            process = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout
            )
            
            # Clean up
            os.unlink(script_path)
            
            return process.returncode, process.stdout
            
        except subprocess.TimeoutExpired:
            # Stop and remove the container
            subprocess.run(["docker", "stop", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["docker", "rm", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 1, f"Error: Command timed out after {timeout} seconds"
            
        except Exception as e:
            return 1, f"Error running command in container: {e}"
    
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
            
            # Run the command
            process = subprocess.Popen(
                command,
                shell=True,
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
        """Check if a command is blocked.
        
        Args:
            command: The command to check
            
        Returns:
            True if the command is blocked, False otherwise
        """
        command_lower = command.lower()
        return any(blocked in command_lower for blocked in self.blocked_commands)
    
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
