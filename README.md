# list-branches

CLI tool to list GitHub repository branches with their PR status and ahead/behind counts relative to main.

## Requirements

- [GitHub CLI](https://cli.github.com/) (`gh`) installed and authenticated
- [uv](https://github.com/astral-sh/uv) for running the script

## Usage

```bash
# List branches for current repo
uv run list_branches.py

# List branches for a specific repo
uv run list_branches.py --repo owner/repo

# Sort by PR status, then by most behind
uv run list_branches.py --sort pr,-behind

# Filter branches containing "feature"
uv run list_branches.py --filter feature

# Show which branches contain a specific commit
uv run list_branches.py --since abc123
```

## Options

| Option | Description |
|--------|-------------|
| `--repo` | GitHub repository in `owner/repo` format (default: current directory's remote) |
| `--sort` | Sort fields, comma-separated. Prefix with `-` for descending. Fields: `branch`, `pr`, `ahead`, `behind`, `ours` |
| `--filter` | Filter branches containing this substring |
| `--since` | Commit SHA to check ancestry. Adds "Ours" column showing if branch contains the commit |

## Example Output

```
        Branches vs main
┏━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Branch        ┃ PR     ┃ Ahead ┃ Behind ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ feature-auth  │ open   │     3 │      1 │
│ feature-ui    │ merged │    12 │      0 │
│ bugfix-login  │ -      │     1 │      5 │
└───────────────┴────────┴───────┴────────┘
```
