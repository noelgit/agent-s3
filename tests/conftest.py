import sys
from pathlib import Path

# Add project root to sys.path for module resolution
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
