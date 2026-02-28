"""Pydantic AI agent wired to MCP Video Server for tool calls."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

from .models import WorkoutAnalysis

SYSTEM_PROMPT = """\
You are an elite fitness coach with deep expertise in biomechanics, sports science, and injury
prevention. You are analyzing a workout video to provide a detailed, actionable critique.

Required analysis sequence — follow this exactly:
1. Call get_video_overview() first — study the entire video, count reps, identify exercise phases
   (setup, concentric, eccentric, transitions), and note any obvious form issues.
2. Call get_video_section() for each critical phase you identified: setup/starting position,
   the primary movement (concentric), the return movement (eccentric), and any transitions.
3. Call get_precise_frame() at moments of maximum load, potential form breaks, joint stress
   positions, and any critical technique points you want to examine closely.
4. After gathering sufficient visual evidence, produce the structured WorkoutAnalysis output.

When scoring technique (1-10):
- 1-3: Significant injury risk — unsafe to continue without correction
- 4-6: Functional but suboptimal — common beginner/intermediate patterns
- 7-8: Good form — minor refinements would enhance performance
- 9-10: Competition-ready — textbook technique

Observations must reference specific timestamps visible in the frame labels.
Be specific about body parts, angles, and positions. Prioritize safety over performance.

IMPORTANT: The video filename to use with all tools is provided in the user message.
"""


def create_agent(video_root: str) -> tuple[Agent[None, WorkoutAnalysis], MCPServerStdio]:
    """Create a workout analysis agent backed by an MCP video server.

    Args:
        video_root: Absolute path to the directory containing the video file.

    Returns:
        Tuple of (agent, mcp_server) — the server must be kept alive for the agent's lifetime.
    """
    # Find the uv binary path
    uv_path = "uv"

    # Find the workspace root (where the root pyproject.toml with [tool.uv.workspace] lives)
    workspace_root = Path(__file__).resolve().parents[4]  # examples/workout-judge-mcp/src/workout_judge_mcp -> root

    mcp_server = MCPServerStdio(
        uv_path,
        args=["run", "--project", str(workspace_root), "python", "-m", "mcp_video_server"],
        env={
            **os.environ,
            "MCP_VIDEO_ROOT": video_root,
            "MCP_VIDEO_DEBUG": "1",
        },
        cwd=str(workspace_root),
        timeout=30,
    )

    agent: Agent[None, WorkoutAnalysis] = Agent(
        "anthropic:claude-sonnet-4-6",
        output_type=WorkoutAnalysis,
        system_prompt=SYSTEM_PROMPT,
        defer_model_check=True,
        toolsets=[mcp_server],
    )

    return agent, mcp_server
