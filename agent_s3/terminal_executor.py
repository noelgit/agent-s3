import subprocess
import threading
import os
import re
import shlex
from typing import Tuple, List, Optional, Dict, Set, Any

class TerminalExecutor:
    """Executes shell commands in a sandbox with denylist and timeout enforcement."""

    def __init__(self, config):
        """Initialize the executor with config settings."""
        # Default dangerous commands that should be denied
        default_denylist = [
            'rm -rf', 'rm -r', 'rmdir', 'sudo', 'su', 
            'shutdown', 'reboot', 'halt', 'poweroff',
            'dd', 'mkfs', 'format', 'fdisk', 'wget', 'curl -O',
            '>(', '&>', '2>', '>', '>>', '|', ';', '&&', '||',
            'eval', 'exec', 'source', 'bash -c', 'ssh', 'telnet',
            'nc', 'ncat', 'nmap', 'chmod 777', 'chmod -R'
        ]
        
        self.denylist: List[str] = config.config.get('denylist', default_denylist)
        self.timeout: float = config.config.get('command_timeout', 30.0)
        self.allowed_dirs: List[str] = config.config.get('allowed_dirs', [os.getcwd()])
        self.max_output_size: int = config.config.get('max_output_size', 1024 * 1024)  # 1MB by default
        self.failure_threshold: int = config.config.get('failure_threshold', 5)
        self.cooldown_period: int = config.config.get('cooldown_period', 300)
        self.failure_count: int = 0
        self.last_failure_time: float = 0
        
        # Initialize logging
        try:
            import logging
            self.logger = logging.getLogger("terminal_executor")
        except ImportError:
            self.logger = None

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a path is within allowed directories."""
        abs_path = os.path.abspath(path)
        for allowed_dir in self.allowed_dirs:
            if abs_path.startswith(os.path.abspath(allowed_dir)):
                return True
        return False

    def _validate_command(self, command: str) -> Tuple[bool, str]:
        """
        Validate a command against security rules.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check against denylist
        for forbidden in self.denylist:
            if forbidden in command:
                if self.logger:
                    self.logger.warning(f"Command contains forbidden token: {forbidden}")
                return False, f"Error: Command contains forbidden token '{forbidden}'"

        # Extract file paths and check if they're allowed
        path_pattern = re.compile(r'(?:^|\s)(\/[^\s]+)')
        paths = path_pattern.findall(command)
        
        for path in paths:
            path = path.strip()
            if not self._is_path_allowed(path):
                if self.logger:
                    self.logger.warning(f"Command attempts to access restricted path: {path}")
                return False, f"Error: Command attempts to access restricted path '{path}'"

        return True, ""

    def run_command(self, command: str, env: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
        """Run a shell command, enforcing denylist, path restrictions, and timeout.

        Args:
            command: The shell command to execute
            env: Optional environment variables
        Returns:
            A tuple (exit_code, output)
        """
        import time
        
        # Check cooldown period if we've had too many failures
        current_time = time.time()
        if self.failure_count >= self.failure_threshold:
            if current_time - self.last_failure_time < self.cooldown_period:
                return 1, f"Error: Too many failed commands. Try again in {self.cooldown_period - int(current_time - self.last_failure_time)} seconds."
            else:
                # Reset failure count after cooldown
                self.failure_count = 0
        
        # Validate command
        is_valid, error_message = self._validate_command(command)
        if not is_valid:
            self.failure_count += 1
            self.last_failure_time = current_time
            return 1, error_message
            
        # Set up environment
        execution_env = os.environ.copy()
        if env:
            execution_env.update(env)
            
        # Remove potentially dangerous environment variables
        for dangerous_var in ['LD_PRELOAD', 'LD_LIBRARY_PATH']:
            if dangerous_var in execution_env:
                del execution_env[dangerous_var]
        
        # Execute command with exception handling
        try:
            proc = subprocess.Popen(
                command, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                env=execution_env,
                cwd=os.getcwd()
            )
            
            # Set up timeout
            timer = threading.Timer(self.timeout, proc.kill)
            timer.start()
            
            # Collect output with size limit
            output_chunks = []
            total_size = 0
            
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                    
                total_size += len(chunk)
                if total_size <= self.max_output_size:
                    output_chunks.append(chunk)
                else:
                    output_chunks.append("\n... Output truncated due to size limit ...")
                    break
            
            proc.wait()
            timer.cancel()
            
            output = ''.join(output_chunks)
            
            # Reset failure count on success
            if proc.returncode == 0:
                self.failure_count = 0
                
            return proc.returncode, output
            
        except Exception as e:
            # Log error and return
            if self.logger:
                self.logger.error(f"Error executing command: {e}")
            
            self.failure_count += 1
            self.last_failure_time = current_time
            return 1, f"Error executing command: {e}"
            
    def run_command_in_background(self, command: str, env: Optional[Dict[str, str]] = None) -> str:
        """
        Run a command in the background and return a process ID.
        
        Args:
            command: The command to execute
            env: Optional environment variables
            
        Returns:
            A process identifier string that can be used to check status
        """
        # Validate command
        is_valid, error_message = self._validate_command(command)
        if not is_valid:
            return f"ERROR: {error_message}"
            
        try:
            import uuid
            process_id = str(uuid.uuid4())
            
            def run_bg():
                execution_env = os.environ.copy()
                if env:
                    execution_env.update(env)
                
                # Remove potentially dangerous environment variables
                for dangerous_var in ['LD_PRELOAD', 'LD_LIBRARY_PATH']:
                    if dangerous_var in execution_env:
                        del execution_env[dangerous_var]
                        
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=execution_env,
                    cwd=os.getcwd()
                )
                
                output, _ = proc.communicate()
                return proc.returncode, output
                
            # Start background thread
            thread = threading.Thread(target=run_bg)
            thread.daemon = True
            thread.start()
            
            return f"Background process started with ID: {process_id}"
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error starting background command: {e}")
            return f"ERROR: Failed to start background process: {e}"