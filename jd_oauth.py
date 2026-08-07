# -*- coding: utf-8 -*-
"""
京东联盟 OAuth 授权流程一键脚本

流程：
1. 自动拼接授权URL，打印到终端
2. 启动本地HTTP服务器(端口8080)等待回调
3. 用户在浏览器登录京东后，京东回调带code参数到本地
4. 脚本自动用code换取access_token
5. 打印token信息，提示保存到.env

用法：
    python jd_oauth.py

前置条件：
    - .env 文件中有 JD_APP_KEY 和 JD_APP_SECRET
    - 京东应用控制台中，回调地址设置为 http://localhost:8080/callback
"""

import http.server
import os
import sys
import json
import time
import secrets
import urllib.parse
import webbrowser
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── 配置 ──────────────────────────────────────────────
REDIRECT_URI = "http://localhost:8080/callback"
CALLBACK_PORT = 8080
OAUTH_BASE = "https://open-oauth.jd.com"

# ── 读取凭证 ──────────────────────────────────────────
def load_env():
    """从 .env 文件读取凭证"""
    env_path = Path(__file__).parent / ".env"
    creds = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    return creds

# ── OAuth回调处理器 ───────────────────────────────────
class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """处理京东OAuth回调的HTTP请求处理器"""
    
    # 类变量，用于传递结果
    received_code = None
    received_state = None
    error = None
    
    def do_GET(self):
        """处理GET请求（京东回调）"""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        if parsed.path == "/callback":
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]
            error_desc = params.get("error_description", [None])[0]
            
            if error:
                OAuthCallbackHandler.error = f"授权失败: {error} - {error_desc}"
                self._send_html("error", f"授权失败: {error_desc}")
            elif code:
                OAuthCallbackHandler.received_code = code
                OAuthCallbackHandler.received_state = state
                self._send_html("success", "授权成功！请回到终端查看结果。可以关闭此页面。")
            else:
                self._send_html("error", "回调中没有code参数")
        else:
            self.send_response(404)
            self.end_headers()
    
    def _send_html(self, status, message):
        """发送HTML响应"""
        color = "#52c41a" if status == "success" else "#ff4d4f"
        title = "授权成功" if status == "success" else "授权失败"
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 80px;">
<h1 style="color: {color};">{title}</h1>
<p style="font-size: 18px;">{message}</p>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
    
    def log_message(self, format, *args):
        """静默日志"""
        pass

# ── 拼接授权URL ───────────────────────────────────────
def build_auth_url(app_key, redirect_uri, state):
    """拼接OAuth授权URL"""
    params = {
        "app_key": app_key,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "snsapi_base",
    }
    query = urllib.parse.urlencode(params)
    return f"{OAUTH_BASE}/oauth2/to_login?{query}"

# ── 用code换token ────────────────────────────────────
def exchange_code_for_token(app_key, app_secret, code):
    """用授权code换取access_token"""
    url = f"{OAUTH_BASE}/oauth2/access_token"
    params = {
        "app_key": app_key,
        "app_secret": app_secret,
        "grant_type": "authorization_code",
        "code": code,
    }
    resp = requests.get(url, params=params, timeout=15)
    return resp.json()

# ── 主流程 ────────────────────────────────────────────
def main():
    creds = load_env()
    app_key = creds.get("JD_APP_KEY", "")
    app_secret = creds.get("JD_APP_SECRET", "")
    
    if not app_key or not app_secret:
        print("[ERROR] .env 文件中缺少 JD_APP_KEY 或 JD_APP_SECRET")
        sys.exit(1)
    
    print("=" * 60)
    print("  京东联盟 OAuth 授权流程")
    print("=" * 60)
    print(f"  AppKey:      {app_key}")
    print(f"  AppSecret:   {app_secret[:8]}...{app_secret[-4:]}")
    print(f"  回调地址:     {REDIRECT_URI}")
    print("=" * 60)
    print()
    
    # ⚠️ 检查回调地址是否匹配
    print("[重要] 请确认你在京东应用控制台设置的回调地址是：")
    print(f"       {REDIRECT_URI}")
    print("       如果不一致，请先去控制台修改，等2分钟后再运行本脚本。")
    print()
    
    # 生成随机state
    state = secrets.token_hex(16)
    auth_url = build_auth_url(app_key, REDIRECT_URI, state)
    
    print("请点击以下链接或在浏览器中打开，登录京东账号完成授权：")
    print()
    print(auth_url)
    print()
    
    # 尝试自动打开浏览器
    try:
        webbrowser.open(auth_url)
        print("[已自动打开浏览器，如果没弹出请手动复制上面的链接]")
    except Exception:
        print("[请手动复制上面的链接到浏览器打开]")
    print()
    print("等待京东回调中... (超时时间: 5分钟)")
    print()
    
    # 启动本地HTTP服务器等待回调
    server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = 300  # 5分钟超时
    
    # 等待回调
    handled = False
    start_time = time.time()
    while time.time() - start_time < 300:
        server.handle_request()
        if OAuthCallbackHandler.received_code or OAuthCallbackHandler.error:
            handled = True
            break
    
    server.server_close()
    
    if not handled:
        print("[ERROR] 等待超时，没有收到京东回调。请重试。")
        sys.exit(1)
    
    if OAuthCallbackHandler.error:
        print(f"[ERROR] {OAuthCallbackHandler.error}")
        sys.exit(1)
    
    # 验证state
    if OAuthCallbackHandler.received_state != state:
        print("[WARNING] state不匹配，可能存在CSRF攻击，但仍继续处理...")
    
    code = OAuthCallbackHandler.received_code
    print(f"[OK] 收到授权码: {code[:20]}...")
    print()
    
    # 用code换token
    print("正在用授权码换取 access_token...")
    result = exchange_code_for_token(app_key, app_secret, code)
    
    print()
    print("-" * 60)
    print("Token 获取结果：")
    print("-" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("-" * 60)
    
    if "access_token" in result:
        access_token = result["access_token"]
        expires_in = result.get("expires_in", 0)
        refresh_token = result.get("refresh_token", "")
        xid = result.get("xid", "")
        
        print()
        print("[成功] access_token 已获取！")
        print(f"  access_token:   {access_token}")
        print(f"  expires_in:     {expires_in} 秒 (约 {int(expires_in/86400)} 天)")
        print(f"  refresh_token:  {refresh_token}")
        print(f"  xid:            {xid}")
        print()
        
        # 自动写入 .env 文件
        env_path = Path(__file__).parent / ".env"
        env_content = env_path.read_text(encoding="utf-8")
        
        # 追加或替换 JD_ACCESS_TOKEN
        if "JD_ACCESS_TOKEN=" in env_content:
            lines = env_content.splitlines()
            new_lines = []
            for line in lines:
                if line.startswith("JD_ACCESS_TOKEN="):
                    new_lines.append(f"JD_ACCESS_TOKEN={access_token}")
                elif line.startswith("JD_REFRESH_TOKEN="):
                    new_lines.append(f"JD_REFRESH_TOKEN={refresh_token}")
                else:
                    new_lines.append(line)
            # 确保 refresh_token 也在
            if not any(l.startswith("JD_REFRESH_TOKEN=") for l in new_lines):
                new_lines.append(f"JD_REFRESH_TOKEN={refresh_token}")
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        else:
            env_path.write_text(
                env_content.rstrip("\n")
                + f"\nJD_ACCESS_TOKEN={access_token}\n"
                + f"JD_REFRESH_TOKEN={refresh_token}\n",
                encoding="utf-8",
            )
        
        print("[已保存] token 已写入 .env 文件:")
        print(f"  JD_ACCESS_TOKEN={access_token}")
        print(f"  JD_REFRESH_TOKEN={refresh_token}")
        print()
        print("现在可以运行 test_jd_api.py 测试 goods.query 接口了！")
    else:
        print()
        print("[ERROR] 获取token失败，请检查上面的返回信息。")
        print(f"  错误码: {result.get('code', 'N/A')}")
        print(f"  错误信息: {result.get('msg', result.get('error', 'N/A'))}")


if __name__ == "__main__":
    main()
