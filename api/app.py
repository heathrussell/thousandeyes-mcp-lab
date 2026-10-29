"""ThousandEyes MCP Lab: scoreboard API.

One Lambda behind an HTTP API. Routes:
  POST /checkin      {name}                       -> {player}
  POST /answer       {name, checkpoint, answer}   -> {correct, player}
  POST /hint         {name, checkpoint}           -> {hint, player}
  GET  /player?name= -> {player}
  GET  /leaderboard  -> {players: [{name, points, solvedCount, updatedAt}]}
  POST /ask          {question, snippets}         -> {answer}   (only when ANTHROPIC_API_KEY is set)

Scoring mirrors the page exactly: 100 points a checkpoint, three free tries, then -10 a wrong answer,
hints -25 (never charged twice, never charged after a solve), total never below 0.
Answers live in checkpoints.json next to this file and never reach the browser.
"""
import json
import os
import re
import time
import unicodedata
import urllib.request
from decimal import Decimal

import boto3

TABLE = os.environ.get("TABLE_NAME", "")
ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")

with open(os.path.join(os.path.dirname(__file__), "checkpoints.json"), encoding="utf-8") as fh:
    BANK = json.load(fh)
RULES = BANK["rules"]
CP = {c["id"]: c for c in BANK["checkpoints"]}

_ddb = boto3.resource("dynamodb")
_table = _ddb.Table(TABLE) if TABLE else None

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{1,23}$")


def canon(s: str) -> str:
    """Identical to the page's canon(): lower, NFKC, drop quotes, trim, strip trailing punctuation, drop spaces/_/-."""
    s = unicodedata.normalize("NFKC", str(s or "").lower())
    s = re.sub(r"[`\"'“”‘’]", "", s).strip()
    s = re.sub(r"[.!?]+$", "", s)
    return re.sub(r"[\s_-]+", "", s)


def clean_name(n: str) -> str:
    n = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(n or ""))).strip()
    return n if NAME_RE.match(n) else ""


def now_ms() -> int:
    return int(time.time() * 1000)


def plain(o):
    """Decimal -> int/float for JSON."""
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
            "Access-Control-Allow-Headers": "content-type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(plain(body), ensure_ascii=False),
    }


def public(item):
    return {
        "name": item["name"],
        "points": int(item.get("points", 0)),
        "solved": item.get("solved", {}) or {},
        "tries": item.get("tries", {}) or {},
        "hints": item.get("hints", {}) or {},
        "createdAt": int(item.get("createdAt", 0)),
        "updatedAt": int(item.get("updatedAt", 0)),
    }


def load(name):
    r = _table.get_item(Key={"key": name.lower()})
    return r.get("Item")


def store(item):
    item["updatedAt"] = now_ms()
    _table.put_item(Item=item)
    return item


def fresh(name):
    t = now_ms()
    return {"key": name.lower(), "name": name, "points": 0, "solved": {}, "tries": {}, "hints": {}, "createdAt": t, "updatedAt": t, "lastSolveAt": 0}


# ── routes ──────────────────────────────────────────────────────────────

def r_checkin(body):
    name = clean_name(body.get("name"))
    if not name:
        return respond(400, {"error": "Pick a handle of 2 to 24 characters: letters, numbers, spaces, dots or dashes."})
    item = load(name) or store(fresh(name))
    return respond(200, {"player": public(item)})


def r_player(qs):
    name = clean_name(qs.get("name", ""))
    item = load(name) if name else None
    if not item:
        return respond(404, {"error": "No such player."})
    return respond(200, {"player": public(item)})


def r_answer(body):
    name = clean_name(body.get("name"))
    cp = CP.get(str(body.get("checkpoint", "")))
    if not name or not cp:
        return respond(400, {"error": "Check in first, and name a real checkpoint."})
    item = load(name)
    if not item:
        return respond(404, {"error": "No such player. Check in again."})
    cid = cp["id"]
    if cid in (item.get("solved") or {}):
        return respond(200, {"correct": True, "already": True, "player": public(item)})
    given = canon(body.get("answer", ""))
    correct = bool(given) and any(given == canon(a) for a in cp["answers"])
    tries = item.setdefault("tries", {})
    tries[cid] = int(tries.get(cid, 0)) + 1
    if correct:
        item.setdefault("solved", {})[cid] = {"at": now_ms()}
        item["points"] = int(item.get("points", 0)) + int(cp["points"])
        item["lastSolveAt"] = now_ms()
    elif tries[cid] > int(RULES["freeTries"]):
        item["points"] = max(0, int(item.get("points", 0)) - int(RULES["wrongAnswerPenalty"]))
    store(item)
    return respond(200, {"correct": correct, "player": public(item)})


def r_hint(body):
    name = clean_name(body.get("name"))
    cp = CP.get(str(body.get("checkpoint", "")))
    if not name or not cp:
        return respond(400, {"error": "Check in first, and name a real checkpoint."})
    item = load(name)
    if not item:
        return respond(404, {"error": "No such player. Check in again."})
    cid = cp["id"]
    hints = item.setdefault("hints", {})
    if not hints.get(cid):
        hints[cid] = True
        if cid not in (item.get("solved") or {}):
            item["points"] = max(0, int(item.get("points", 0)) - int(RULES["hintCost"]))
        store(item)
    return respond(200, {"hint": cp["hint"], "player": public(item)})


def r_leaderboard():
    items, start = [], None
    while True:
        kw = {"ProjectionExpression": "#n, points, solved, updatedAt, lastSolveAt", "ExpressionAttributeNames": {"#n": "name"}}
        if start:
            kw["ExclusiveStartKey"] = start
        page = _table.scan(**kw)
        items.extend(page.get("Items", []))
        start = page.get("LastEvaluatedKey")
        if not start:
            break
    rows = [{"name": i["name"], "points": int(i.get("points", 0)), "solvedCount": len(i.get("solved") or {}), "updatedAt": int(i.get("updatedAt", 0)), "lastSolveAt": int(i.get("lastSolveAt", 0) or 0)} for i in items]
    rows.sort(key=lambda r: (-r["points"], -r["solvedCount"], r["lastSolveAt"] or 9e15, r["name"].lower()))
    return respond(200, {"players": rows[:100], "total": len(rows)})


def r_ask(body):
    if not ANTHROPIC_API_KEY:
        return respond(404, {"error": "ask is not enabled on this deployment"})
    q = str(body.get("question", ""))[:500].strip()
    snippets = body.get("snippets") or []
    if not q:
        return respond(400, {"error": "Ask something."})
    ctx = "\n\n".join(f"[{s.get('route', '')}] {s.get('title', '')}\n{str(s.get('text', ''))[:900]}" for s in snippets[:5] if isinstance(s, dict))
    prompt = ("You are the front desk for a hands-on ThousandEyes MCP lab. Answer the attendee's question in at most four short sentences, "
              "using only the lab guide excerpts below. If the excerpts do not cover it, say so and name the page most likely to help. "
              "Plain language, no bullet lists, no em dashes.\n\nQuestion: " + q + "\n\nGuide excerpts:\n" + ctx)
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({"model": ANTHROPIC_MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]}).encode("utf-8"),
        headers={"content-type": "application/json", "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        return respond(200, {"answer": text})
    except Exception as exc:  # noqa: BLE001
        return respond(502, {"error": f"The front desk is unavailable: {exc.__class__.__name__}"})


def handler(event, _context):
    rc = event.get("requestContext", {}).get("http", {})
    method = rc.get("method", "GET").upper()
    path = (event.get("rawPath") or "/").rstrip("/") or "/"
    if method == "OPTIONS":
        return respond(204, {})
    try:
        body = json.loads(event.get("body") or "{}") if method == "POST" else {}
    except json.JSONDecodeError:
        return respond(400, {"error": "Body must be JSON."})
    qs = event.get("queryStringParameters") or {}
    try:
        if method == "POST" and path == "/checkin":
            return r_checkin(body)
        if method == "POST" and path == "/answer":
            return r_answer(body)
        if method == "POST" and path == "/hint":
            return r_hint(body)
        if method == "POST" and path == "/ask":
            return r_ask(body)
        if method == "GET" and path == "/player":
            return r_player(qs)
        if method == "GET" and path == "/leaderboard":
            return r_leaderboard()
        if method == "GET" and path in ("/", "/health"):
            return respond(200, {"status": "ready", "checkpoints": len(CP), "ask": bool(ANTHROPIC_API_KEY)})
    except Exception as exc:  # noqa: BLE001
        print("error", repr(exc))
        return respond(500, {"error": "Something broke on our side. Try again."})
    return respond(404, {"error": "No such route."})
