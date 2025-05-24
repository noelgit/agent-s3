"""
EnvTool: Environment activation and package management utilities.
Follows security and performance best practices (see Copilot instructions).
"""
import os
from typing import Dict
from typing import Optional

class EnvTool:
    """Handles virtual environment activation and package inspection."""
    def __init__(self, bash_tool):
        self.bash_tool = bash_tool

    def activate_virtual_env(self) -> str:
        """Detects and returns the shell prefix to activate the current Python virtual environment.
        Returns an empty string if no env is found. Handles .venv, venv, and conda.
        """
        # Check for venv/.venv
        for env_dir in [".venv", "venv"]:
            if os.path.isdir(env_dir):
                activate_path = os.path.join(env_dir, "bin", "activate")
                if os.path.isfile(activate_path):
                    return f"source {activate_path} && "
        # Check for conda
        conda_env = os.environ.get("CONDA_DEFAULT_ENV")
        if conda_env:
            return f"conda activate {conda_env} && "
        return ""

    def get_installed_packages(self, activation_prefix: Optional[str] = None) -> Dict[str, str]:
        """Returns a dict of installed pip packages and versions in the current environment."""
        activation_prefix = activation_prefix or self.activate_virtual_env()
        cmd = f"{activation_prefix}pip freeze"
        result = self.bash_tool.run_command(cmd, timeout=60)
        packages = {}
        if result[0] == 0:
            for line in result[1].splitlines():
                if "==" in line:
                    name, version = line.strip().split("==", 1)
                    packages[name] = version
        return packages
