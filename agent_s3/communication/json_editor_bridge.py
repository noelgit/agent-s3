"""Utility helpers for manipulating JSON data structures via dot paths."""
from __future__ import annotations

from typing import Any, List, Union


class JSONPath:
    """Simple JSON path utilities used by tests."""

    @staticmethod
    def parse_path(path: str) -> List[Union[str, int]]:
        components: List[Union[str, int]] = []
        token = ""
        i = 0
        while i < len(path):
            ch = path[i]
            if ch == '.':
                if token:
                    components.append(token)
                    token = ""
                i += 1
                continue
            if ch == '[':
                if token:
                    components.append(token)
                    token = ""
                j = path.find(']', i)
                index = int(path[i + 1 : j])
                components.append(index)
                i = j + 1
                continue
            token += ch
            i += 1
        if token:
            components.append(token)
        return components

    @staticmethod
    def set_value(data: Any, path: str, value: Any) -> None:
        parts = JSONPath.parse_path(path)
        cur = data
        for idx, part in enumerate(parts):
            if idx == len(parts) - 1:
                if isinstance(part, int):
                    while len(cur) <= part:
                        cur.append({})
                    cur[part] = value
                else:
                    cur[part] = value
                return
            if isinstance(part, int):
                while len(cur) <= part:
                    cur.append({})
                if not isinstance(cur[part], (dict, list)):
                    cur[part] = {}
                cur = cur[part]
            else:
                if part not in cur or not isinstance(cur[part], (dict, list)):
                    cur[part] = {}
                cur = cur[part]

    @staticmethod
    def get_value(data: Any, path: str) -> Any:
        parts = JSONPath.parse_path(path)
        cur = data
        for part in parts:
            if isinstance(part, int):
                cur = cur[part]
            else:
                cur = cur[part]
        return cur
