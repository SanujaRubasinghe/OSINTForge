from __future__ import annotations
import os
from github import Github, GithubException

_gh: Github | None = None


def get_client() -> Github:
    global _gh
    if _gh is None:
        token = os.getenv("GITHUB_TOKEN", "")
        _gh   = Github(token) if token else Github()
    return _gh


def get_org(org_name: str) -> dict:
    try:
        org     = get_client().get_organization(org_name)
        members = [
            {"login": m.login, "name": m.name, "email": m.email,
             "location": m.location, "company": m.company,
             "twitter": m.twitter_username, "blog": m.blog}
            for m in list(org.get_members())[:50]
        ]
        repos = [
            {"name": r.name, "description": r.description,
             "language": r.language, "stars": r.stargazers_count,
             "topics": r.get_topics(), "pushed": str(r.pushed_at),
             "license": r.license.name if r.license else None}
            for r in list(org.get_repos())[:30]
        ]
        return {"name": org.name, "description": org.description,
                "blog": org.blog, "location": org.location,
                "email": org.email, "members": members, "repos": repos}
    except GithubException:
        return {}


def get_user(username: str) -> dict:
    try:
        u     = get_client().get_user(username)
        repos = list(u.get_repos())[:20]
        emails: set[str] = set()
        for repo in repos[:5]:
            try:
                for commit in list(repo.get_commits())[:30]:
                    e = commit.commit.author.email
                    if e and "noreply" not in e:
                        emails.add(e)
            except Exception:
                pass
        return {
            "login": u.login, "name": u.name, "email": u.email,
            "bio": u.bio, "company": u.company, "location": u.location,
            "blog": u.blog, "twitter": u.twitter_username,
            "followers": u.followers, "public_repos": u.public_repos,
            "commit_emails": list(emails),
        }
    except GithubException:
        return {}


def scan_secrets(org_name: str, patterns: list[str] | None = None) -> list[dict]:
    if patterns is None:
        patterns = ["password", "api_key", "secret", "BEGIN RSA", "token"]
    findings = []
    gh = get_client()
    for pattern in patterns:
        try:
            for item in list(gh.search_code(f"org:{org_name} {pattern}"))[:5]:
                findings.append({
                    "repo":    item.repository.full_name,
                    "file":    item.path,
                    "url":     item.html_url,
                    "pattern": pattern,
                })
        except Exception:
            pass
    return findings


def get_contributor_network(repo_full_name: str) -> list[dict]:
    try:
        repo = get_client().get_repo(repo_full_name)
        return [
            {"login": c.login, "contributions": c.contributions,
             "profile": c.html_url}
            for c in repo.get_contributors()
        ]
    except GithubException:
        return []
