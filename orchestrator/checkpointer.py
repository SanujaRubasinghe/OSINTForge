from __future__ import annotations
import os
from typing import AsyncGenerator

from langgraph.checkpoint.memory import MemorySaver


async def get_checkpointer():
    """
    Returns the appropriate checkpointer based on environment.

    Production:  AsyncPostgresSaver backed by DATABASE_URL env var.
    Development: MemorySaver (in-process, no persistence between restarts).

    Usage in graph.py:
        checkpointer = await get_checkpointer()
        graph = _make_graph(checkpointer=checkpointer)
    """
    db_url = os.getenv("DATABASE_URL", "")

    if db_url:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            checkpointer = AsyncPostgresSaver.from_conn_string(db_url)
            await checkpointer.setup()   # creates checkpoint tables if not exist
            return checkpointer
        except Exception as e:
            import warnings
            warnings.warn(
                f"PostgreSQL checkpointer unavailable ({e}), falling back to MemorySaver.",
                RuntimeWarning,
                stacklevel=2,
            )

    return MemorySaver()


class CheckpointConfig:
    """
    Helper to build the LangGraph config dict for a given run.

    Each unique task_id gets its own thread so runs don't share state.

    Usage:
        config = CheckpointConfig.for_task(task_id)
        await graph.ainvoke(initial_state, config=config)
    """

    @staticmethod
    def for_task(task_id: str) -> dict:
        return {
            "configurable": {
                "thread_id": task_id,
            }
        }

    @staticmethod
    def for_stream(task_id: str, recursion_limit: int = 50) -> dict:
        return {
            "configurable":   {"thread_id": task_id},
            "recursion_limit": recursion_limit,
        }
