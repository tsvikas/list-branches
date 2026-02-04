# /// script
# dependencies = ["rich", "cyclopts"]
# ///
"""List all branches with PR status and ahead/behind relative to main."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

import cyclopts
from rich.console import Console
from rich.table import Table

app = cyclopts.App()

SORT_FIELDS = {"branch", "pr", "ahead", "behind", "ours"}


def gh(*args: str) -> str:
    """Run a gh command and return stdout."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh {args[0]} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def get_pr_statuses(repo: str) -> dict[str, str]:
    """Fetch PR status for all branches."""
    prs = json.loads(
        gh(
            "pr",
            "list",
            "-R",
            repo,
            "--state",
            "all",
            "--json",
            "headRefName,state",
        )
    )
    return {p["headRefName"]: p["state"].lower() for p in prs}


def find_main_branch(branch_names: list[str]) -> str:
    """Find the main branch name from a list of branches."""
    for name in ["main", "master"]:
        if name in branch_names:
            return name
    raise RuntimeError("no main branch found")


def get_branch_comparisons(
    repo: str, main_branch: str, branch_names: list[str]
) -> dict[str, tuple[int, int]]:
    """Fetch ahead/behind counts for branches in parallel."""

    def get_comparison(branch: str) -> tuple[str, int | str, int | str]:
        try:
            data = gh(
                "api",
                f"repos/{repo}/compare/{main_branch}...{branch}",
                "--jq",
                r'"\(.ahead_by) \(.behind_by)"',
            )
            ahead, behind = data.split()
            return branch, int(ahead), int(behind)
        except Exception:
            return branch, "?", "?"

    with ThreadPoolExecutor(max_workers=10) as pool:
        return {
            branch: (ahead, behind)
            for branch, ahead, behind in pool.map(get_comparison, branch_names)
        }


def check_ancestry(repo: str, commit: str, branch_names: list[str]) -> dict[str, bool]:
    """Check if commit is an ancestor of each branch (i.e., branch contains commit)."""

    def is_ancestor(branch: str) -> tuple[str, bool]:
        try:
            status = gh(
                "api",
                f"repos/{repo}/compare/{commit}...{branch}",
                "--jq",
                ".status",
            )
            # "ahead" or "identical" means commit is ancestor of branch
            return branch, status in ("ahead", "identical")
        except Exception:
            return branch, False

    with ThreadPoolExecutor(max_workers=10) as pool:
        return dict(pool.map(is_ancestor, branch_names))


def get_branch_names(repo: str) -> tuple[str, list[str]]:
    """Fetch all branches with ahead/behind counts."""
    branch_names = gh(
        "api", f"repos/{repo}/branches", "--paginate", "--jq", ".[].name"
    ).splitlines()
    main_branch = find_main_branch(branch_names)
    branch_names = [b for b in branch_names if b != main_branch]

    if not branch_names:
        return main_branch, {}

    return main_branch, branch_names


def build_rows(
    branches: dict,
    pr_statuses: dict,
    ancestry: dict[str, bool] | None,
    filter_str: str | None,
) -> list[dict]:
    """Build row dicts from branches and PR statuses, with optional filtering."""
    rows = []
    for name, (ahead, behind) in branches.items():
        if filter_str and filter_str not in name:
            continue
        row = {
            "branch": name,
            "pr": pr_statuses.get(name, "-"),
            "ahead": ahead,
            "behind": behind,
            "ours": ancestry.get(name) if ancestry else None,
        }
        rows.append(row)
    return rows


def parse_sort(sort_str: str) -> list[tuple[str, bool]]:
    """Parse sort string like 'pr,-behind,ahead' into [(field, descending), ...]."""
    result = []
    for part in sort_str.split(","):
        part = part.strip()
        desc = part.startswith("-")
        field = part[1:] if desc else part
        if field not in SORT_FIELDS:
            raise ValueError(
                f"Unknown sort field: {field}. Use: {', '.join(SORT_FIELDS)}"
            )
        result.append((field, desc))
    return result


def make_sort_key(sort_spec: list[tuple[str, bool]]):
    """Create a sort key function from parsed sort spec."""

    def sort_key(row):
        def field_val(field, desc):
            val = row[field]
            if field in ("ahead", "behind") and not isinstance(val, int):
                val = -1 if desc else float("inf")
            if field == "ours":
                # True > False > None; for desc, reverse
                val = {True: 2, False: 1, None: 0}.get(val, 0)
                return -val if desc else val
            if desc:
                return -val if isinstance(val, int) else (1, val)
            return (0, val) if isinstance(val, str) else val

        return tuple(field_val(f, d) for f, d in sort_spec)

    return sort_key


def print_table(rows: list[dict], main_branch: str, show_ours: bool):
    """Print formatted branch table using rich."""
    table = Table(title=f"Branches vs {main_branch}")
    table.add_column("Branch", style="cyan")
    table.add_column("PR", style="magenta")
    table.add_column("Ahead", justify="right", style="green")
    table.add_column("Behind", justify="right", style="red")
    if show_ours:
        table.add_column("Ours", justify="center")

    for row in rows:
        cols = [row["branch"], row["pr"], str(row["ahead"]), str(row["behind"])]
        if show_ours:
            ours = row.get("ours")
            cols.append("[green]yes[/]" if ours else "[dim]no[/]" if ours is False else "-")
        table.add_row(*cols)

    Console().print(table)


def get_default_repo() -> str:
    """Get owner/repo from current directory's git remote."""
    try:
        return gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")
    except RuntimeError:
        return ""


@app.default
def main(
    repo: str | None = None,
    sort: str = "branch",
    filter: str | None  = None,
    since: str | None  = None,
):
    """List branches with PR status and ahead/behind counts.

    Args:
        repo: GitHub repository in owner/repo format (default: current directory's remote).
        sort: Sort fields, comma-separated. Prefix with - for descending. E.g. "pr,-behind,-ahead"
        filter: Filter branches containing this substring.
        since: Commit SHA to check ancestry. Shows "ours" column for branches containing this commit.
    """
    if repo is None:
        repo = get_default_repo()
    if not repo:
        raise SystemExit(
            "No repo specified and not in a git directory with a GitHub remote."
        )

    pr_statuses = get_pr_statuses(repo)
    main_branch, branch_names = get_branch_names(repo)
    branches = get_branch_comparisons(repo, main_branch, branch_names)
    ancestry = check_ancestry(repo, since, branch_names) if since else None
    rows = build_rows(branches, pr_statuses, ancestry, filter)
    rows.sort(key=make_sort_key(parse_sort(sort)))
    print_table(rows, main_branch, show_ours=since is not None)


if __name__ == "__main__":
    app()
