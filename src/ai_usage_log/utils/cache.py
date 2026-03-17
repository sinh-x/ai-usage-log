"""Helper for the slim cache_path pattern used by large-response tools."""

import os
import time
from typing import Any

from ..models.schemas import SessionContext, SlimResponse


def write_to_cache(
    result: Any,
    tool_name: str,
    schema_paths: list[str],
    cache_path: str = "",
    context: SessionContext | None = None,
) -> str:
    """Write result to cache file and return slim JSON response.

    If cache_path is empty, auto-generates a path under /tmp/ai-usage-log/.
    The full result JSON is written to the cache file; only slim metadata is returned.

    Args:
        result: Pydantic model to serialize.
        tool_name: Tool name used in auto-generated filenames.
        schema_paths: List of jq path hints describing the cached content.
        cache_path: Explicit cache file path. Auto-generated if empty.
        context: Optional SessionContext to include inline in slim response.

    Returns:
        Slim JSON string with cached_at, schema_paths, and optional context.
    """
    if not cache_path:
        tmp_dir = "/tmp/ai-usage-log"
        os.makedirs(tmp_dir, exist_ok=True)
        cache_path = os.path.join(tmp_dir, f"{tool_name}-{int(time.time())}.json")
    else:
        parent = os.path.dirname(cache_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    error = None
    try:
        with open(cache_path, "w") as f:
            f.write(result.model_dump_json(indent=2))
    except Exception as e:
        error = str(e)

    slim = SlimResponse(
        cached_at=cache_path,
        schema_paths=schema_paths,
        context=context,
        error=error,
    )
    return slim.model_dump_json(indent=2)
