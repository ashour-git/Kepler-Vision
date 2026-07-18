"""Fetch raw job logs for the latest CI run."""
from urllib.request import urlopen, Request
import json, sys

REPO = "ashour-git/Kepler-Vision"
headers = {"Accept": "application/vnd.github+json", "User-Agent": "CheckCI/1.0"}

# Get latest CI run
runs = json.loads(urlopen(Request(f"https://api.github.com/repos/{REPO}/actions/runs?per_page=2&event=push", headers=headers)).read())
for r in runs.get("workflow_runs", []):
    if r["name"] != "CI":
        continue
    print(f"Run #{r['run_number']} ({r['id']}): status={r['status']} conclusion={r.get('conclusion','?')}")
    # Get jobs
    jobs = json.loads(urlopen(Request(r["jobs_url"], headers=headers)).read())
    for j in jobs.get("jobs", []):
        print(f"  Job: {j['name']} ({j['id']}): conclusion={j.get('conclusion','?')}")

        # Try to get the raw log
        try:
            logs_url = j.get("url", "") + "/logs"
            # Logs are not available via the REST API without auth; use the raw log API
            log_req = Request(
                f"https://api.github.com/repos/{REPO}/actions/jobs/{j['id']}/logs",
                headers={"Accept": "text/plain", "User-Agent": "CheckCI/1.0"},
            )
            # This redirects; we need to follow
            from urllib.request import build_opener, HTTPRedirectHandler
            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    print(f"    Logs redirect to: {newurl}")
                    return None
            try:
                resp = urlopen(log_req)
                # If we get here, the API returned log content directly
                logs = resp.read().decode("utf-8", errors="replace")
                for line in logs.split("\n")[-30:]:
                    print(f"    {line}")
            except Exception as e2:
                print(f"    Could not fetch logs: {e2}")
            try:
                # Try the annotation API
                anns = json.loads(urlopen(Request(
                    f"https://api.github.com/repos/{REPO}/actions/runs/{r['id']}/annotations",
                    headers=headers,
                )).read())
                for a in anns[:5]:
                    print(f"    Annotation ({a.get('annotation_level','?')}): {a.get('message','')[:200]}")
            except Exception:
                pass
        except Exception as e:
            print(f"    Could not fetch log URL: {e}")

    break
