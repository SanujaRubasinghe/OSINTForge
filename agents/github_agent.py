from __future__ import annotations
import uuid
import os
from datetime import datetime, timezone

from github import Github, GithubException

from orchestrator.state import OSINTState, FindingRecord


class GitHubAgent:
    SECRET_PATTERNS = ["password", "api_key", "secret", "BEGIN RSA", "token", "credential"]

    def __init__(self):
        token = os.getenv("GITHUB_TOKEN", "")
        self.gh = Github(token) if token else Github()

    def run(self, state: OSINTState) -> dict:
        tasks = [t for t in state["collection_tasks"] if t["type"] == "github" and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "github_agent", "action": "no_tasks"}]}

        findings = []
        for task in tasks:
            target = task["query"].strip()
            findings.extend(self._collect_org(target))
            findings.extend(self._collect_user(target))
            findings.extend(self._scan_secrets(target))

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "github_agent",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    def _collect_org(self, name: str) -> list[FindingRecord]:
        try:
            org = self.gh.get_organization(name)
            members = [{"login": m.login, "name": m.name, "email": m.email,
                        "bio": m.bio, "location": m.location, "company": m.company}
                       for m in list(org.get_members())[:50]]
            repos = [{"name": r.name, "description": r.description, "language": r.language,
                      "stars": r.stargazers_count, "topics": r.get_topics(),
                      "last_push": str(r.pushed_at)}
                     for r in list(org.get_repos())[:30]]

            text = (
                f"GitHub Org: {org.name or name}\n"
                f"Description: {org.description}\n"
                f"Blog: {org.blog}\nLocation: {org.location}\nEmail: {org.email}\n\n"
                f"Members ({len(members)}):\n"
                + "\n".join(f"  - {m['login']} ({m['name']}) {m['email'] or ''} {m['location'] or ''}" for m in members)
                + f"\n\nRepositories ({len(repos)}):\n"
                + "\n".join(f"  - {r['name']}: {r['description']} [{r['language']}] ★{r['stars']}" for r in repos)
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "github_org",
                "source_url":  f"https://github.com/{name}",
                "raw_text":    text,
                "title":       f"GitHub organisation: {name}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata":    {"members": members, "repos": repos},
            }]
        except GithubException:
            return []

    def _collect_user(self, username: str) -> list[FindingRecord]:
        try:
            user = self.gh.get_user(username)
            repos = list(user.get_repos())[:20]
            commit_emails = self._harvest_commit_emails(repos)
            text = (
                f"GitHub User: {user.login}\nName: {user.name}\n"
                f"Email: {user.email}\nBio: {user.bio}\n"
                f"Company: {user.company}\nLocation: {user.location}\n"
                f"Blog: {user.blog}\nTwitter: {user.twitter_username}\n"
                f"Followers: {user.followers}\nPublic repos: {user.public_repos}\n\n"
                f"Commit emails found: {', '.join(commit_emails)}"
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "github_user",
                "source_url":  f"https://github.com/{username}",
                "raw_text":    text,
                "title":       f"GitHub user: {username}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "email":         user.email,
                    "commit_emails": commit_emails,
                    "company":       user.company,
                    "location":      user.location,
                },
            }]
        except GithubException:
            return []

    def _harvest_commit_emails(self, repos) -> list[str]:
        emails = set()
        for repo in repos[:5]:
            try:
                for commit in list(repo.get_commits())[:30]:
                    e = commit.commit.author.email
                    if e and "noreply" not in e:
                        emails.add(e)
            except Exception:
                pass
        return list(emails)

    def _scan_secrets(self, org_name: str) -> list[FindingRecord]:
        findings = []
        for pattern in self.SECRET_PATTERNS:
            try:
                query = f"org:{org_name} {pattern}"
                results = list(self.gh.search_code(query))[:5]
                for item in results:
                    findings.append({
                        "id":          str(uuid.uuid4()),
                        "source_type": "github_secret_scan",
                        "source_url":  item.html_url,
                        "raw_text":    f"Potential secret pattern '{pattern}' found in {item.repository.full_name}/{item.path}",
                        "title":       f"[RISK] Potential exposed secret in {item.repository.full_name}",
                        "timestamp":   datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "pattern": pattern,
                            "repo":    item.repository.full_name,
                            "file":    item.path,
                            "risk":    "potential_secret_exposure",
                        },
                    })
            except Exception:
                pass
        return findings
