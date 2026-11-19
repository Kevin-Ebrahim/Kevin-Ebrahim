"""Refresh the four public counters used by the profile. Requires an authenticated gh CLI."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess

LOGIN = "Kevin-Ebrahim"
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "github-stats.json"


def pages(query, **variables):
    args = ["gh", "api", "graphql", "--paginate", "--slurp", "-f", "query=" + query]
    for name, value in variables.items():
        args.extend(["-f", f"{name}={value}"])
    return [page["data"] for page in json.loads(subprocess.check_output(args))]


def contributed_repos(start, end):
    [data] = pages("""
      query($login: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $login) {
          contributionsCollection(from: $from, to: $to) {
            commitContributionsByRepository(maxRepositories: 100) {
              repository { nameWithOwner isPrivate }
            }
          }
        }
      }
    """, login=LOGIN, **{"from": start.isoformat(), "to": end.isoformat()})
    rows = data["user"]["contributionsCollection"]["commitContributionsByRepository"]
    # This field has no cursor. Split a full window to include less active repos.
    if len(rows) == 100:
        seconds = int((end - start).total_seconds())
        if seconds < 1:
            raise ValueError("GitHub's repository limit was reached within a single second")
        middle = start + timedelta(seconds=seconds // 2)
        return contributed_repos(start, middle) | contributed_repos(middle + timedelta(seconds=1), end)
    return {row["repository"]["nameWithOwner"] for row in rows if not row["repository"]["isPrivate"]}


def public_stats():
    owned = pages("""
      query($login: String!, $endCursor: String) {
        user(login: $login) {
          id createdAt followers { totalCount }
          repositories(first: 100, after: $endCursor, ownerAffiliations: OWNER, privacy: PUBLIC) {
            nodes { nameWithOwner }
            pageInfo { hasNextPage endCursor }
          }
        }
      }
    """, login=LOGIN)
    user = owned[0]["user"]
    repos = {repo["nameWithOwner"] for page in owned for repo in page["user"]["repositories"]["nodes"]}
    owned_count = len(repos)

    start_year = int(user["createdAt"][:4])
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for year in range(start_year, now.year + 1):
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = min(now, start.replace(year=year + 1) - timedelta(seconds=1))
        repos.update(contributed_repos(start, end))

    # Forks and transferred history can contain the same commit.
    lines_by_commit = {}
    for repo in sorted(repos):
        owner, name = repo.split("/")
        for page in pages("""
          query($owner: String!, $name: String!, $user: ID!, $endCursor: String) {
            repository(owner: $owner, name: $name) {
              defaultBranchRef {
                target {
                  ... on Commit {
                    history(first: 100, after: $endCursor, author: {id: $user}) {
                      nodes { oid additions deletions }
                      pageInfo { hasNextPage endCursor }
                    }
                  }
                }
              }
            }
          }
        """, owner=owner, name=name, user=user["id"]):
            branch = page["repository"]["defaultBranchRef"]
            if branch:
                for commit in branch["target"]["history"]["nodes"]:
                    lines_by_commit[commit["oid"]] = commit["additions"] - commit["deletions"]

    return {
        "public_repos": owned_count,
        "commits": len(lines_by_commit),
        "followers": user["followers"]["totalCount"],
        "net_lines": sum(lines_by_commit.values()),
    }


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(public_stats(), indent=2) + "\n", encoding="utf-8")
