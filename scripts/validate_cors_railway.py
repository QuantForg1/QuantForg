import json
import urllib.error
import urllib.request

API = "https://quantforg-production.up.railway.app"
ORIGIN = "http://localhost:3000"
PREFIX = f"{API}/api/v1"

paths = [
    ("OPTIONS", f"{PREFIX}/auth/login"),
    ("OPTIONS", f"{PREFIX}/auth/me"),
    ("OPTIONS", f"{PREFIX}/mt5/status"),
    ("OPTIONS", f"{PREFIX}/weltrade/health"),
    ("POST", f"{PREFIX}/auth/login"),
    ("GET", f"{PREFIX}/auth/me"),
    ("GET", f"{PREFIX}/mt5/status"),
    ("GET", f"{PREFIX}/weltrade/health"),
]


def request(method: str, url: str) -> dict:
    headers = {
        "Origin": ORIGIN,
        "Accept": "application/json",
    }
    data = None
    if method == "OPTIONS":
        headers.update(
            {
                "Access-Control-Request-Method": "POST" if "login" in url else "GET",
                "Access-Control-Request-Headers": "authorization,content-type,x-request-id,accept",
            }
        )
    elif method == "POST":
        headers["Content-Type"] = "application/json"
        data = json.dumps(
            {"email": "cors-gate@example.com", "password": "invalid-for-cors-check"}
        ).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read(400).decode("utf-8", "replace")
            return {
                "method": method,
                "url": url,
                "status": res.status,
                "acao": res.headers.get("Access-Control-Allow-Origin"),
                "acac": res.headers.get("Access-Control-Allow-Credentials"),
                "acam": res.headers.get("Access-Control-Allow-Methods"),
                "acah": res.headers.get("Access-Control-Allow-Headers"),
                "vary": res.headers.get("Vary"),
                "body": body[:200],
            }
    except urllib.error.HTTPError as e:
        return {
            "method": method,
            "url": url,
            "status": e.code,
            "acao": e.headers.get("Access-Control-Allow-Origin") if e.headers else None,
            "acac": e.headers.get("Access-Control-Allow-Credentials") if e.headers else None,
            "acam": e.headers.get("Access-Control-Allow-Methods") if e.headers else None,
            "acah": e.headers.get("Access-Control-Allow-Headers") if e.headers else None,
            "vary": e.headers.get("Vary") if e.headers else None,
            "body": e.read(200).decode("utf-8", "replace"),
        }
    except Exception as e:
        return {"method": method, "url": url, "status": 0, "error": str(e)}


results = [request(m, u) for m, u in paths]
print(json.dumps(results, indent=2))

ok_preflight = all(
    r.get("status") == 200 and r.get("acao") == ORIGIN
    for r in results
    if r["method"] == "OPTIONS"
)
# Auth endpoints may 401/422 but must include ACAO
ok_auth_cors = all(
    r.get("acao") == ORIGIN and r.get("status") not in (0,)
    for r in results
    if r["method"] != "OPTIONS"
)
print(
    json.dumps(
        {
            "preflight_ok": ok_preflight,
            "authenticated_routes_cors_headers_ok": ok_auth_cors,
            "blocker3_cleared": ok_preflight and ok_auth_cors,
        },
        indent=2,
    )
)
