import http.server
import socketserver
import webbrowser
import os
import sys
import json
import urllib.request
import urllib.error

PORT = 8000

os.chdir(os.path.dirname(os.path.abspath(__file__)))

url = f"http://localhost:{PORT}/"

print("=" * 50)
print("  경제 냠냠 블로그 스튜디오 서버")
print("=" * 50)
print(f"\n  주소: {url}")
print("\n  [Google Cloud Console 설정 필요]")
print(f"  승인된 자바스크립트 원본: http://localhost:{PORT}")
print(f"  승인된 리디렉션 URI:      {url}")
print("\n  Claude(칩섭)는 이 서버 프록시(/api/claude)로 호출됩니다.")
print("  종료: Ctrl+C")
print("=" * 50)

try:
    webbrowser.open(url)
except Exception:
    pass


def _send_json(handler, status, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 로그 숨김

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, x-api-key, Authorization, anthropic-version",
        )
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/save_config":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                config_data = json.loads(post_data.decode("utf-8"))
                config_file = "config.json"

                existing_config = {}
                if os.path.exists(config_file):
                    try:
                        with open(config_file, "r", encoding="utf-8") as f:
                            existing_config = json.load(f)
                    except Exception:
                        pass

                valid_keys = {
                    "gemini",
                    "claude",
                    "claude_endpoint",
                    "claude_model",
                    "client_id",
                    "blog_id",
                    "yt_key",
                    "yt_channel",
                }
                for key, val in config_data.items():
                    if key in valid_keys:
                        existing_config[key] = val

                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(existing_config, f, ensure_ascii=False, indent=2)

                _send_json(self, 200, {"status": "success"})
            except Exception as e:
                _send_json(self, 500, {"error": str(e)})
            return

        # 브라우저 CORS 우회: 칩섭/Anthropic Messages 프록시
        if self.path == "/api/claude":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode("utf-8"))
                api_key = (payload.get("api_key") or "").strip()
                endpoint = (payload.get("endpoint") or "https://api.cheapsub.im/v1").strip().rstrip("/")
                if endpoint.endswith("/messages"):
                    endpoint = endpoint[: -len("/messages")]
                body = payload.get("body") or {}
                if not api_key:
                    _send_json(self, 400, {"error": {"message": "api_key 없음"}})
                    return

                target = endpoint + "/messages"
                # Cloudflare(칩섭)가 Python 기본 UA 를 막는 경우(1010) 대비
                req_headers = {
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36 EconnyamBlogProxy/1.0"
                    ),
                    "Accept": "application/json",
                }
                if api_key.startswith("csk_"):
                    req_headers["Authorization"] = "Bearer " + api_key

                data = json.dumps(body, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    target, data=data, headers=req_headers, method="POST"
                )
                try:
                    with urllib.request.urlopen(req, timeout=300) as resp:
                        resp_body = resp.read()
                        self.send_response(resp.status)
                        self.send_header(
                            "Content-Type",
                            resp.headers.get("Content-Type", "application/json"),
                        )
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Content-Length", str(len(resp_body)))
                        self.end_headers()
                        self.wfile.write(resp_body)
                except urllib.error.HTTPError as he:
                    err_body = he.read()
                    self.send_response(he.code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(err_body)))
                    self.end_headers()
                    self.wfile.write(err_body)
            except Exception as e:
                _send_json(self, 500, {"error": {"message": "프록시 오류: " + str(e)}})
            return

        self.send_response(404)
        self.end_headers()


Handler = CustomHandler

try:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n서버 종료")
    sys.exit(0)
except OSError as e:
    if "Address already in use" in str(e) or "10048" in str(e):
        print(f"\n포트 {PORT} 이 이미 사용 중이에요.")
        print("브라우저에서 직접 접속하세요:")
        print(f"  {url}")
        input("Enter 키로 종료...")
    else:
        raise
