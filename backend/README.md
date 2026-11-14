
# Backend — FastAPI Integration

## Overview

This module provides the FastAPI backend for the Pixolid
3D Enclosure Generation project.

It connects the Text-to-Design Agent with the Geometry
and Automatic Checks module.

## Features

- REST API implemented using FastAPI
- Automatic task ID generation
- Agent request and output validation
- Geometry validation and CAD generation
- STEP file download endpoint
- Automatic Swagger API documentation

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Basic API health check |
| POST | /design | Process a design request |
| GET | /design/{task_id}/download | Download a generated STEP file |

## Installation

From the repository root, create and activate a
Python virtual environment.

Install the backend dependencies:

    python -m pip install -r backend/requirements.txt

## Development Setup

The current prototype depends on Agent PR #1 and
Geometry PR #2.

Until those modules are merged, they can be checked
out into separate Git worktrees:

    git fetch origin
    git worktree add --detach ../pixolid-agent-review origin/feature/agent-prototype
    git worktree add --detach ../pixolid-geometry-review origin/feature/geometry-checks

On Windows PowerShell, from the repository root:

    $env:PYTHONPATH = (Resolve-Path ..\pixolid-agent-review).Path + ";" + (Resolve-Path ..\pixolid-geometry-review).Path

Start the backend:

    python -m uvicorn backend.main:app --reload

API documentation:

    http://127.0.0.1:8000/docs

## Current Limitations

- Agent and Geometry currently require separate worktrees.
- Agent supports Raspberry Pi 4, but Geometry currently
  uses placeholder test_board data.
- Natural-language-to-STEP generation is not yet
  fully working for the same supported board.
- Physical fit and printability are not fully verified.
- Backend integration tests are still pending.

## Status

Draft prototype — not yet ready for production or merge.
