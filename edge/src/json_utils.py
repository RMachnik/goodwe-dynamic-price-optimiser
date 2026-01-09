#!/usr/bin/env python3
"""
JSON Utilities - Fast JSON serialization wrapper using orjson
Provides ~5x faster JSON operations compared to stdlib json module
Falls back to stdlib json if orjson is not available
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try to import orjson, fall back to standard json
try:
    import orjson
    ORJSON_AVAILABLE = True
    logger.debug("Using orjson for fast JSON serialization")
except ImportError:
    import json as stdlib_json
    ORJSON_AVAILABLE = False
    logger.debug("orjson not available, using stdlib json")


def dumps(obj: Any, **kwargs) -> str:
    """
    Serialize object to JSON string
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments (passed to stdlib json if orjson unavailable)
    
    Returns:
        JSON string
    """
    if ORJSON_AVAILABLE:
        # orjson returns bytes, decode to str
        # orjson.OPT_INDENT_2 for pretty printing if indent is requested
        opts = 0
        if kwargs.get('indent'):
            opts |= orjson.OPT_INDENT_2
        return orjson.dumps(obj, option=opts).decode('utf-8')
    else:
        return stdlib_json.dumps(obj, **kwargs)


def loads(s: str) -> Any:
    """
    Deserialize JSON string to object
    
    Args:
        s: JSON string
    
    Returns:
        Deserialized object
    """
    if ORJSON_AVAILABLE:
        # orjson accepts both str and bytes
        return orjson.loads(s)
    else:
        return stdlib_json.loads(s)


def dump(obj: Any, fp, **kwargs) -> None:
    """
    Serialize object to JSON and write to file
    
    Args:
        obj: Object to serialize
        fp: File-like object
        **kwargs: Additional arguments (passed to stdlib json if orjson unavailable)
    """
    if ORJSON_AVAILABLE:
        opts = 0
        if kwargs.get('indent'):
            opts |= orjson.OPT_INDENT_2
        fp.write(orjson.dumps(obj, option=opts).decode('utf-8'))
    else:
        stdlib_json.dump(obj, fp, **kwargs)


def load(fp) -> Any:
    """
    Deserialize JSON from file
    
    Args:
        fp: File-like object
    
    Returns:
        Deserialized object
    """
    if ORJSON_AVAILABLE:
        return orjson.loads(fp.read())
    else:
        return stdlib_json.load(fp)
