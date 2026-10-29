"""Attendee onboarding for the ThousandEyes MCP Lab.

A web form on the site posts {name, email, company, eventCode} to POST /onboard. This module then, with the
proctor's ThousandEyes credential, creates one account group per attendee under the lab's ThousandEyes
organisation (POST /v7/account-groups), optionally shares Enterprise Agents into it, and creates the attendee as a
user (POST /v7/users) with the proctor-chosen role in their own group plus, optionally, a role in a shared demo
account group that already holds live tests and alert history. ThousandEyes then emails the attendee.

Where things live:
  DynamoDB Config table   item id="onboarding": everything the proctor sets except the credential
  DynamoDB Onboard table  one item per attendee email: status, account group, user id, errors
  SSM Parameter Store     SecureString TE_TOKEN_PARAM: the ThousandEyes token (never in DynamoDB, never in git)

Proctor routes require the X-Proctor-Key header to equal the PROCTOR_KEY stack parameter (NoEcho).
The ThousandEyes credential needs "Edit all account groups" (Organization Admin) and user management rights.
Docs: https://developer.cisco.com/docs/thousandeyes/create-account-group and
      https://developer.cisco.com/docs/thousandeyes/create-user
"""
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

import boto3

CONFIG_TABLE = os.environ.get("CONFIG_TABLE", "")
ONBOARD_TABLE = os.environ.get("ONBOARD_TABLE", "")
PROCTOR_KEY = os.environ.get("PROCTOR_KEY", "")
TE_TOKEN_PARAM = os.environ.get("TE_TOKEN_PARAM", "")
TE_API = os.environ.get("TE_API_BASE", "https://api.thousandeyes.com/v7").rstrip("/")
ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")

_ddb = boto3.resource("dynamodb")
_config = _ddb.Table(CONFIG_TABLE) if CONFIG_TABLE else None
_onboard = _ddb.Table(ONBOARD_TABLE) if ONBOARD_TABLE else None
_ssm = boto3.client("ssm")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-']+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
CONFIG_ID = "onboarding"
DEFAULT_CONFIG = {
    "id": CONFIG_ID,
    "enabled": False,
    "eventCode": "",
    "groupNameTemplate": "{name} ({email})",
    "ownRoleId": "",
    "ownRoleName": "",
    "sharedAid": "",
    "sharedAccountGroupName": "",
    "sharedRoleId": "",
    "sharedRoleName": "",
    "agentIds": [],
    "maxOnboardings": 60,
    "welcomeNote": "",
    "orgName": "",
    "eventEndsAt": "",
    "updatedAt": 0,
}
EDITABLE = ("enabled", "eventCode", "groupNameTemplate", "ownRoleId", "ownRoleName", "sharedAid", "sharedAccountGroupName",
            "sharedRoleId", "sharedRoleName", "agentIds", "maxOnboardings", "welcomeNote", "orgName", "eventEndsAt")


# ── small helpers ────────────────────────────────────────────────────────

def now_ms() -> int:
    return int(time.time() * 1000)


def plain(o):
    if isinstance(o, list):
        return [plain(x) for x in o]
    if isinstance(o, dict):
        return {k: plain(v) for k, v in o.items()}
    if isinstance(o, Decimal):
        return int(o) if o == int(o) else float(o)
    return o


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": ORIGIN,
            "Access-Control-Allow-Headers": "content-type,x-proctor-key",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(plain(body), ensure_ascii=False),
    }


def norm_code(s: str) -> str:
    return re.sub(r"[\s\-_]+", "", str(s or "").strip().lower())


def clean_person(name: str) -> str:
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    return name if 2 <= len(name) <= 60 and not re.search(r"[<>{}\[\]\\]", name) else ""


def clean_email(email: str) -> str:
    email = str(email or "").strip().lower()
    return email if EMAIL_RE.match(email) and len(email) <= 120 else ""


# ── storage ──────────────────────────────────────────────────────────────

def get_config() -> dict:
    item = {}
    if _config is not None:
        item = _config.get_item(Key={"id": CONFIG_ID}).get("Item") or {}
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(plain(item))
    cfg["agentIds"] = [str(a) for a in (cfg.get("agentIds") or [])]
    cfg["maxOnboardings"] = int(cfg.get("maxOnboardings") or 0)
    return cfg


def save_config(patch: dict) -> dict:
    cfg = get_config()
    for key in EDITABLE:
        if key not in patch:
            continue
        val = patch[key]
        if key == "enabled":
            val = bool(val)
        elif key == "agentIds":
            val = [str(a) for a in (val or []) if str(a).strip()]
        elif key == "maxOnboardings":
            try:
                val = max(0, min(5000, int(val or 0)))
            except (TypeError, ValueError):
                raise ValueError("maxOnboardings must be a whole number (0 means no cap)") from None
        elif key == "eventEndsAt":
            val = str(val or "").strip()
            if val and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})$", val):
                raise ValueError("eventEndsAt must be an ISO 8601 time with offset, e.g. 2026-11-11T16:30:00+11:00, or blank")
        elif key == "groupNameTemplate":
            val = str(val or "").strip() or DEFAULT_CONFIG["groupNameTemplate"]
            try:
                val.format(name="Ada Lovelace", email="ada@example.com", company="Example")
            except (KeyError, IndexError, ValueError):
                raise ValueError("groupNameTemplate may only use {name}, {email} and {company}") from None
        else:
            val = str(val or "").strip()
        cfg[key] = val
    cfg["updatedAt"] = now_ms()
    cfg["id"] = CONFIG_ID
    _config.put_item(Item=cfg)
    return cfg


def token_get() -> str:
    if not TE_TOKEN_PARAM:
        return ""
    try:
        return _ssm.get_parameter(Name=TE_TOKEN_PARAM, WithDecryption=True)["Parameter"]["Value"]
    except _ssm.exceptions.ParameterNotFound:
        return ""


def token_set(value: str) -> None:
    _ssm.put_parameter(Name=TE_TOKEN_PARAM, Value=value, Type="SecureString", Overwrite=True)


def token_clear() -> None:
    try:
        _ssm.delete_parameter(Name=TE_TOKEN_PARAM)
    except _ssm.exceptions.ParameterNotFound:
        pass


def record_get(email: str):
    item = _onboard.get_item(Key={"email": email}).get("Item")
    return plain(item) if item else None


def record_put(rec: dict) -> dict:
    rec["updatedAt"] = now_ms()
    _onboard.put_item(Item=rec)
    return rec


def record_all() -> list:
    items, start = [], None
    while True:
        kw = {}
        if start:
            kw["ExclusiveStartKey"] = start
        page = _onboard.scan(**kw)
        items.extend(page.get("Items", []))
        start = page.get("LastEvaluatedKey")
        if not start:
            break
    rows = [plain(i) for i in items]
    rows.sort(key=lambda r: -int(r.get("createdAt", 0) or 0))
    return rows


def public_record(rec: dict) -> dict:
    keys = ("email", "name", "company", "status", "accountGroupName", "aid", "uid", "userStatus", "error", "createdAt", "readyAt", "attempts")
    return {k: rec.get(k) for k in keys if k in rec}


# ── ThousandEyes API client ──────────────────────────────────────────────

class TeError(Exception):
    def __init__(self, status: int, message: str, errors=None):
        super().__init__(message)
        self.status, self.message, self.errors = status, message, errors or []


def te(method: str, path: str, token: str, body=None, query: dict | None = None):
    url = TE_API + path
    if query:
        url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v not in (None, "")})
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json", "User-Agent": "te-lab-onboarding/1.0"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    for attempt in (1, 2):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            if exc.code == 429 and attempt == 1:
                time.sleep(min(5, int(exc.headers.get("Retry-After", "2") or 2)))
                continue
            try:
                prob = json.loads(raw)
            except json.JSONDecodeError:
                prob = {}
            errors = prob.get("errors") or []
            detail = "; ".join(f"{e.get('field', '')}: {e.get('message', '')}".strip(": ") for e in errors if isinstance(e, dict))
            message = prob.get("title") or prob.get("message") or prob.get("errorMessage") or raw[:200] or f"HTTP {exc.code}"
            raise TeError(exc.code, (message + (" (" + detail + ")" if detail else ""))[:400], errors) from None
        except urllib.error.URLError as exc:
            raise TeError(0, f"could not reach ThousandEyes: {exc.reason}") from None
    raise TeError(429, "ThousandEyes rate limit; try again in a minute")


def te_overview(token: str) -> dict:
    groups = te("GET", "/account-groups", token).get("accountGroups") or []
    roles = te("GET", "/roles", token).get("roles") or []
    try:
        agents = te("GET", "/agents", token, query={"agentTypes": "enterprise"}).get("agents") or []
    except TeError as exc:
        agents = []
        agents_error = exc.message
    else:
        agents_error = ""
    org = next((g.get("organizationName") for g in groups if g.get("organizationName")), "")
    return {
        "orgName": org or "",
        "accountGroups": [{"aid": str(g.get("aid")), "name": g.get("accountGroupName", ""), "isDefault": bool(g.get("isDefaultAccountGroup"))} for g in groups],
        "roles": [{"roleId": str(r.get("roleId")), "name": r.get("name", ""), "isBuiltin": bool(r.get("isBuiltin")), "hasManagementPermissions": bool(r.get("hasManagementPermissions"))} for r in roles],
        "agents": [{"agentId": str(a.get("agentId")), "name": a.get("agentName", ""), "location": a.get("location", ""), "type": a.get("agentType", "")} for a in agents],
        "agentsError": agents_error,
    }


def find_user(token: str, email: str):
    users = te("GET", "/users", token).get("users") or []
    for u in users:
        if str(u.get("email", "")).lower() == email:
            return u
    return None


def add_groups_to_existing_user(token: str, uid: str, new_roles: list) -> dict:
    """PUT replaces accountGroupRoles wholesale, so merge the user's current memberships with the new ones."""
    u = te("GET", f"/users/{uid}", token)
    merged = {}
    for agr in u.get("accountGroupRoles") or []:
        gid = str((agr.get("accountGroup") or {}).get("aid", ""))
        if gid:
            merged[gid] = [str(r.get("roleId")) for r in (agr.get("roles") or []) if r.get("roleId") is not None]
    for nr in new_roles:
        merged.setdefault(nr["accountGroupId"], [])
        for rid in nr["roleIds"]:
            if rid not in merged[nr["accountGroupId"]]:
                merged[nr["accountGroupId"]].append(rid)
    body = {
        "name": u.get("name") or "",
        "email": u.get("email"),
        "loginAccountGroupId": str((u.get("loginAccountGroup") or {}).get("aid") or new_roles[0]["accountGroupId"]),
        "accountGroupRoles": [{"accountGroupId": gid, "roleIds": rids} for gid, rids in merged.items()],
        "allAccountGroupRoleIds": [str(r.get("roleId")) for r in (u.get("allAccountGroupRoles") or []) if r.get("roleId") is not None],
    }
    return te("PUT", f"/users/{uid}", token, body)


# ── the onboarding itself ────────────────────────────────────────────────

def onboard(name: str, email: str, company: str, event_code: str, by_proctor: bool = False):
    cfg = get_config()
    if not by_proctor:
        if not cfg["enabled"]:
            return respond(403, {"error": "Onboarding is closed right now. See a proctor for a login."})
        if cfg["eventCode"] and not hmac.compare_digest(norm_code(event_code), norm_code(cfg["eventCode"])):
            return respond(403, {"error": "That event code is not right. It is on the screen at the front of the room."})
    name, email = clean_person(name), clean_email(email)
    company = re.sub(r"\s+", " ", str(company or "")).strip()[:80]
    if not name or not email:
        return respond(400, {"error": "A real name (2 to 60 characters) and a valid email address, please."})
    existing = record_get(email)
    if existing and existing.get("status") == "ready" and not by_proctor:
        return respond(200, {"status": "already", "record": public_record(existing), "sharedAccountGroupName": cfg["sharedAccountGroupName"], "welcomeNote": cfg["welcomeNote"]})
    if existing and existing.get("status") == "pending" and now_ms() - int(existing.get("updatedAt", 0) or 0) < 60_000:
        return respond(409, {"error": "That email is being set up right now. Give it a minute, then check again.", "record": public_record(existing)})
    if not existing and not by_proctor and cfg["maxOnboardings"] and len(record_all()) >= cfg["maxOnboardings"]:
        return respond(429, {"error": "Onboarding is full for this event. See a proctor."})
    token = token_get()
    if not token or not cfg["ownRoleId"]:
        return respond(503, {"error": "Onboarding is not configured yet. See a proctor."})

    rec = existing or {"email": email, "createdAt": now_ms(), "attempts": 0}
    rec.update({"name": name, "company": company, "status": "pending", "error": "", "attempts": int(rec.get("attempts", 0)) + 1})
    record_put(rec)
    try:
        aid = str(rec.get("aid") or "")
        if not aid:
            group_name = cfg["groupNameTemplate"].format(name=name, email=email, company=company)[:100]
            created = te("POST", "/account-groups", token, {"accountGroupName": group_name, "agents": cfg["agentIds"]})
            aid = str(created.get("aid"))
            rec["aid"], rec["accountGroupName"] = aid, created.get("accountGroupName") or group_name
        roles = [{"accountGroupId": aid, "roleIds": [cfg["ownRoleId"]]}]
        if cfg["sharedAid"] and cfg["sharedRoleId"]:
            roles.append({"accountGroupId": cfg["sharedAid"], "roleIds": [cfg["sharedRoleId"]]})
        if not rec.get("uid"):
            # Someone from an earlier event, or a colleague of the proctor, may already be a user of this org.
            # PUT replaces a user's account group roles wholesale, so merge rather than create.
            found = find_user(token, email)
            if found:
                add_groups_to_existing_user(token, str(found.get("uid")), roles)
                rec["uid"], rec["userStatus"] = str(found.get("uid")), "added-to-existing"
            else:
                try:
                    created_user = te("POST", "/users", token, {"name": name, "email": email, "loginAccountGroupId": aid, "accountGroupRoles": roles, "allAccountGroupRoleIds": []})
                    rec["uid"], rec["userStatus"] = str(created_user.get("uid") or ""), "invited"
                except TeError as exc:
                    # Race or a user the list did not show: fall back to the lookup once more before giving up.
                    found = find_user(token, email) if exc.status in (400, 409) else None
                    if not found:
                        raise
                    add_groups_to_existing_user(token, str(found.get("uid")), roles)
                    rec["uid"], rec["userStatus"] = str(found.get("uid")), "added-to-existing"
        rec["status"], rec["readyAt"] = "ready", now_ms()
    except TeError as exc:
        rec["status"], rec["error"] = "failed", f"ThousandEyes answered {exc.status or 'no response'}: {exc.message}"
    except Exception as exc:  # noqa: BLE001
        rec["status"], rec["error"] = "failed", f"{exc.__class__.__name__}: {str(exc)[:200]}"
    record_put(rec)
    if rec["status"] != "ready":
        return respond(502, {"error": "ThousandEyes did not accept the request. A proctor can retry it from the proctor page.", "detail": rec["error"], "record": public_record(rec)})
    return respond(200, {"status": "ready", "record": public_record(rec), "sharedAccountGroupName": cfg["sharedAccountGroupName"], "welcomeNote": cfg["welcomeNote"]})


# ── routing ──────────────────────────────────────────────────────────────

def proctor_ok(headers: dict) -> bool:
    given = str((headers or {}).get("x-proctor-key") or "")
    return bool(PROCTOR_KEY) and hmac.compare_digest(given, PROCTOR_KEY)


def health_fields() -> dict:
    """What the page needs to decide whether to show the sign-up form: no secrets, no config values."""
    needs_code, ends_at = False, ""
    try:
        cfg = get_config()
        needs_code = bool(cfg["eventCode"])
        ends_at = str(cfg.get("eventEndsAt") or "")
        if not cfg["enabled"]:
            state = "off"
        elif not cfg["ownRoleId"] or not token_get():
            state = "unconfigured"
        else:
            state = "ready"
    except Exception:  # noqa: BLE001
        state = "error"
    return {"onboarding": state, "onboardingNeedsCode": needs_code, "proctor": bool(PROCTOR_KEY), "eventEndsAt": ends_at}


def handle(method: str, path: str, body: dict, qs: dict, headers: dict):
    """Returns a response dict for onboarding and proctor routes, or None when the path is not ours."""
    if _config is None or _onboard is None:
        if path.startswith("/onboard") or path.startswith("/proctor"):
            return respond(503, {"error": "Onboarding tables are not configured on this deployment."})
        return None

    if method == "POST" and path == "/onboard":
        return onboard(body.get("name"), body.get("email"), body.get("company", ""), body.get("eventCode", ""))
    if method == "GET" and path == "/onboard":
        email = clean_email(qs.get("email", ""))
        rec = record_get(email) if email else None
        if not rec:
            return respond(404, {"error": "No onboarding found for that email."})
        cfg = get_config()
        return respond(200, {"status": rec.get("status"), "record": public_record(rec), "sharedAccountGroupName": cfg["sharedAccountGroupName"], "welcomeNote": cfg["welcomeNote"]})

    if path.startswith("/proctor"):
        if not proctor_ok(headers):
            return respond(401, {"error": "Proctor key missing or wrong." if PROCTOR_KEY else "Proctor routes are disabled: the stack was deployed without a ProctorKey."})
        if method == "GET" and path == "/proctor/config":
            cfg = get_config()
            return respond(200, {"config": cfg, "tokenSet": bool(token_get()), "onboarded": len(record_all())})
        if method == "PUT" and path == "/proctor/config":
            try:
                cfg = save_config(body)
            except ValueError as exc:
                return respond(400, {"error": str(exc)})
            tok = str(body.get("teToken") or "").strip()
            if tok:
                token_set(tok)
            if body.get("clearToken"):
                token_clear()
            return respond(200, {"config": cfg, "tokenSet": bool(token_get())})
        if method in ("GET", "POST") and path == "/proctor/te":
            # GET tests the saved token; POST {teToken} tests a candidate without saving it (never put tokens in a URL).
            token = str(body.get("teToken") or "").strip() if method == "POST" else token_get()
            if not token:
                return respond(400, {"error": "No ThousandEyes token saved yet." if method == "GET" else "Paste a token to test."})
            try:
                return respond(200, te_overview(token))
            except TeError as exc:
                hint = {401: "The token was rejected. Paste a current User API Token from an Organization Admin of the lab org.",
                        403: "The token works but lacks permissions. It needs Edit all account groups and user management (Organization Admin)."}.get(exc.status, "")
                return respond(502, {"error": f"ThousandEyes answered {exc.status or 'no response'}: {exc.message}", "hint": hint})
        if method == "GET" and path == "/proctor/onboarded":
            return respond(200, {"records": [public_record(r) for r in record_all()]})
        if method == "POST" and path == "/proctor/retry":
            email = clean_email(body.get("email", ""))
            rec = record_get(email) if email else None
            if not rec:
                return respond(404, {"error": "No onboarding found for that email."})
            return onboard(rec.get("name") or body.get("name", ""), email, rec.get("company", ""), "", by_proctor=True)
        if method == "POST" and path == "/proctor/onboard":
            # A proctor adding someone by hand: ignores the enabled flag, the event code and the cap.
            return onboard(body.get("name"), body.get("email"), body.get("company", ""), "", by_proctor=True)
        if method == "DELETE" and path == "/proctor/onboarded":
            email = clean_email(qs.get("email", ""))
            if not email:
                return respond(400, {"error": "email required"})
            _onboard.delete_item(Key={"email": email})
            return respond(200, {"deleted": email, "note": "Only the lab's record was removed. The ThousandEyes account group and user, if created, still exist."})
        return respond(404, {"error": "No such proctor route."})
    return None
