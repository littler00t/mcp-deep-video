"""Entry point for python -m mcp_video_server."""

from __future__ import annotations

import asyncio

from mcp.server.stdio import stdio_server

from .server import create_server


def main() -> None:
    server = create_server()

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
