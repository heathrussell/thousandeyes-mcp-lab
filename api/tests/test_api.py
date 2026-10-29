"""Offline checks for the whole API: scoreboard routes plus onboarding and proctor routes.

Runs with the standard library and boto3 only (boto3 is imported by the app, never called: DynamoDB and SSM are stubbed).
ThousandEyes is replaced by a small local HTTP server that speaks the same shapes as the v7 Administrative API,
so the real HTTP client, request bodies, bearer header and problem+json error handling are all exercised.

    python3 api/tests/test_api.py          (from the repo root; needs api/answers.json or ANSWERS_B64)
"""
import base64
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fakes import GOOD_TOKEN, FakeTE, setup_env, start_fake_te, wire  # noqa: E402

server = start_fake_te()
setup_env(server.server_address[1])
answers_file = os.path.join(ROOT, "answers.json")
if not os.environ.get("ANSWERS_B64") and os.path.exists(answers_file):
    os.environ["ANSWERS_B64"] = base64.b64encode(open(answers_file, "rb").read()).decode()

import app  # noqa: E402
import onboarding  # noqa: E402

wire(app, onboarding)

PROCTOR = {"x-proctor-key": "proctor-secret-123"}


def call(method, path, body=None, qs=None, headers=None):
    event = {"requestContext": {"http": {"method": method}}, "rawPath": path, "body": json.dumps(body) if body is not None else None,
             "queryStringParameters": qs, "headers": {"Content-Type": "application/json", **(headers or {})}}
    r = app.handler(event, None)
    return r["statusCode"], json.loads(r["body"])


def check(label, cond, extra=""):
    if not cond:
        print("FAIL", label, extra)
        sys.exit(1)
    print("ok  ", label)


# ── scoreboard routes ─────────────────────────────────────────────────

st, h = call("GET", "/health")
check("health", st == 200 and h["status"] == "ready" and h["onboarding"] == "off" and h["proctor"] is True, h)
has_answers = h["answers"]
check("checkin", call("POST", "/checkin", {"name": "Smoke Test"})[1]["player"]["points"] == 0)
if has_answers:
    check("correct answer", call("POST", "/answer", {"name": "smoke test", "checkpoint": "cp1", "answer": "Five."})[1]["correct"] is True)
    check("leaderboard", call("GET", "/leaderboard")[1]["players"][0]["points"] == 100)
else:
    print("skip correct-answer check (no answers.json / ANSWERS_B64)")
check("wrong answer", call("POST", "/answer", {"name": "smoke test", "checkpoint": "cp2", "answer": "nope"})[1]["correct"] is False)
check("bad body", call("POST", "/checkin", ["not", "an", "object"])[0] == 400)
check("unknown route", call("GET", "/nothing")[0] == 404)
st, r = call("GET", "/discover")
check("discover needs a domain", st == 400, r)
st, r = call("GET", "/discover", qs={"domain": "not a domain"})
check("discover rejects junk", st == 400, r)

class FakeFinder:
    def __init__(s, payload):
        s._payload = json.dumps(payload).encode()
    def read(s):
        return s._payload
    def __enter__(s):
        return s
    def __exit__(s, *a):
        pass

def fake_finder(req, timeout=None):
    url = getattr(req, "full_url", req)
    assert "xb2md8toek.execute-api.us-east-1.amazonaws.com/prod/saas" in url
    assert "domain=cisco.com" in url and "extra=true" in url
    return FakeFinder({"saas": {"Office 365": True, "Webex": True, "Zoom": True, "Salesforce": True, "Servicenow": True}, "subdomains": ["www.cisco.com", "login.cisco.com"]})

_real_urlopen = app.urllib.request.urlopen
app.urllib.request.urlopen = fake_finder
st, r = call("GET", "/discover", qs={"domain": "https://cisco.com/foo"})
check("discover proxies finder JSON", st == 200 and r["domain"] == "cisco.com" and len(r["saas"]) == 5 and r["subdomains"] == ["www.cisco.com", "login.cisco.com"], r)
app.urllib.request.urlopen = _real_urlopen

# ── proctor gate ──────────────────────────────────────────────────────

check("proctor without key", call("GET", "/proctor/config")[0] == 401)
check("proctor wrong key", call("GET", "/proctor/config", headers={"x-proctor-key": "nope"})[0] == 401)
st, c = call("GET", "/proctor/config", headers=PROCTOR)
check("proctor config defaults", st == 200 and c["config"]["enabled"] is False and c["tokenSet"] is False and c["config"]["groupNameTemplate"] == "{name} ({email})", c)

# ── token and overview ────────────────────────────────────────────────

st, r = call("GET", "/proctor/te", headers=PROCTOR)
check("overview without token", st == 400, r)
st, r = call("POST", "/proctor/te", {"teToken": "bad-token"}, headers=PROCTOR)
check("probing a bad token is a clear 502 + hint, nothing saved", st == 502 and "rejected" in r["hint"] and not onboarding._ssm.params, r)
st, r = call("POST", "/proctor/te", {"teToken": GOOD_TOKEN}, headers=PROCTOR)
check("probing a good token returns the overview without saving", st == 200 and r["orgName"] == "AI Builders" and not onboarding._ssm.params, r)
st, r = call("PUT", "/proctor/config", {"teToken": GOOD_TOKEN, "orgName": "AI Builders"}, headers=PROCTOR)
check("token saved to SSM, never echoed", st == 200 and r["tokenSet"] is True and GOOD_TOKEN not in json.dumps(r) and onboarding._ssm.params["/te-lab/test/te-token"] == GOOD_TOKEN, r)
st, ov = call("GET", "/proctor/te", headers=PROCTOR)
check("overview", st == 200 and ov["orgName"] == "AI Builders" and ov["accountGroups"][0]["aid"] == "1001" and any(x["name"] == "Account Admin" for x in ov["roles"]) and ov["agents"][0]["agentId"] == "105", ov)
st, r = call("PUT", "/proctor/config", {"groupNameTemplate": "{nope}"}, headers=PROCTOR)
check("bad template rejected", st == 400, r)
st, r = call("PUT", "/proctor/config", {"maxOnboardings": "lots"}, headers=PROCTOR)
check("bad cap rejected", st == 400, r)

# ── onboarding ────────────────────────────────────────────────────────

check("onboarding closed", call("POST", "/onboard", {"name": "Ada Lovelace", "email": "ada@example.com"})[0] == 403)
st, r = call("PUT", "/proctor/config", {"enabled": True, "eventCode": "BUILD-2026", "ownRoleId": "57", "ownRoleName": "Account Admin",
                                        "sharedAid": "1001", "sharedAccountGroupName": "AI Builders Demo", "sharedRoleId": "1140", "sharedRoleName": "Regular User",
                                        "agentIds": ["105"], "maxOnboardings": 2, "welcomeNote": "Check your inbox."}, headers=PROCTOR)
check("config saved", st == 200 and r["config"]["enabled"] is True and r["config"]["agentIds"] == ["105"], r)
check("health says ready", call("GET", "/health")[1]["onboarding"] == "ready")
check("wrong event code", call("POST", "/onboard", {"name": "Ada Lovelace", "email": "ada@example.com", "eventCode": "nope"})[0] == 403)
check("bad email", call("POST", "/onboard", {"name": "Ada Lovelace", "email": "ada@", "eventCode": "build 2026"})[0] == 400)
check("bad name", call("POST", "/onboard", {"name": "A", "email": "ada@example.com", "eventCode": "build-2026"})[0] == 400)

FakeTE.calls.clear()
st, r = call("POST", "/onboard", {"name": "Ada Lovelace", "email": "Ada@Example.com", "company": "Analytical Engines", "eventCode": "build 2026"})
check("onboard new attendee", st == 200 and r["status"] == "ready" and r["record"]["status"] == "ready" and r["record"]["userStatus"] == "invited" and r["welcomeNote"] == "Check your inbox.", r)
group_call = next(c for c in FakeTE.calls if c[0] == "POST" and c[1] == "/v7/account-groups")
check("account group body", group_call[2] == {"accountGroupName": "Ada Lovelace (ada@example.com)", "agents": ["105"]}, group_call)
user_call = next(c for c in FakeTE.calls if c[0] == "POST" and c[1] == "/v7/users")
aid = r["record"]["aid"]
check("user body: own group as Account Admin, login group = own group, shared group as Regular User",
      user_call[2] == {"name": "Ada Lovelace", "email": "ada@example.com", "loginAccountGroupId": aid,
                       "accountGroupRoles": [{"accountGroupId": aid, "roleIds": ["57"]}, {"accountGroupId": "1001", "roleIds": ["1140"]}],
                       "allAccountGroupRoleIds": []}, user_call)
check("lookup before create", [c[:2] for c in FakeTE.calls].index(("GET", "/v7/users")) < [c[:2] for c in FakeTE.calls].index(("POST", "/v7/users")))

st, r = call("POST", "/onboard", {"name": "Ada Lovelace", "email": "ada@example.com", "eventCode": "build-2026"})
check("second submit is idempotent", st == 200 and r["status"] == "already" and len([c for c in FakeTE.calls if c[1] == "/v7/account-groups" and c[0] == "POST"]) == 1, r)
st, r = call("GET", "/onboard", qs={"email": "ADA@example.com"})
check("status lookup", st == 200 and r["status"] == "ready" and r["record"]["aid"] == aid, r)

FakeTE.calls.clear()
st, r = call("POST", "/onboard", {"name": "Existing Person", "email": "existing@example.com", "eventCode": "build-2026"})
check("existing TE user gets merged roles, not a duplicate", st == 200 and r["record"]["userStatus"] == "added-to-existing" and r["record"]["uid"] == "77", r)
put_call = next(c for c in FakeTE.calls if c[0] == "PUT")
own_aid = r["record"]["aid"]
check("PUT keeps the old membership and login group, adds the new group",
      put_call[2]["loginAccountGroupId"] == "1001" and {"accountGroupId": "1001", "roleIds": ["1140"]} in put_call[2]["accountGroupRoles"]
      and {"accountGroupId": own_aid, "roleIds": ["57"]} in put_call[2]["accountGroupRoles"], put_call)
check("no POST /users for an existing user", not any(c[0] == "POST" and c[1] == "/v7/users" for c in FakeTE.calls))

st, r = call("POST", "/onboard", {"name": "Third Person", "email": "third@example.com", "eventCode": "build-2026"})
check("cap enforced", st == 429, r)
check("health tells the page a code is needed", call("GET", "/health")[1]["onboardingNeedsCode"] is True)
check("bad event end time rejected", call("PUT", "/proctor/config", {"eventEndsAt": "tomorrow 4pm"}, headers=PROCTOR)[0] == 400)
st, r = call("PUT", "/proctor/config", {"eventEndsAt": "2026-11-11T16:30:00+11:00"}, headers=PROCTOR)
check("event end time saved and on /health", st == 200 and call("GET", "/health")[1]["eventEndsAt"] == "2026-11-11T16:30:00+11:00", r)
st, r = call("POST", "/proctor/onboard", {"name": "Walk Up", "email": "walkup@example.com", "company": "Cisco"}, headers=PROCTOR)
check("proctor manual onboarding skips the cap and the code", st == 200 and r["record"]["status"] == "ready", r)
call("DELETE", "/proctor/onboarded", qs={"email": "walkup@example.com"}, headers=PROCTOR)

st, r = call("PUT", "/proctor/config", {"maxOnboardings": 0}, headers=PROCTOR)
FakeTE.fail_group_create = (403, "Insufficient permissions to create account groups")
st, r = call("POST", "/onboard", {"name": "Grace Hopper", "email": "grace@example.com", "eventCode": "build-2026"})
check("TE failure reported honestly", st == 502 and r["record"]["status"] == "failed" and "403" in r["detail"] and "Insufficient" in r["detail"], r)
FakeTE.fail_group_create = None
st, r = call("POST", "/proctor/retry", {"email": "grace@example.com"}, headers=PROCTOR)
check("proctor retry succeeds once TE cooperates", st == 200 and r["record"]["status"] == "ready" and r["record"]["attempts"] == 2, r)

st, r = call("GET", "/proctor/onboarded", headers=PROCTOR)
check("onboarded list", st == 200 and {x["email"] for x in r["records"]} == {"ada@example.com", "existing@example.com", "grace@example.com"}, r)
st, r = call("DELETE", "/proctor/onboarded", qs={"email": "grace@example.com"}, headers=PROCTOR)
check("delete record", st == 200 and call("GET", "/onboard", qs={"email": "grace@example.com"})[0] == 404, r)

st, r = call("PUT", "/proctor/config", {"clearToken": True}, headers=PROCTOR)
check("token cleared", st == 200 and r["tokenSet"] is False and call("GET", "/health")[1]["onboarding"] == "unconfigured", r)
st, r = call("POST", "/onboard", {"name": "Late Comer", "email": "late@example.com", "eventCode": "build-2026"})
check("unconfigured onboarding says so", st == 503, r)

# Secrets must never leak through any response.
leak = [GOOD_TOKEN, "proctor-secret-123"]
for m, p in (("GET", "/health"), ("GET", "/proctor/config"), ("GET", "/proctor/onboarded")):
    body = json.dumps(call(m, p, headers=PROCTOR)[1])
    check(f"no secret in {p}", not any(s in body for s in leak))

server.shutdown()
print("\nall API checks passed")
