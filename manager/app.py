"""WA-TG Bridge 管理面板后端。

职责：
  * 通过 supervisord 控制安卓模拟器（Xvfb + x11vnc + emulator）和 watgbridge 的启停
  * 提供 noVNC 网页远程画面（内置 WebSocket→VNC 转发，单端口 + 统一登录）
  * 图形化编辑 watgbridge 配置
  * 调用 wapair 完成 WhatsApp 关联设备登录（配对码 / 二维码）
  * 记录安卓手机最后在线时间，支持定期自动开机保活、Telegram 提醒
"""

import asyncio
import base64
import contextvars
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

import qrcode
import qrcode.image.svg
import yaml
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

import config_schema as cs

log = logging.getLogger("manager")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------------------------------------------------------- 路径 & 常量
DATA = Path(os.environ.get("DATA_DIR", "/data"))
CONFIG_PATH = DATA / "config.yaml"
BRIDGE_DIR = DATA / "bridge"
LOG_DIR = DATA / "logs"
STATE_PATH = DATA / "manager.json"
APK_DIR = DATA / "apk"
STATIC_DIR = Path(__file__).parent / "static"
NOVNC_DIR = Path(os.environ.get("NOVNC_DIR", "/usr/share/novnc"))
BUILTIN_BIN_DIR = Path(os.environ.get("BUILTIN_BIN_DIR", "/opt/watgbridge"))  # 镜像内置版本
BIN_DIR = DATA / "bin"  # 在线更新后的版本（优先使用）
SUPERVISOR_CONF = os.environ.get("SUPERVISOR_CONF", "/etc/supervisor/wa.conf")
ADB = os.environ.get("ADB_BIN", "adb")
ADB_SERIAL = os.environ.get("ADB_SERIAL", "emulator-5554")
VNC_PORT = int(os.environ.get("VNC_PORT", "5900"))
WHATSAPP_APK_URL = os.environ.get("WHATSAPP_APK_URL", "https://www.whatsapp.com/android/current/WhatsApp.apk")
WHATSAPP_PKG = "com.whatsapp"
COOKIE = "wa_session"
SESSION_TTL = 7 * 86400

for d in (DATA, BRIDGE_DIR, LOG_DIR, APK_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- 持久状态
DEFAULT_STATE = {
    "bridge_enabled": True,
    "last_phone_online": 0,  # 模拟器上 WhatsApp 最后一次在线（开机完成）时间
    "last_paired": 0,
    "keepalive": {"enabled": False, "interval_days": 7, "duration_minutes": 20, "auto_update": True},
    "reminder": {"enabled": True, "days": 10},
    "last_reminder": 0,
    "language": "zh",  # 后台消息（Telegram 提醒）使用的语言，跟随界面最后一次选择
    "was_paired": False,  # 用于检测关联失效
}


def load_state() -> dict:
    st = json.loads(json.dumps(DEFAULT_STATE))
    if STATE_PATH.exists():
        try:
            saved = json.loads(STATE_PATH.read_text("utf-8"))
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(st.get(k), dict):
                    st[k].update(v)
                else:
                    st[k] = v
        except Exception as e:  # noqa: BLE001
            log.warning("failed to read manager.json: %s", e)
    return st


def save_state():
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(STATE_PATH)


STATE = load_state()

# 运行期（不持久化）
RUNTIME = {
    "boot_seen": False,          # 本次模拟器启动是否已检测到开机完成
    "keepalive_started_at": 0,   # 由保活任务启动模拟器的时间
    "job": None,                 # 当前 APK 安装任务 {"name","status","message"}
}

PAIR = {"proc": None, "status": "idle", "code": None, "qr": None, "qr_timeout": 0,
        "error": None, "jid": None, "mode": None, "updated": 0}


# ---------------------------------------------------------------- 国际化
# 当前请求的界面语言（"zh" / "en"），由前端通过 X-Lang 请求头传入
_LANG = contextvars.ContextVar("lang", default="zh")


def norm_lang(value: str | None) -> str:
    return "en" if (value or "").lower().startswith("en") else "zh"


def t(zh: str, en: str) -> str:
    """按当前请求语言返回文本（用于即时返回的错误信息）。"""
    return en if _LANG.get() == "en" else zh


def L(zh: str, en: str) -> dict:
    """双语文本对象（用于存储后再展示的消息，前端按所选语言显示）。"""
    return {"zh": zh, "en": en}


def tl(msg) -> str:
    """把 L() 对象转成当前语言的字符串。"""
    if isinstance(msg, dict):
        return msg.get(_LANG.get()) or msg.get("zh") or ""
    return str(msg)


def bg(zh: str, en: str) -> str:
    """后台任务（无请求上下文）使用面板最后选择的语言。"""
    return en if STATE.get("language") == "en" else zh


# ---------------------------------------------------------------- 认证
def _load_secret(name: str, generator) -> str:
    p = DATA / name
    if p.exists():
        return p.read_text("utf-8").strip()
    val = generator()
    p.write_text(val, "utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return val


SECRET = _load_secret(".secret", lambda: secrets.token_hex(32)).encode()
WEB_PASSWORD = os.environ.get("WEB_PASSWORD") or _load_secret(".web_password", lambda: secrets.token_urlsafe(12))
if not os.environ.get("WEB_PASSWORD"):
    log.warning("WEB_PASSWORD not set; generated admin password: %s (saved in %s) / "
                "未设置 WEB_PASSWORD，已自动生成管理密码", WEB_PASSWORD, DATA / ".web_password")


def make_token() -> str:
    exp = str(int(time.time()) + SESSION_TTL)
    sig = hmac.new(SECRET, exp.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def check_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    exp, sig = token.split(".", 1)
    good = hmac.new(SECRET, exp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good) and exp.isdigit() and int(exp) > time.time()


PUBLIC_PATHS = {"/login", "/api/login", "/healthz", "/static/style.css", "/static/login.js", "/static/i18n.js"}


# ---------------------------------------------------------------- 工具函数
def run(cmd: list[str], timeout: float = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", f"{cmd[0]}: not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


async def arun(cmd: list[str], timeout: float = 30) -> subprocess.CompletedProcess:
    return await asyncio.to_thread(run, cmd, timeout)


def sv(*args: str) -> subprocess.CompletedProcess:
    return run(["supervisorctl", "-c", SUPERVISOR_CONF, *args], 90)


def _bin(name: str) -> str:
    """优先使用 /data/bin 中在线更新的二进制，否则用镜像内置版本。"""
    p = BIN_DIR / name
    if p.is_file() and os.access(p, os.X_OK):
        return str(p)
    return str(BUILTIN_BIN_DIR / name)


def wapair_bin() -> str:
    return _bin("wapair")


def sv_status() -> dict[str, str]:
    """返回 {进程名: 状态}，进程名形如 bridge / android:emulator。"""
    res = sv("status")
    out = {}
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


def adb(*args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return run([ADB, "-s", ADB_SERIAL, *args], timeout)


def kvm_status() -> dict:
    exists = os.path.exists("/dev/kvm")
    ok = exists and os.access("/dev/kvm", os.R_OK | os.W_OK)
    return {"available": ok, "exists": exists}


def read_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def enforce_paths(cfg: dict) -> dict:
    """容器内固定的路径，避免用户误改导致数据写到非持久化目录。"""
    cfg["ffmpeg_executable"] = "/usr/bin/ffmpeg"
    cfg["git_executable"] = "/usr/bin/git"
    cfg.setdefault("whatsapp", {})
    ldb = cfg["whatsapp"].get("login_database") or {}
    if not ldb.get("type") or ldb.get("type") == "sqlite3":
        cfg["whatsapp"]["login_database"] = {
            "type": "sqlite3", "url": f"file:{BRIDGE_DIR}/wawebstore.db?_foreign_keys=on"}
    db = cfg.get("database") or {}
    if not db.get("type") or db.get("type") == "sqlite":
        cfg["database"] = {"type": "sqlite", "path": str(BRIDGE_DIR / "gobot.sqlite.db")}
    return cfg


def write_config(cfg: dict):
    cfg = enforce_paths(cfg)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# Generated by WA-TG Bridge manager / 由 WA-TG Bridge 管理面板生成\n")
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    tmp.replace(CONFIG_PATH)


def ensure_config():
    if not CONFIG_PATH.exists():
        write_config(cs.default_config(str(DATA)))
        log.info("default config written to %s", CONFIG_PATH)


def config_ready(cfg: dict | None = None) -> tuple[bool, list[str]]:
    cfg = cfg if cfg is not None else read_config()
    missing = []
    tg = cfg.get("telegram") or {}
    if not str(tg.get("bot_token") or "").strip():
        missing.append(L("Bot Token", "Bot Token"))
    if not tg.get("owner_id"):
        missing.append(L("你的 Telegram 用户 ID", "Your Telegram user ID"))
    if not tg.get("target_chat_id"):
        missing.append(L("目标超级群组 ID", "Target supergroup ID"))
    return (not missing), missing


def wa_session() -> dict:
    """读取 whatsmeow 登录库判断是否已关联。"""
    cfg = read_config()
    ldb = (cfg.get("whatsapp") or {}).get("login_database") or {}
    if ldb.get("type", "sqlite3") != "sqlite3":
        res = run([wapair_bin(), "--config", str(CONFIG_PATH), "--status"], 30)
        for line in res.stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("event") == "status":
                return {"paired": ev.get("paired", False), "jid": ev.get("jid"), "push_name": ev.get("push_name")}
        return {"paired": False, "error": (res.stderr or res.stdout)[-300:]}
    url = ldb.get("url", "")
    path = url.split("?", 1)[0]
    path = path[len("file:"):] if path.startswith("file:") else path
    if path.startswith("//"):
        path = path[2:]
    if not path:
        path = str(BRIDGE_DIR / "wawebstore.db")
    if not os.path.isabs(path):
        path = str(BRIDGE_DIR / path)
    if not os.path.exists(path):
        return {"paired": False}
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=3)
        try:
            row = con.execute("SELECT jid, push_name FROM whatsmeow_device LIMIT 1").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return {"paired": False}
    if not row:
        return {"paired": False}
    return {"paired": True, "jid": row[0], "push_name": row[1]}


def remove_session_files():
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = BRIDGE_DIR / f"wawebstore.db{suffix}"
        if p.exists():
            p.unlink()


def tail(path: Path, lines: int = 300) -> str:
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 256 * 1024))
        data = f.read().decode("utf-8", "replace")
    return "\n".join(data.splitlines()[-lines:])


async def send_telegram(text: str) -> bool:
    cfg = read_config()
    tg = cfg.get("telegram") or {}
    token, owner = tg.get("bot_token"), tg.get("owner_id")
    if not token or not owner:
        return False
    base = (tg.get("api_url") or "https://api.telegram.org").rstrip("/")
    url = f"{base}/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": owner, "text": text}).encode()

    def _post():
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=20) as r:
                return r.status == 200
        except Exception as e:  # noqa: BLE001
            log.warning("failed to send Telegram message: %s", e)
            return False

    return await asyncio.to_thread(_post)


# ---------------------------------------------------------------- 安卓控制
def android_running() -> bool:
    return sv_status().get("android:emulator") in ("RUNNING", "STARTING")


def boot_completed() -> bool:
    res = adb("shell", "getprop", "sys.boot_completed", timeout=8)
    return res.returncode == 0 and res.stdout.strip() == "1"


def whatsapp_installed() -> bool:
    res = adb("shell", "pm", "list", "packages", WHATSAPP_PKG, timeout=15)
    return f"package:{WHATSAPP_PKG}\n" in (res.stdout + "\n")


def whatsapp_info() -> dict:
    """读取模拟器上 WhatsApp 的版本号与最后更新时间。"""
    res = adb("shell", "dumpsys", "package", WHATSAPP_PKG, timeout=20)
    info = {"installed": False, "version": None, "updated": None}
    if res.returncode != 0:
        return info
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.startswith("versionName=") and not info["version"]:
            info["version"] = line.split("=", 1)[1]
            info["installed"] = True
        elif line.startswith("lastUpdateTime=") and not info["updated"]:
            info["updated"] = line.split("=", 1)[1]
    return info


async def start_android():
    RUNTIME["boot_seen"] = False
    res = await asyncio.to_thread(sv, "start", "android:*")
    if res.returncode not in (0,) and "ALREADY_STARTED" not in res.stdout:
        log.warning("failed to start android: %s %s", res.stdout, res.stderr)
    return res


async def stop_android():
    # 先让模拟器优雅关机，保证 userdata 写盘
    await arun([ADB, "-s", ADB_SERIAL, "emu", "kill"], 15)
    for _ in range(20):
        if not android_running():
            break
        await asyncio.sleep(1)
    res = await asyncio.to_thread(sv, "stop", "android:*")
    RUNTIME["boot_seen"] = False
    RUNTIME["keepalive_started_at"] = 0
    return res


async def launch_whatsapp():
    await arun([ADB, "-s", ADB_SERIAL, "shell", "monkey", "-p", WHATSAPP_PKG,
                "-c", "android.intent.category.LAUNCHER", "1"], 20)


async def install_apk(path: Path, name: str) -> bool:
    """安装/升级 APK。使用 install -r 覆盖安装，应用数据（WhatsApp 登录状态）会保留。"""
    RUNTIME["job"] = {"name": name, "status": "running", "message": L("正在安装到模拟器…", "Installing on the emulator…")}
    before = await asyncio.to_thread(whatsapp_info)
    res = await arun([ADB, "-s", ADB_SERIAL, "install", "-r", "-g", str(path)], 600)
    detail = (res.stdout + res.stderr).strip()[-500:]
    if res.returncode == 0 and "Success" in res.stdout:
        after = await asyncio.to_thread(whatsapp_info)
        old, new = before.get("version"), after.get("version")
        if old and new and old != new:
            msg = L(f"已从 {old} 升级到 {new}", f"Upgraded from {old} to {new}")
        else:
            msg = L(f"安装成功（版本 {new or '?'}）", f"Installed successfully (version {new or '?'})")
        RUNTIME["job"] = {"name": name, "status": "done", "message": msg}
        return True
    if "INSTALL_FAILED_VERSION_DOWNGRADE" in detail:
        msg = L("安装失败：该 APK 版本比已安装的旧，不能降级", "Install failed: this APK is older than the installed version")
    elif "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in detail:
        msg = L("安装失败：签名与已安装版本不一致（请使用官方 APK）",
                "Install failed: signature differs from the installed app (use the official APK)")
    else:
        msg = L("安装失败：" + detail, "Install failed: " + detail)
    RUNTIME["job"] = {"name": name, "status": "error", "message": msg}
    return False


def _remote_apk_meta() -> dict:
    """获取官方 APK 的 Last-Modified / Content-Length / ETag，用来判断是否有新版本。"""
    req = urllib.request.Request(WHATSAPP_APK_URL, method="HEAD",
                                 headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return {k: r.headers.get(k) or "" for k in ("Last-Modified", "Content-Length", "ETag")}


async def download_and_install_whatsapp(force: bool = False):
    """下载官方最新版 WhatsApp 并安装/升级。force=False 时若官方文件与上次安装的相同则跳过。"""
    dest = APK_DIR / "WhatsApp.apk"
    RUNTIME["job"] = {"name": "WhatsApp", "status": "running",
                      "message": L("正在检查 whatsapp.com 上的最新版本…", "Checking whatsapp.com for the latest version…")}
    try:
        meta = await asyncio.to_thread(_remote_apk_meta)
    except Exception as e:  # noqa: BLE001
        meta = {}
        log.warning("HEAD %s failed: %s", WHATSAPP_APK_URL, e)
    installed = await asyncio.to_thread(whatsapp_info)
    if (not force and meta and meta.get("Content-Length") and installed.get("installed")
            and STATE.get("apk_installed_meta") == meta):
        RUNTIME["job"] = {"name": "WhatsApp", "status": "done",
                          "message": L(f"已是官方最新版本（{installed.get('version')}）",
                                       f"Already the latest official version ({installed.get('version')})")}
        return

    RUNTIME["job"]["message"] = L("正在从 whatsapp.com 下载官方 APK…", "Downloading the official APK from whatsapp.com…")

    def _download():
        req = urllib.request.Request(WHATSAPP_APK_URL, headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14)"})
        tmp = dest.with_suffix(".part")
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                got += len(chunk)
                if total:
                    pct = got * 100 // total
                    RUNTIME["job"]["message"] = L(f"正在下载官方 APK… {pct}%", f"Downloading official APK… {pct}%")
        tmp.replace(dest)

    try:
        await asyncio.to_thread(_download)
    except Exception as e:  # noqa: BLE001
        RUNTIME["job"] = {"name": "WhatsApp", "status": "error", "message": L(f"下载失败：{e}", f"Download failed: {e}")}
        return
    if await install_apk(dest, "WhatsApp") and meta:
        STATE["apk_installed_meta"] = meta
        save_state()


# ---------------------------------------------------------------- 桥接控制
def bridge_status() -> str:
    return sv_status().get("bridge", "UNKNOWN")


async def start_bridge() -> tuple[bool, str]:
    ok, missing = config_ready()
    if not ok:
        return False, t("配置不完整：", "Configuration incomplete: ") + ", ".join(tl(m) for m in missing)
    if not (await asyncio.to_thread(wa_session)).get("paired"):
        return False, t("WhatsApp 尚未登录关联", "WhatsApp is not linked yet")
    if PAIR["status"] in ("starting", "waiting"):
        return False, t("正在进行配对，请稍候", "Pairing in progress, please wait")
    res = await asyncio.to_thread(sv, "start", "bridge")
    return (res.returncode == 0 or "ALREADY_STARTED" in res.stdout), (res.stdout + res.stderr).strip()


async def stop_bridge():
    return await asyncio.to_thread(sv, "stop", "bridge")


async def restart_bridge():
    await stop_bridge()
    return await start_bridge()


# ---------------------------------------------------------------- WhatsApp 配对
def _pair_update(**kw):
    PAIR.update(kw)
    PAIR["updated"] = time.time()


async def pair_reader(proc: asyncio.subprocess.Process):
    logf = open(LOG_DIR / "pair.log", "a", encoding="utf-8")

    async def read_stderr():
        async for raw in proc.stderr:
            logf.write(raw.decode("utf-8", "replace"))
            logf.flush()

    err_task = asyncio.create_task(read_stderr())
    try:
        async for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").strip()
            logf.write(line + "\n")
            logf.flush()
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            e = ev.get("event")
            if e == "connecting":
                _pair_update(status="starting")
            elif e == "pair_code":
                _pair_update(status="waiting", code=ev.get("code"))
            elif e == "qr":
                _pair_update(status="waiting", qr=ev.get("code"), qr_timeout=time.time() + ev.get("timeout", 20))
            elif e == "pair_success":
                _pair_update(status="finishing", jid=ev.get("jid"))
            elif e in ("success", "already_paired"):
                _pair_update(status="success", jid=ev.get("jid"), code=None, qr=None)
            elif e == "error":
                _pair_update(status="error", error=pair_error_text(ev.get("code"), ev.get("error")))
        await proc.wait()
    finally:
        await err_task
        logf.close()
    if PAIR["status"] not in ("success", "error"):
        _pair_update(status="error", error=L(f"配对进程意外退出（代码 {proc.returncode}），详见 pair 日志",
                                             f"Pairing process exited unexpectedly (code {proc.returncode}), see the pair log"))
    PAIR["proc"] = None
    if PAIR["status"] == "success":
        STATE["last_paired"] = int(time.time())
        STATE["was_paired"] = True
        STATE["session_expired"] = False
        save_state()
        if STATE.get("bridge_enabled"):
            ok, msg = await start_bridge()
            log.info("start bridge after pairing: %s %s", ok, msg)


PAIR_ERRORS = {
    "config_load": ("加载配置失败", "Failed to load config"),
    "db_open": ("打开登录数据库失败", "Failed to open the login database"),
    "db_read": ("读取设备信息失败", "Failed to read device info"),
    "connect": ("连接 WhatsApp 失败", "Failed to connect to WhatsApp"),
    "pair_code_request": ("请求配对码失败（请检查号码是否正确）", "Failed to request a pairing code (check the phone number)"),
    "pair_error": ("配对失败", "Pairing failed"),
    "logged_out": ("被服务器注销", "Logged out by the server"),
    "client_outdated": ("客户端版本过旧，请更新 watgbridge 后重新构建镜像",
                        "Client is outdated; update watgbridge and rebuild the image"),
    "timeout": ("配对超时或被取消", "Pairing timed out or was cancelled"),
    "qr_expired": ("二维码已全部过期，请重新开始", "All QR codes expired, please start again"),
    "logout": ("注销失败", "Logout failed"),
}


def pair_error_text(code: str | None, detail: str | None) -> dict:
    zh, en = PAIR_ERRORS.get(code or "", ("出错", "Error"))
    return L(zh + (f"：{detail}" if detail else ""), en + (f": {detail}" if detail else ""))


async def start_pairing(phone: str | None):
    if PAIR["proc"] is not None:
        raise HTTPException(409, t("已有配对进行中", "A pairing session is already running"))
    if not Path(wapair_bin()).exists():
        raise HTTPException(500, t(f"未找到配对工具 {wapair_bin()}", f"Pairing tool not found: {wapair_bin()}"))
    await stop_bridge()
    cmd = [wapair_bin(), "--config", str(CONFIG_PATH)]
    if phone:
        cmd += ["--phone", phone]
    _pair_update(status="starting", code=None, qr=None, error=None, jid=None, mode="code" if phone else "qr")
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(BRIDGE_DIR),
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    PAIR["proc"] = proc
    asyncio.create_task(pair_reader(proc))


async def cancel_pairing():
    proc = PAIR["proc"]
    if proc and proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), 10)
        except asyncio.TimeoutError:
            proc.kill()
    _pair_update(status="idle", code=None, qr=None, error=None)


# ---------------------------------------------------------------- 后台循环
async def monitor_loop():
    while True:
        try:
            await monitor_tick()
        except Exception as e:  # noqa: BLE001
            log.exception("background task error: %s", e)
        await asyncio.sleep(15)


async def monitor_tick():
    now = int(time.time())
    running = await asyncio.to_thread(android_running)
    if running:
        if await asyncio.to_thread(boot_completed):
            STATE["last_phone_online"] = now
            save_state()
            if not RUNTIME["boot_seen"]:
                RUNTIME["boot_seen"] = True
                if await asyncio.to_thread(whatsapp_installed):
                    await launch_whatsapp()
                    # 保活开机时顺便检查并升级 WhatsApp（install -r 保留数据）
                    if (RUNTIME["keepalive_started_at"] and STATE["keepalive"].get("auto_update")
                            and not (RUNTIME["job"] and RUNTIME["job"]["status"] == "running")):
                        asyncio.create_task(download_and_install_whatsapp())
        # 保活任务到期后自动关机（有安装任务进行中时等待其完成）
        ka = STATE["keepalive"]
        job_running = bool(RUNTIME["job"] and RUNTIME["job"]["status"] == "running")
        if (RUNTIME["keepalive_started_at"] and not job_running
                and now - RUNTIME["keepalive_started_at"] > ka["duration_minutes"] * 60):
            log.info("keep-alive window finished, stopping the emulator")
            await stop_android()
    else:
        RUNTIME["boot_seen"] = False
        ka = STATE["keepalive"]
        last = STATE.get("last_phone_online") or 0
        if ka.get("enabled") and last and kvm_status()["available"] and now - last > ka["interval_days"] * 86400:
            log.info("phone offline for more than %s days, starting emulator for keep-alive", ka["interval_days"])
            RUNTIME["keepalive_started_at"] = now
            await start_android()

    await check_session_expiry()

    rm = STATE["reminder"]
    last = STATE.get("last_phone_online") or 0
    if rm.get("enabled") and last and now - last > rm["days"] * 86400 and now - STATE.get("last_reminder", 0) > 86400:
        days = (now - last) // 86400
        sent = await send_telegram(bg(
            f"⚠️ WA-TG Bridge 提醒：安卓手机端 WhatsApp 已有 {days} 天未上线。\n"
            "WhatsApp 在主手机离线约 14 天后会注销所有关联设备，请尽快打开管理面板启动安卓模拟器。",
            f"⚠️ WA-TG Bridge reminder: WhatsApp on the Android phone has been offline for {days} days.\n"
            "WhatsApp logs out all linked devices after the primary phone is offline for about 14 days. "
            "Please open the manager and start the Android emulator soon."))
        if sent:
            STATE["last_reminder"] = now
            save_state()


async def check_session_expiry():
    """关联设备被 WhatsApp 注销后（whatsmeow 会删除本地会话），停止桥接并提醒用户重新关联。"""
    if PAIR["proc"] is not None:
        return
    session = await asyncio.to_thread(wa_session)
    if session.get("paired"):
        if not STATE.get("was_paired"):
            STATE["was_paired"] = True
            save_state()
        return
    if STATE.get("was_paired"):
        log.warning("WhatsApp linked session is gone (expired or removed); stopping bridge")
        STATE["was_paired"] = False
        STATE["session_expired"] = True
        save_state()
        await stop_bridge()
        await send_telegram(bg(
            "⚠️ WA-TG Bridge：WhatsApp 关联已失效（可能因手机长时间离线或在手机上被移除），转发已停止。\n"
            "请打开管理面板 → 安卓手机 → 启动，然后在「WhatsApp 关联」页用配对码重新关联。",
            "⚠️ WA-TG Bridge: the WhatsApp link has expired (phone offline too long or removed on the phone). "
            "Forwarding has stopped.\nOpen the manager → Android → Start, then re-link on the \"WhatsApp link\" page "
            "using a pairing code."))
    elif await asyncio.to_thread(bridge_status) in ("RUNNING", "STARTING", "BACKOFF"):
        await stop_bridge()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_config()
    if STATE.get("bridge_enabled"):
        ok, msg = await start_bridge()
        log.info("auto-start bridge on boot: %s %s", ok, msg)
    task = asyncio.create_task(monitor_loop())
    yield
    task.cancel()
    await cancel_pairing()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    _LANG.set(norm_lang(request.headers.get("x-lang") or request.cookies.get("lang")
                        or request.headers.get("accept-language")))
    path = request.url.path
    if path in PUBLIC_PATHS or check_token(request.cookies.get(COOKIE)):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": t("未登录", "Not logged in")}, status_code=401)
    return RedirectResponse("/login")


# ---------------------------------------------------------------- 页面 & 登录
@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/login")
async def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.post("/api/login")
async def api_login(request: Request):
    body = await request.json()
    if not hmac.compare_digest(str(body.get("password", "")), WEB_PASSWORD):
        await asyncio.sleep(1)
        raise HTTPException(401, t("密码错误", "Wrong password"))
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE, make_token(), max_age=SESSION_TTL, httponly=True, samesite="lax")
    return resp


@app.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------- 状态
@app.get("/api/status")
async def api_status():
    st = await asyncio.to_thread(sv_status)
    emu = st.get("android:emulator", "STOPPED")
    booted = False
    wa_installed = None
    wa_app = {}
    if emu == "RUNNING":
        booted = await asyncio.to_thread(boot_completed)
        if booted:
            wa_app = await asyncio.to_thread(whatsapp_info)
            wa_installed = wa_app.get("installed")
    ok, missing = config_ready()
    session = await asyncio.to_thread(wa_session)
    last = STATE.get("last_phone_online") or 0
    return {
        "kvm": kvm_status(),
        "android": {"state": emu, "booted": booted, "whatsapp_installed": wa_installed,
                    "whatsapp_version": wa_app.get("version"), "whatsapp_updated": wa_app.get("updated"),
                    "vnc": st.get("android:vnc"), "xvfb": st.get("android:xvfb"),
                    "keepalive_session": bool(RUNTIME["keepalive_started_at"])},
        "bridge": {"state": st.get("bridge", "UNKNOWN"), "enabled": STATE.get("bridge_enabled", True)},
        "config": {"ready": ok, "missing": missing},
        "whatsapp": {**session, "expired": bool(STATE.get("session_expired")) and not session.get("paired")},
        "phone": {"last_online": last, "days_offline": ((time.time() - last) / 86400) if last else None},
        "job": RUNTIME["job"],
        "settings": {"keepalive": STATE["keepalive"], "reminder": STATE["reminder"]},
        "now": int(time.time()),
    }


# ---------------------------------------------------------------- 安卓 API
@app.post("/api/android/start")
async def api_android_start():
    if not kvm_status()["available"]:
        raise HTTPException(400, t("容器内没有可用的 /dev/kvm，无法运行安卓模拟器。请在宿主机开启虚拟化并以 --device /dev/kvm 启动容器。",
                                   "/dev/kvm is not available in the container, so the Android emulator cannot run. "
                                   "Enable virtualization on the host and start the container with --device /dev/kvm."))
    RUNTIME["keepalive_started_at"] = 0
    res = await start_android()
    return {"ok": True, "output": (res.stdout + res.stderr).strip()}


@app.post("/api/android/stop")
async def api_android_stop():
    res = await stop_android()
    return {"ok": True, "output": (res.stdout + res.stderr).strip()}


@app.post("/api/android/key/{key}")
async def api_android_key(key: str):
    codes = {"home": "KEYCODE_HOME", "back": "KEYCODE_BACK", "recent": "KEYCODE_APP_SWITCH",
             "power": "KEYCODE_POWER", "wake": "KEYCODE_WAKEUP"}
    if key == "whatsapp":
        await launch_whatsapp()
        return {"ok": True}
    if key not in codes:
        raise HTTPException(400, t("未知按键", "Unknown key"))
    res = await arun([ADB, "-s", ADB_SERIAL, "shell", "input", "keyevent", codes[key]], 15)
    return {"ok": res.returncode == 0}


@app.post("/api/android/text")
async def api_android_text(request: Request):
    """把电脑上输入的文字发送到模拟器（用于粘贴验证码等）。"""
    text = str((await request.json()).get("text", ""))
    if not text:
        return {"ok": True}
    escaped = "".join("%s" if c == " " else ("\\" + c if c in "\\'\"`$&|;<>()*?!#~" else c) for c in text)
    res = await arun([ADB, "-s", ADB_SERIAL, "shell", "input", "text", escaped], 30)
    return {"ok": res.returncode == 0, "output": res.stderr.strip()}


def _require_booted():
    if not boot_completed():
        raise HTTPException(400, t("安卓模拟器尚未启动完成", "The Android emulator has not finished booting"))


@app.post("/api/android/install-whatsapp")
async def api_install_whatsapp(force: bool = False):
    """安装或升级到官方最新版；force=true 时无论是否已是最新都重新下载安装。"""
    await asyncio.to_thread(_require_booted)
    if RUNTIME["job"] and RUNTIME["job"]["status"] == "running":
        raise HTTPException(409, t("已有安装任务进行中", "An install task is already running"))
    asyncio.create_task(download_and_install_whatsapp(force=force))
    return {"ok": True}


@app.post("/api/android/upload-apk")
async def api_upload_apk(file: UploadFile = File(...)):
    await asyncio.to_thread(_require_booted)
    if not (file.filename or "").lower().endswith(".apk"):
        raise HTTPException(400, t("请上传 .apk 文件", "Please upload an .apk file"))
    dest = APK_DIR / "uploaded.apk"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    asyncio.create_task(install_apk(dest, file.filename))
    return {"ok": True}


@app.get("/api/android/screenshot")
async def api_screenshot():
    res = await asyncio.to_thread(
        lambda: subprocess.run([ADB, "-s", ADB_SERIAL, "exec-out", "screencap", "-p"], capture_output=True, timeout=15))
    if res.returncode != 0 or not res.stdout:
        raise HTTPException(400, t("截图失败", "Screenshot failed"))
    return Response(res.stdout, media_type="image/png")


# ---------------------------------------------------------------- watgbridge 在线更新
# 新版本二进制放在 /data/bin（持久化），上一版本保存在 /data/bin/prev，可一键回滚。
GH_REPO = os.environ.get("WATGBRIDGE_GITHUB", "akshettrj/watgbridge")
GIT_URL = os.environ.get("WATGBRIDGE_REPO", f"https://github.com/{GH_REPO}.git")
GO_BIN = os.environ.get("GO_BIN", "/usr/local/go/bin/go")
WAPAIR_SRC = Path(os.environ.get("WAPAIR_SRC", "/opt/watgbridge/src/wapair/main.go"))
BUILD_DIR = DATA / "build"
PREV_DIR = BIN_DIR / "prev"
UPDATE_LOG = LOG_DIR / "update.log"
BIN_NAMES = ("watgbridge", "wapair")
UPD: dict = {"status": "idle", "message": None, "started": 0}
_RELEASE_CACHE: dict = {"at": 0, "data": None}


def release_arch() -> str:
    import platform
    return "aarch64" if platform.machine().lower() in ("aarch64", "arm64") else "amd64"


def read_version(d: Path) -> dict:
    try:
        return json.loads((d / "version.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def bridge_version_info() -> dict:
    override = (BIN_DIR / "watgbridge").is_file()
    info = read_version(BIN_DIR if override else BUILTIN_BIN_DIR)
    info["override"] = override
    info["builtin"] = read_version(BUILTIN_BIN_DIR)
    prev = None
    if PREV_DIR.is_dir():
        prev = {"builtin": True} if (PREV_DIR / "BUILTIN").exists() else read_version(PREV_DIR)
    info["prev"] = prev
    info["go_available"] = Path(GO_BIN).exists()
    return info


def fetch_releases(force: bool = False) -> list[dict]:
    if not force and _RELEASE_CACHE["data"] is not None and time.time() - _RELEASE_CACHE["at"] < 600:
        return _RELEASE_CACHE["data"]
    req = urllib.request.Request(f"https://api.github.com/repos/{GH_REPO}/releases?per_page=15",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "wa-tg-bridge"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    asset = f"watgbridge_linux_{release_arch()}"
    out = []
    for rel in data:
        if rel.get("draft"):
            continue
        url = next((a["browser_download_url"] for a in rel.get("assets", []) if a.get("name") == asset), None)
        if url:
            out.append({"tag": rel["tag_name"], "published": rel.get("published_at"), "url": url,
                        "prerelease": rel.get("prerelease", False)})
    _RELEASE_CACHE.update(at=time.time(), data=out)
    return out


def _ulog(text: str):
    with open(UPDATE_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%F %T')}] {text}\n")


def _is_elf(p: Path) -> bool:
    try:
        with open(p, "rb") as f:
            return f.read(4) == b"\x7fELF" and p.stat().st_size > 1_000_000
    except OSError:
        return False


def _swap_in(new_files: dict[str, Path], version: dict):
    """把新二进制放入 /data/bin，当前版本移到 /data/bin/prev。new_files 中缺少的（如 wapair）沿用当前版本。"""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    if PREV_DIR.exists():
        shutil.rmtree(PREV_DIR)
    PREV_DIR.mkdir()
    if (BIN_DIR / "watgbridge").is_file():
        for name in BIN_NAMES:
            src = BIN_DIR / name
            if src.is_file():
                if name in new_files:
                    shutil.move(str(src), PREV_DIR / name)
                else:
                    shutil.copy2(src, PREV_DIR / name)
        if (BIN_DIR / "version.json").exists():
            shutil.move(str(BIN_DIR / "version.json"), PREV_DIR / "version.json")
    else:
        (PREV_DIR / "BUILTIN").write_text("1")
    for name in BIN_NAMES:
        dst = BIN_DIR / name
        if name in new_files:
            shutil.copy2(new_files[name], dst)
        elif not dst.exists() and (BUILTIN_BIN_DIR / name).exists():
            shutil.copy2(BUILTIN_BIN_DIR / name, dst)
        if dst.exists():
            os.chmod(dst, 0o755)
    version = {**version, "installed_at": int(time.time())}
    (BIN_DIR / "version.json").write_text(json.dumps(version, ensure_ascii=False), "utf-8")


def _rollback_files() -> bool:
    if not PREV_DIR.is_dir():
        return False
    if (PREV_DIR / "BUILTIN").exists():
        for name in (*BIN_NAMES, "version.json"):
            p = BIN_DIR / name
            if p.exists():
                p.unlink()
    else:
        for name in (*BIN_NAMES, "version.json"):
            src = PREV_DIR / name
            if src.exists():
                shutil.copy2(src, BIN_DIR / name)
    shutil.rmtree(PREV_DIR)
    return True


async def _restart_and_verify() -> bool | None:
    """重启桥接并确认能正常运行。返回 None 表示桥接未在使用（无法验证）。"""
    if not STATE.get("bridge_enabled") or not config_ready()[0] or not (await asyncio.to_thread(wa_session)).get("paired"):
        return None
    await restart_bridge()
    for _ in range(12):
        await asyncio.sleep(5)
        st = await asyncio.to_thread(bridge_status)
        if st in ("FATAL", "BACKOFF", "EXITED"):
            return False
    return await asyncio.to_thread(bridge_status) == "RUNNING"


async def _finish_install(new_files: dict[str, Path], version: dict, label: str):
    await stop_bridge()
    await asyncio.to_thread(_swap_in, new_files, version)
    _ulog(f"installed {label}")
    ok = await _restart_and_verify()
    if ok is False:
        _ulog("new version failed to start, rolling back")
        await asyncio.to_thread(_rollback_files)
        await _restart_and_verify()
        UPD.update(status="error", message=L(f"{label} 启动失败，已自动回滚到之前的版本，详见更新日志和转发日志",
                                             f"{label} failed to start and was rolled back automatically; see the update and bridge logs"))
        return
    UPD.update(status="done", message=L(f"已更新到 {label}" + ("" if ok else "（转发未运行，未做启动验证）"),
                                        f"Updated to {label}" + ("" if ok else " (bridge not running, start not verified)")))


async def update_from_release(tag: str):
    UPD.update(status="running", started=time.time(), message=L(f"正在下载 {tag}…", f"Downloading {tag}…"))
    try:
        rels = await asyncio.to_thread(fetch_releases)
        rel = next((r for r in rels if r["tag"] == tag), None)
        if not rel:
            raise RuntimeError(f"release {tag} not found")
        tmp = BUILD_DIR / "download"
        tmp.mkdir(parents=True, exist_ok=True)
        dest = tmp / "watgbridge"

        def _dl():
            req = urllib.request.Request(rel["url"], headers={"User-Agent": "wa-tg-bridge"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)

        _ulog(f"download {rel['url']}")
        await asyncio.to_thread(_dl)
        if not _is_elf(dest):
            raise RuntimeError("downloaded file is not a valid Linux binary")
        await _finish_install({"watgbridge": dest}, {"source": "release", "version": tag.lstrip("v")}, tag)
    except Exception as e:  # noqa: BLE001
        _ulog(f"release update failed: {e}")
        UPD.update(status="error", message=L(f"更新失败：{e}", f"Update failed: {e}"))


def _build_from_source(ref: str) -> tuple[dict[str, Path], dict]:
    """在容器内用 Go 编译 watgbridge 和 wapair（保证两者使用同一版本的 whatsmeow）。"""
    src = BUILD_DIR / "src"
    out = BUILD_DIR / "out"
    env = {**os.environ, "GOPATH": str(BUILD_DIR / "gopath"), "GOMODCACHE": str(BUILD_DIR / "gopath" / "pkg" / "mod"),
           "GOCACHE": str(BUILD_DIR / "gocache"), "CGO_ENABLED": "1", "GOTOOLCHAIN": "auto",
           "PATH": f"{Path(GO_BIN).parent}:{os.environ.get('PATH', '')}"}

    def step(cmd: list[str], cwd: Path | None = None, timeout: int = 1800):
        _ulog("$ " + " ".join(cmd))
        with open(UPDATE_LOG, "a", encoding="utf-8") as f:
            res = subprocess.run(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
        if res.returncode != 0:
            raise RuntimeError(f"{cmd[0]} {cmd[1] if len(cmd) > 1 else ''} exited with {res.returncode}")

    if src.exists():
        shutil.rmtree(src)
    out.mkdir(parents=True, exist_ok=True)
    UPD["message"] = L(f"正在获取源码 {ref}…", f"Fetching source {ref}…")
    try:
        step(["git", "clone", "--depth", "1", "--branch", ref, GIT_URL, str(src)], timeout=600)
    except RuntimeError:
        if src.exists():
            shutil.rmtree(src)
        step(["git", "clone", GIT_URL, str(src)], timeout=900)
        step(["git", "checkout", ref], cwd=src)
    commit = run(["git", "-C", str(src), "rev-parse", "--short", "HEAD"]).stdout.strip()
    ver_file = src / "state" / "version.txt"
    version = ver_file.read_text("utf-8").strip() if ver_file.exists() else ""
    (src / "cmd" / "wapair").mkdir(parents=True, exist_ok=True)
    shutil.copy2(WAPAIR_SRC, src / "cmd" / "wapair" / "main.go")
    UPD["message"] = L("正在编译（首次需要下载依赖，可能要几分钟）…", "Compiling (the first build downloads dependencies and may take a few minutes)…")
    step([GO_BIN, "build", "-trimpath", "-ldflags", "-s -w", "-o", str(out / "watgbridge"), "."], cwd=src)
    step([GO_BIN, "build", "-trimpath", "-ldflags", "-s -w", "-o", str(out / "wapair"), "./cmd/wapair"], cwd=src)
    return ({"watgbridge": out / "watgbridge", "wapair": out / "wapair"},
            {"source": "source", "ref": ref, "commit": commit, "version": version})


async def update_from_source(ref: str):
    UPD.update(status="running", started=time.time(), message=L("正在准备编译…", "Preparing build…"))
    try:
        files, version = await asyncio.to_thread(_build_from_source, ref)
        label = f"{version.get('version') or ref} ({version.get('commit')})"
        await _finish_install(files, version, label)
    except Exception as e:  # noqa: BLE001
        _ulog(f"source build failed: {e}")
        UPD.update(status="error", message=L(f"编译失败：{e}（详见更新日志）", f"Build failed: {e} (see the update log)"))


async def update_from_upload(path: Path, filename: str):
    UPD.update(status="running", started=time.time(), message=L("正在安装上传的文件…", "Installing uploaded file…"))
    if not _is_elf(path):
        UPD.update(status="error", message=L("上传的文件不是有效的 Linux 可执行文件", "The uploaded file is not a valid Linux executable"))
        return
    await _finish_install({"watgbridge": path}, {"source": "upload", "version": filename}, filename)


async def rollback_bridge():
    UPD.update(status="running", started=time.time(), message=L("正在回滚…", "Rolling back…"))
    await stop_bridge()
    if not await asyncio.to_thread(_rollback_files):
        UPD.update(status="error", message=L("没有可回滚的版本", "No previous version to roll back to"))
        return
    _ulog("rolled back")
    await _restart_and_verify()
    UPD.update(status="done", message=L("已回滚到之前的版本", "Rolled back to the previous version"))


def _require_idle_update():
    if UPD["status"] == "running":
        raise HTTPException(409, t("已有更新任务进行中", "An update is already running"))
    if PAIR["proc"] is not None:
        raise HTTPException(409, t("正在进行 WhatsApp 关联，请稍后再更新", "WhatsApp linking is in progress, update later"))


@app.get("/api/update/status")
async def api_update_status():
    return {"current": await asyncio.to_thread(bridge_version_info), "job": UPD}


@app.get("/api/update/releases")
async def api_update_releases(refresh: bool = False):
    try:
        return {"releases": await asyncio.to_thread(fetch_releases, refresh)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, t("获取 GitHub Release 列表失败：", "Failed to fetch GitHub releases: ") + str(e)) from e


@app.post("/api/update/release")
async def api_update_release(request: Request):
    _require_idle_update()
    tag = str((await request.json()).get("tag") or "").strip()
    if not tag:
        raise HTTPException(400, t("请选择版本", "Please choose a version"))
    asyncio.create_task(update_from_release(tag))
    return {"ok": True}


@app.post("/api/update/source")
async def api_update_source(request: Request):
    _require_idle_update()
    ref = str((await request.json()).get("ref") or "main").strip()
    if not ref or any(c in ref for c in " ;&|$`\\\n") or ref.startswith("-"):
        raise HTTPException(400, t("分支/标签/提交名称无效", "Invalid branch / tag / commit"))
    if not Path(GO_BIN).exists():
        raise HTTPException(400, t("镜像中没有 Go 编译环境", "No Go toolchain in this image"))
    asyncio.create_task(update_from_source(ref))
    return {"ok": True}


@app.post("/api/update/upload")
async def api_update_upload(file: UploadFile = File(...)):
    _require_idle_update()
    dest = BUILD_DIR / "upload" / "watgbridge"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    asyncio.create_task(update_from_upload(dest, file.filename or "upload"))
    return {"ok": True}


@app.post("/api/update/rollback")
async def api_update_rollback():
    _require_idle_update()
    asyncio.create_task(rollback_bridge())
    return {"ok": True}


# ---------------------------------------------------------------- 桥接 API
@app.post("/api/bridge/{action}")
async def api_bridge(action: str):
    if action == "start":
        STATE["bridge_enabled"] = True
        save_state()
        ok, msg = await start_bridge()
        if not ok:
            raise HTTPException(400, msg)
        return {"ok": True}
    if action == "stop":
        STATE["bridge_enabled"] = False
        save_state()
        await stop_bridge()
        return {"ok": True}
    if action == "restart":
        STATE["bridge_enabled"] = True
        save_state()
        ok, msg = await restart_bridge()
        if not ok:
            raise HTTPException(400, msg)
        return {"ok": True}
    raise HTTPException(404)


# ---------------------------------------------------------------- 配置 API
@app.get("/api/config")
async def api_get_config():
    cfg = read_config()
    values = {k: cs.get_path(cfg, k) for k in cs.FIELD_INDEX}
    return {"schema": cs.SCHEMA, "values": values}


@app.put("/api/config")
async def api_put_config(request: Request):
    body = await request.json()
    cfg = read_config() or cs.default_config(str(DATA))
    errors = []
    for key, value in (body.get("values") or {}).items():
        field = cs.FIELD_INDEX.get(key)
        if not field:
            continue
        try:
            cs.set_path(cfg, key, cs.coerce(field, value, _LANG.get()))
        except (ValueError, TypeError) as e:
            errors.append(f"{t(field['label'], field['label_en'])}: {e}")
    if errors:
        raise HTTPException(400, "；".join(errors))
    tg = cfg.get("telegram") or {}
    if tg.get("owner_id") and not tg.get("sudo_users_id"):
        tg["sudo_users_id"] = [tg["owner_id"]]
    write_config(cfg)
    restarted = False
    if body.get("restart") and bridge_status() == "RUNNING":
        await restart_bridge()
        restarted = True
    return {"ok": True, "restarted": restarted}


@app.get("/api/config/raw")
async def api_get_raw():
    return {"yaml": CONFIG_PATH.read_text("utf-8") if CONFIG_PATH.exists() else ""}


@app.put("/api/config/raw")
async def api_put_raw(request: Request):
    text = (await request.json()).get("yaml", "")
    try:
        cfg = yaml.safe_load(text) or {}
        if not isinstance(cfg, dict):
            raise ValueError(t("顶层必须是映射", "top level must be a mapping"))
    except (yaml.YAMLError, ValueError) as e:
        raise HTTPException(400, t("YAML 格式错误：", "Invalid YAML: ") + str(e)) from e
    write_config(cfg)
    return {"ok": True}


# ---------------------------------------------------------------- WhatsApp 登录 API
@app.get("/api/wa/pair")
async def api_pair_status():
    out = {k: v for k, v in PAIR.items() if k != "proc"}
    out["running"] = PAIR["proc"] is not None
    if PAIR.get("qr"):
        img = qrcode.make(PAIR["qr"], image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
        buf = io.BytesIO()
        img.save(buf)
        out["qr_svg"] = "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()
        out["qr_remaining"] = max(0, int(PAIR["qr_timeout"] - time.time()))
    return out


@app.post("/api/wa/pair")
async def api_pair_start(request: Request):
    body = await request.json()
    session = await asyncio.to_thread(wa_session)
    if session.get("paired"):
        raise HTTPException(400, t("已经登录，如需重新关联请先注销", "Already linked. Log out first to link again"))
    phone = "".join(c for c in str(body.get("phone") or "") if c.isdigit())
    if body.get("mode") == "code":
        if len(phone) < 7:
            raise HTTPException(400, t("请输入带国家码的完整手机号，例如 8613800000000",
                                       "Enter the full phone number with country code, e.g. 14155550123"))
    else:
        phone = None
    await start_pairing(phone)
    return {"ok": True}


@app.post("/api/wa/pair/cancel")
async def api_pair_cancel():
    await cancel_pairing()
    return {"ok": True}


@app.post("/api/wa/logout")
async def api_wa_logout(request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        pass
    await cancel_pairing()
    await stop_bridge()
    note = ""
    if body.get("local_only"):
        await asyncio.to_thread(remove_session_files)
        note = t("已清除本地会话", "Local session cleared")
    else:
        res = await arun([wapair_bin(), "--config", str(CONFIG_PATH), "--logout"], 60)
        for line in res.stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("event") == "logged_out":
                if ev.get("code") == "local_only":
                    note = t("服务器注销失败，已清除本地会话：", "Server logout failed, local session cleared: ") + str(ev.get("error"))
                elif ev.get("code") == "not_paired":
                    note = t("当前未登录", "Not linked")
                else:
                    note = t("已注销", "Logged out")
            elif ev.get("event") == "error":
                raise HTTPException(500, tl(pair_error_text(ev.get("code"), ev.get("error"))))
    STATE["was_paired"] = False
    STATE["session_expired"] = False
    save_state()
    return {"ok": True, "note": note}


# ---------------------------------------------------------------- 设置 & 日志
@app.put("/api/settings")
async def api_settings(request: Request):
    body = await request.json()
    ka, rm = body.get("keepalive") or {}, body.get("reminder") or {}
    try:
        STATE["keepalive"] = {
            "enabled": bool(ka.get("enabled")),
            "interval_days": max(1, min(13, int(ka.get("interval_days", 7)))),
            "duration_minutes": max(5, min(240, int(ka.get("duration_minutes", 20)))),
            "auto_update": bool(ka.get("auto_update")),
        }
        STATE["reminder"] = {"enabled": bool(rm.get("enabled")), "days": max(1, min(30, int(rm.get("days", 10))))}
    except (TypeError, ValueError) as e:
        raise HTTPException(400, t("参数错误：", "Invalid parameter: ") + str(e)) from e
    save_state()
    return {"ok": True}


@app.put("/api/settings/language")
async def api_language(request: Request):
    STATE["language"] = norm_lang((await request.json()).get("language"))
    save_state()
    return {"ok": True}


@app.post("/api/settings/test-reminder")
async def api_test_reminder():
    ok = await send_telegram(t("✅ WA-TG Bridge 测试提醒：如果你看到这条消息，说明提醒功能正常。",
                               "✅ WA-TG Bridge test reminder: if you can see this, reminders are working."))
    if not ok:
        raise HTTPException(400, t("发送失败，请检查 Bot Token 和你的用户 ID，并确认已经给机器人发过 /start",
                                   "Sending failed. Check the Bot Token and your user ID, and make sure you have sent /start to the bot"))
    return {"ok": True}


LOG_FILES = {"bridge": "bridge.log", "emulator": "emulator.log", "pair": "pair.log",
             "manager": "manager.log", "vnc": "vnc.log", "supervisor": "supervisord.log",
             "update": "update.log"}


@app.get("/api/logs/{name}")
async def api_logs(name: str, lines: int = 300):
    if name not in LOG_FILES:
        raise HTTPException(404)
    return {"text": await asyncio.to_thread(tail, LOG_DIR / LOG_FILES[name], min(max(lines, 10), 3000))}


# ---------------------------------------------------------------- noVNC
@app.websocket("/websockify")
async def ws_vnc(ws: WebSocket):
    if not check_token(ws.cookies.get(COOKIE)):
        await ws.close(code=1008)
        return
    subprotocols = ws.scope.get("subprotocols") or []
    await ws.accept(subprotocol="binary" if "binary" in subprotocols else None)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", VNC_PORT)
    except OSError:
        await ws.close(code=1011)
        return

    async def ws_to_tcp():
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            data = msg.get("bytes")
            if data is None and msg.get("text") is not None:
                data = msg["text"].encode()
            if data:
                writer.write(data)
                await writer.drain()

    async def tcp_to_ws():
        while True:
            data = await reader.read(65536)
            if not data:
                return
            await ws.send_bytes(data)

    tasks = [asyncio.create_task(ws_to_tcp()), asyncio.create_task(tcp_to_ws())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        writer.close()
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if NOVNC_DIR.exists():
    app.mount("/novnc", StaticFiles(directory=NOVNC_DIR, html=True), name="novnc")
