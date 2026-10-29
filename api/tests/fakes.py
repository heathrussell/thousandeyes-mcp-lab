"""Test doubles shared by test_api.py and devserver.py: a fake ThousandEyes v7 API, and in-memory DynamoDB / SSM stubs.

Nothing here talks to AWS or to ThousandEyes. Import `setup_env(te_port)` BEFORE importing app/onboarding (they read
their environment at import time), then `wire(app, onboarding)` to swap the real clients for the stubs.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

GOOD_TOKEN = "good-token"


class FakeTE(BaseHTTPRequestHandler):
    """Speaks the shapes of https://developer.cisco.com/docs/thousandeyes/administrative-api (the parts we use)."""
    calls = []
    users = {}
    groups = {}
    next_id = 5000
    fail_group_create = None   # None or (status, message) to simulate a permissions problem

    def log_message(self, *_):
        pass

    def _send(self, status, body, problem=False):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/problem+json" if problem else "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode()) if n else None

    def _route(self, method):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        body = self._body()
        FakeTE.calls.append((method, u.path, body))
        if self.headers.get("Authorization") != "Bearer " + GOOD_TOKEN:
            return self._send(401, {"timestamp": "now", "status": 401, "error": "Unauthorized", "errorMessage": "Invalid or missing bearer token"}, problem=True)
        if method == "GET" and u.path == "/v7/account-groups":
            return self._send(200, {"accountGroups": list(FakeTE.groups.values())})
        if method == "GET" and u.path == "/v7/roles":
            return self._send(200, {"roles": [
                {"roleId": "57", "name": "Account Admin", "isBuiltin": True, "hasManagementPermissions": True},
                {"roleId": "1140", "name": "Regular User", "isBuiltin": True, "hasManagementPermissions": False},
                {"roleId": "58", "name": "Organization Admin", "isBuiltin": True, "hasManagementPermissions": True}]})
        if method == "GET" and u.path == "/v7/agents":
            assert qs.get("agentTypes") == ["enterprise"], qs
            return self._send(200, {"agents": [
                {"agentId": "105", "agentName": "Melbourne lab agent", "location": "Melbourne, Australia", "agentType": "enterprise"},
                {"agentId": "719", "agentName": "Sydney office", "location": "Sydney, Australia", "agentType": "enterprise"}]})
        if method == "POST" and u.path == "/v7/account-groups":
            if FakeTE.fail_group_create:
                st, msg = FakeTE.fail_group_create
                return self._send(st, {"timestamp": "now", "status": st, "error": msg, "errors": [{"code": "FORBIDDEN", "field": "", "message": msg}]}, problem=True)
            FakeTE.next_id += 1
            aid = str(FakeTE.next_id)
            FakeTE.groups[aid] = {"aid": aid, "accountGroupName": body["accountGroupName"], "organizationName": "AI Builders", "isDefaultAccountGroup": False, "agents": body.get("agents", [])}
            return self._send(201, FakeTE.groups[aid])
        if method == "GET" and u.path == "/v7/users":
            return self._send(200, {"users": [{"uid": x["uid"], "name": x["name"], "email": x["email"]} for x in FakeTE.users.values()]})
        if method == "GET" and u.path.startswith("/v7/users/"):
            x = FakeTE.users.get(u.path.rsplit("/", 1)[1])
            return self._send(200, x) if x else self._send(404, {"errors": [{"code": "NOT_FOUND", "message": "no such user"}]}, problem=True)
        if method == "POST" and u.path == "/v7/users":
            if any(x["email"].lower() == body["email"].lower() for x in FakeTE.users.values()):
                return self._send(400, {"timestamp": "now", "status": 400, "error": "Bad Request", "errors": [{"code": "DUPLICATE", "field": "email", "message": "User with this email already exists"}]}, problem=True)
            FakeTE.next_id += 1
            uid = str(FakeTE.next_id)
            FakeTE.users[uid] = {
                "uid": uid, "name": body["name"], "email": body["email"],
                "loginAccountGroup": {"aid": body["loginAccountGroupId"]},
                "accountGroupRoles": [{"accountGroup": {"aid": r["accountGroupId"]}, "roles": [{"roleId": rid} for rid in r["roleIds"]]} for r in body["accountGroupRoles"]],
                "allAccountGroupRoles": [{"roleId": rid} for rid in body.get("allAccountGroupRoleIds", [])],
            }
            return self._send(201, FakeTE.users[uid])
        if method == "PUT" and u.path.startswith("/v7/users/"):
            uid = u.path.rsplit("/", 1)[1]
            x = FakeTE.users[uid]
            x["loginAccountGroup"] = {"aid": body["loginAccountGroupId"]}
            x["accountGroupRoles"] = [{"accountGroup": {"aid": r["accountGroupId"]}, "roles": [{"roleId": rid} for rid in r["roleIds"]]} for r in body["accountGroupRoles"]]
            return self._send(200, x)
        return self._send(404, {"errors": [{"code": "NOT_FOUND", "message": "no route"}]}, problem=True)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")


def start_fake_te():
    server = HTTPServer(("127.0.0.1", 0), FakeTE)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    FakeTE.groups["1001"] = {"aid": "1001", "accountGroupName": "AI Builders Demo", "organizationName": "AI Builders", "isDefaultAccountGroup": True}
    FakeTE.users["77"] = {"uid": "77", "name": "Existing Person", "email": "existing@example.com", "loginAccountGroup": {"aid": "1001"},
                          "accountGroupRoles": [{"accountGroup": {"aid": "1001"}, "roles": [{"roleId": "1140"}]}], "allAccountGroupRoles": []}
    return server


class StubTable:
    def __init__(self, key):
        self.key, self.items = key, {}

    def get_item(self, Key):
        i = self.items.get(Key[self.key])
        return {"Item": json.loads(json.dumps(i))} if i else {}

    def put_item(self, Item):
        self.items[Item[self.key]] = json.loads(json.dumps(Item))

    def delete_item(self, Key):
        self.items.pop(Key[self.key], None)

    def scan(self, **kw):
        return {"Items": [json.loads(json.dumps(i)) for i in self.items.values()]}


class StubSSM:
    class exceptions:
        class ParameterNotFound(Exception):
            pass

    def __init__(self):
        self.params = {}

    def get_parameter(self, Name, WithDecryption=False):
        if Name not in self.params:
            raise StubSSM.exceptions.ParameterNotFound()
        return {"Parameter": {"Value": self.params[Name]}}

    def put_parameter(self, Name, Value, Type, Overwrite):
        assert Type == "SecureString"
        self.params[Name] = Value

    def delete_parameter(self, Name):
        if Name not in self.params:
            raise StubSSM.exceptions.ParameterNotFound()
        del self.params[Name]


def setup_env(te_port, proctor_key="proctor-secret-123"):
    os.environ.update({
        "AWS_DEFAULT_REGION": "ap-southeast-2", "TABLE_NAME": "players", "CONFIG_TABLE": "config", "ONBOARD_TABLE": "onboard",
        "PROCTOR_KEY": proctor_key, "TE_TOKEN_PARAM": "/te-lab/test/te-token", "TE_API_BASE": f"http://127.0.0.1:{te_port}/v7",
    })


def wire(app, onboarding):
    app._table = StubTable("key")
    onboarding._config = StubTable("id")
    onboarding._onboard = StubTable("email")
    onboarding._ssm = StubSSM()
