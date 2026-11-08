"""Smoke test of a running AGroup site (used by the CI/CD staging job).

    python scripts/smoke_test.py http://127.0.0.1:8000

Checks that the pages load, protected routes refuse anonymous users, and a demo designer
can log in, read their data and log out. Standard library only. Exit code 1 on any failure.
"""
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5050").rstrip("/")
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
results = []


def request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with opener.open(req, timeout=10) as res:
            return res.status, res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as err:   # server not running / not reachable
        return 0, str(err)


def check(name, method, path, status, body=None, contains=None):
    code, text = request(method, path, body)
    ok = code == status and (contains is None or contains in text)
    results.append((ok, name, f"{method} {path}", f"{code} (expected {status})"))
    print(("PASS" if ok else "FAIL"), name, "-", method, path, code)
    return text


check("Customer website loads", "GET", "/", 200, contains="AGroup")
check("Staff portal loads", "GET", "/portal.html", 200)
check("Login page loads", "GET", "/login.html", 200)
check("Icons load", "GET", "/assets/icons/lucide.svg", 200, contains="<symbol")
check("Anonymous user is not logged in", "GET", "/api/auth/me", 401)
check("Designer data needs login", "GET", "/api/company", 401)
check("Wrong password is refused", "POST", "/api/auth/login", 401,
      body={"email": "designer@demo.agroup", "password": "wrong"})
check("Demo designer logs in", "POST", "/api/auth/login", 200,
      body={"email": "designer@demo.agroup", "password": "demo"}, contains='"DESIGNER"')
check("Session knows the designer", "GET", "/api/auth/me", 200, contains="user-form-field")
check("Designer reads own company", "GET", "/api/company", 200, contains="Form & Field")
check("Designer reads statistics (ID-13)", "GET", "/api/statistics", 200)
check("Designer logs out", "POST", "/api/auth/logout", 200)
check("Session ended after logout", "GET", "/api/auth/me", 401)

failed = [r for r in results if not r[0]]
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as out:
        out.write(f"### Smoke test against staging ({len(results) - len(failed)}/{len(results)} passed)\n\n")
        out.write("| Result | Check | Request | Status |\n|---|---|---|---|\n")
        for ok, name, req, status in results:
            out.write(f"| {'✅' if ok else '❌'} | {name} | `{req}` | {status} |\n")
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
