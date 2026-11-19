"""Refresh the GitHub profile stats. Requires an authenticated gh CLI."""

from datetime import date, datetime, timedelta, timezone
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


def contribution_activity(start, end):
    [data] = pages("""
      query($login: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $login) {
          contributionsCollection(from: $from, to: $to) {
            contributionCalendar { weeks { contributionDays { date contributionCount } } }
            commitContributionsByRepository(maxRepositories: 100) {
              repository { nameWithOwner isPrivate }
            }
          }
        }
      }
    """, login=LOGIN, **{"from": start.isoformat(), "to": end.isoformat()})
    collection = data["user"]["contributionsCollection"]
    rows = collection["commitContributionsByRepository"]
    # This field has no cursor. Split a full window to include less active repos.
    if len(rows) == 100:
        seconds = int((end - start).total_seconds())
        if seconds < 1:
            raise ValueError("GitHub's repository limit was reached within a single second")
        middle = start + timedelta(seconds=seconds // 2)
        early_repos, early_days = contribution_activity(start, middle)
        late_repos, late_days = contribution_activity(middle + timedelta(seconds=1), end)
        return early_repos | late_repos, early_days | late_days
    repos = {row["repository"]["nameWithOwner"] for row in rows if not row["repository"]["isPrivate"]}
    active_days = {
        date.fromisoformat(day["date"])
        for week in collection["contributionCalendar"]["weeks"]
        for day in week["contributionDays"] if day["contributionCount"] > 0
    }
    return repos, active_days


def longest_streak(active_days):
    longest = current = 0
    previous = None
    for day in sorted(active_days):
        current = current + 1 if previous and (day - previous).days == 1 else 1
        longest = max(longest, current)
        previous = day
    return longest


def public_stats():
    owned = pages("""
      query($login: String!, $endCursor: String) {
        user(login: $login) {
          id createdAt followers { totalCount }
          repositories(first: 100, after: $endCursor, ownerAffiliations: OWNER, privacy: PUBLIC) {
            nodes { nameWithOwner stargazerCount }
            pageInfo { hasNextPage endCursor }
          }
        }
      }
    """, login=LOGIN)
    user = owned[0]["user"]
    owned_stars = {repo["nameWithOwner"]: repo["stargazerCount"]
                   for page in owned for repo in page["user"]["repositories"]["nodes"]}
    repos = set(owned_stars)

    start_year = int(user["createdAt"][:4])
    now = datetime.now(timezone.utc).replace(microsecond=0)
    active_days = set()
    for year in range(start_year, now.year + 1):
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = min(now, start.replace(year=year + 1) - timedelta(seconds=1))
        year_repos, year_days = contribution_activity(start, end)
        repos.update(year_repos)
        active_days.update(year_days)

    # Forks and transferred history can contain the same commit.
    commit_ids = set()
    additions = deletions = 0
    for repo in sorted(repos):
        owner, name = repo.split("/")
        for page in pages("""
          query($owner: String!, $name: String!, $user: ID!, $endCursor: String) {
            repository(owner: $owner, name: $name) {
              defaultBranchRef {
                target {
                  ... on Commit {
                    history(first: 100, after: $endCursor, author: {id: $user}) {
                      nodes { oid additions deletions parents(first: 1) { totalCount } }
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
                    if commit["oid"] in commit_ids:
                        continue
                    commit_ids.add(commit["oid"])
                    # Merge diffs can repeat changes already counted in their parents.
                    if commit["parents"]["totalCount"] <= 1:
                        additions += commit["additions"]
                        deletions += commit["deletions"]

    return {
        "public_repos": len(owned_stars),
        "commits": len(commit_ids),
        "stars": sum(owned_stars.values()),
        "additions": additions,
        "deletions": deletions,
        "followers": user["followers"]["totalCount"],
        "longest_streak": longest_streak(active_days),
        "active_days_365": sum(0 <= (now.date() - day).days < 365 for day in active_days),
    }


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(public_stats(), indent=2) + "\n", encoding="utf-8")
