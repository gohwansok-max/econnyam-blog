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


# 브라우저가 탭을 닫거나 새로고침하면 연결이 끊김 → 정상 상황
_CLIENT_GONE = (
    ConnectionAbortedError,
    ConnectionResetError,
    BrokenPipeError,
    TimeoutError,
)


def _client_gone(exc):
    if isinstance(exc, _CLIENT_GONE):
        return True
    # Windows: WinError 10053, 10054 등
    msg = str(exc)
    return "10053" in msg or "10054" in msg or "10058" in msg or "중단" in msg


def _send_json(handler, status, obj):
    try:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except Exception as e:
        if _client_gone(e):
            return  # 브라우저가 먼저 끊음 — 무시
        raise


def _write_raw(handler, status, content_type, body_bytes):
    try:
        handler.send_response(status)
        handler.send_header("Content-Type", content_type or "application/json")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Content-Length", str(len(body_bytes)))
        handler.end_headers()
        handler.wfile.write(body_bytes)
    except Exception as e:
        if _client_gone(e):
            return
        raise


class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 로그 숨김

    def handle_one_request(self):
        """클라이언트가 중간에 끊어도 서버 창에 빨간 스택 안 띄움"""
        try:
            super().handle_one_request()
        except Exception as e:
            if _client_gone(e):
                return
            # 기타 예외만 한 줄 출력
            print("[서버] 요청 처리 중 오류:", type(e).__name__, str(e)[:120])

    def do_OPTIONS(self):
        try:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, x-api-key, Authorization, anthropic-version",
            )
            self.send_header("Access-Control-Max-Age", "86400")
            self.end_headers()
        except Exception as e:
            if _client_gone(e):
                return
            raise

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
                if _client_gone(e):
                    return
                _send_json(self, 500, {"error": str(e)})
            return

        # 브라우저 CORS 우회: 칩섭/Anthropic Messages 프록시
        if self.path == "/api/claude":
            content_length = int(self.headers.get("Content-Length", 0))
            try:
                post_data = self.rfile.read(content_length)
            except Exception as e:
                if _client_gone(e):
                    return
                raise

            try:
                payload = json.loads(post_data.decode("utf-8"))
                api_key = (payload.get("api_key") or "").strip()
                endpoint = (
                    payload.get("endpoint") or "https://api.cheapsub.im/v1"
                ).strip().rstrip("/")
                if endpoint.endswith("/messages"):
                    endpoint = endpoint[: -len("/messages")]
                body = payload.get("body") or {}
                if not api_key:
                    _send_json(self, 400, {"error": {"message": "api_key 없음"}})
                    return

                target = endpoint + "/messages"
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
                        _write_raw(
                            self,
                            resp.status,
                            resp.headers.get("Content-Type", "application/json"),
                            resp_body,
                        )
                except urllib.error.HTTPError as he:
                    err_body = he.read()
                    _write_raw(self, he.code, "application/json", err_body)
            except Exception as e:
                if _client_gone(e):
                    # 브라우저 탭 닫음 / 새로고침 / 생성 중단 → 정상
                    print("[알림] 브라우저가 연결을 끊었습니다. (탭 닫기·새로고침·중단 시 정상)")
                    return
                _send_json(self, 500, {"error": {"message": "프록시 오류: " + str(e)}})
            return

        try:
            self.send_response(404)
            self.end_headers()
        except Exception as e:
            if _client_gone(e):
                return
            raise


Handler = CustomHandler

try:
    # 같은 포트 재시작 편하게
    socketserver.TCPServer.allow_reuse_address = True
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
