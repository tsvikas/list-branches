# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Single-file Python CLI tool that lists GitHub repository branches with their PR status and ahead/behind counts relative to main. Uses the `gh` CLI for GitHub API access.

## Running the Script

This script uses PEP 723 inline script metadata. Run with `uv`:

```bash
uv run list_branches.py [--repo owner/repo] [--sort field] [--filter substring] [--since commit]
```

Dependencies (`rich`, `cyclopts`) are automatically resolved from the inline metadata.

## Key Concepts

- **gh CLI wrapper**: All GitHub API calls go through the `gh()` helper which shells out to the GitHub CLI
- **Parallel API calls**: `ThreadPoolExecutor` with 10 workers fetches branch comparisons and ancestry checks concurrently
- **Sort specification**: Multi-field sorting via comma-separated fields with `-` prefix for descending (e.g., `pr,-behind,-ahead`)
- **Ancestry checking**: The `--since` flag checks if a commit is contained in each branch using the GitHub compare API
