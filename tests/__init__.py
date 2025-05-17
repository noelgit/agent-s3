# Ensure tests is a package for pytest discovery

"""Test package initialization.

This module provides shims for optional third-party dependencies that may
not be installed in the testing environment. Currently it creates a minimal
``requests`` substitute so modules importing ``requests`` during tests do not
fail with ``ModuleNotFoundError``.
"""

import sys
import types

# Provide a lightweight stub for the ``requests`` library if it is missing.
try:  # pragma: no cover - only executed when requests is available
    import requests as _requests  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - simplified handling for test env
    stub = types.ModuleType("requests")

    class _Timeout(Exception):
        pass

    class _ConnectionError(Exception):
        pass

    class _HTTPError(Exception):
        pass

    class _exceptions:
        Timeout = _Timeout
        ConnectionError = _ConnectionError
        HTTPError = _HTTPError

    stub.exceptions = _exceptions
    sys.modules["requests"] = stub

# Provide a lightweight stub for the ``numpy`` library if it is missing.
try:  # pragma: no cover - only executed when numpy is available
    import numpy as _np  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - simplified handling for test env
    np_stub = types.ModuleType("numpy")
    sys.modules["numpy"] = np_stub

# Provide a lightweight stub for the ``torch`` library if it is missing.
try:  # pragma: no cover - only executed when torch is available
    import torch as _torch  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - simplified handling for test env
    torch_stub = types.ModuleType("torch")
    class _Tensor:
        pass
    torch_stub.Tensor = _Tensor
    sys.modules["torch"] = torch_stub

# Provide a lightweight stub for the ``gptcache`` library if it is missing.
try:  # pragma: no cover - only executed when gptcache is available
    import gptcache as _gptcache  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - simplified handling for test env
    gptcache_stub = types.ModuleType("gptcache")
    gptcache_stub.cache = None
    sys.modules["gptcache"] = gptcache_stub

# Provide a lightweight stub for the ``jsonschema`` library if it is missing.
try:  # pragma: no cover - only executed when jsonschema is available
    import jsonschema as _jsonschema  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - simplified handling for test env
    jsonschema_stub = types.ModuleType("jsonschema")
    def _validate(instance=None, schema=None, *args, **kwargs):
        return None
    jsonschema_stub.validate = _validate
    sys.modules["jsonschema"] = jsonschema_stub

# Provide a lightweight stub for the ``websockets`` library if it is missing.
try:  # pragma: no cover - only executed when websockets is available
    import websockets as _websockets  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - simplified handling for test env
    websockets_stub = types.ModuleType("websockets")
    class WebSocketServerProtocol:
        pass
    websockets_stub.WebSocketServerProtocol = WebSocketServerProtocol
    sys.modules["websockets"] = websockets_stub

