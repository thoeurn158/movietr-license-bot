# -*- coding: utf-8 -*-
"""
Telegram License Manager Bot for Movie TR AI Tool
Enables Admin (@TiengThoeurn) to approve and generate License Keys directly on mobile phone 24/7 without opening PC.
"""

import os
import sys
import json
import time
import re
import base64
import hashlib
import hmac
from datetime import datetime, timedelta
import requests
import http.server
import socketserver
import threading
from urllib.parse import urlparse, parse_qs

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    os.chdir(BASE_DIR)
except Exception:
    pass

# Cryptographic Salt matching Movie_TR and license_manager
SECRET_SALT = "TR_AI_SECURE_KEY_2026_@KhmerMovieDubbing#PRO"

# Bot Configuration file
CONFIG_FILE = os.path.join(BASE_DIR, "bot_config.json")

def load_config():
    cfg = {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", "8848157189:AAGzV9rJNXFn5T8NOiLWP3em06QRDmGgzCY"),
        "admin_chat_id": os.environ.get("ADMIN_CHAT_ID", "1380452891"),
        "admin_username": "TiengThoeurn",
        "secret_admin_pin": "TR2026",
        "api_port": 8080
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                cfg.update(loaded)
        except Exception as e:
            print(f"Error loading {CONFIG_FILE}: {e}")
    return cfg

def load_revoked_hwids():
    try:
        import license_manager
        return license_manager.load_revoked_hwids()
    except Exception:
        rev_file = os.path.join(BASE_DIR, "revoked_licenses.json")
        if os.path.exists(rev_file):
            try:
                with open(rev_file, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                pass
        return set()

def save_revoked_hwid(hwid):
    try:
        import license_manager
        license_manager.add_revoked_hwid(hwid)
        return
    except Exception:
        rev = load_revoked_hwids()
        rev.add(hwid.upper().strip())
        rev_file = os.path.join(BASE_DIR, "revoked_licenses.json")
        try:
            with open(rev_file, "w", encoding="utf-8") as f:
                json.dump(list(rev), f, indent=4)
        except Exception:
            pass

def remove_revoked_hwid(hwid):
    try:
        import license_manager
        license_manager.remove_revoked_hwid(hwid)
        return
    except Exception:
        rev = load_revoked_hwids()
        rev.discard(hwid.upper().strip())
        rev_file = os.path.join(BASE_DIR, "revoked_licenses.json")
        try:
            with open(rev_file, "w", encoding="utf-8") as f:
                json.dump(list(rev), f, indent=4)
        except Exception:
            pass

def load_license_history():
    try:
        import license_manager
        return license_manager.load_license_history()
    except Exception:
        h_file = os.path.join(BASE_DIR, "license_history.json")
        if os.path.exists(h_file):
            try:
                with open(h_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

def save_license_history(history):
    try:
        import license_manager
        license_manager.save_license_history(history)
        return
    except Exception:
        h_file = os.path.join(BASE_DIR, "license_history.json")
        try:
            with open(h_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

def record_license_to_history(machine_id, user_name, expiry_date, plan, key, duration="", notes="", channel=""):
    try:
        import license_manager
        license_manager.record_license_to_history(machine_id, user_name, expiry_date, plan, key, duration, notes, channel)
        return
    except Exception:
        hist = load_license_history()
        entry = {
            "id": f"LIC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": str(user_name).strip(),
            "machine_id": str(machine_id).upper().strip(),
            "plan": str(plan).strip(),
            "duration": duration,
            "expiry_date": str(expiry_date).strip(),
            "key": str(key).strip(),
            "notes": notes,
            "channel": channel
        }
        hist.insert(0, entry)
        save_license_history(hist)

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {CONFIG_FILE}: {e}")

def generate_license_key(machine_id, user_name, expiry_date, plan="VIP"):
    """Generate cryptographically signed license key."""
    payload_obj = {
        "m": str(machine_id).upper().strip(),
        "u": str(user_name).strip(),
        "e": str(expiry_date).strip(),
        "p": str(plan).strip()
    }
    payload_str = json.dumps(payload_obj, separators=(',', ':'), ensure_ascii=False)
    payload_b64 = base64.urlsafe_b64encode(payload_str.encode('utf-8')).decode('utf-8').rstrip('=')
    sig = hmac.new(SECRET_SALT.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()[:16].upper()
    return f"TRVIP-{payload_b64}-{sig}"

class LicenseHttpHandler(http.server.BaseHTTPRequestHandler):
    bot_instance = None

    def log_message(self, format, *args):
        # Quiet logger for background server
        pass

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path in ["/", "/health", "/stats", "/users"]:
            hist = load_license_history()
            revoked = load_revoked_hwids()
            active_list = []
            for h in hist:
                mid = h.get("machine_id", "").upper().strip()
                if mid and mid not in revoked and h.get("status") != "revoked":
                    active_list.append({
                        "hwid": mid,
                        "customer": h.get("customer_name", "User"),
                        "expiry": h.get("expiry_date", ""),
                        "duration": h.get("duration", "")
                    })
            self._send_json(200, {
                "status": "ok",
                "service": "Movie TR Cloud License Auto-Activation Service",
                "admin": "@TiengThoeurn",
                "active_count": len(active_list),
                "revoked_count": len(revoked),
                "total_history": len(hist),
                "active_users": active_list
            })
            return

        if path == "/revoke":
            hwid_list = params.get("hwid", [])
            if not hwid_list:
                self._send_json(400, {"status": "error", "message": "Missing hwid parameter"})
                return
            hwid = hwid_list[0].upper().strip()
            if self.bot_instance:
                self.bot_instance.revoke_license(hwid)
            self._send_json(200, {"status": "revoked", "hwid": hwid, "message": "License revoked successfully"})
            return

        if path == "/check":
            hwid_list = params.get("hwid", [])
            if not hwid_list:
                self._send_json(400, {"status": "error", "message": "Missing hwid parameter"})
                return
            hwid = hwid_list[0].upper().strip()

            # Always sync persistent revoked list from disk
            disk_revoked = load_revoked_hwids()

            # 1. Check fresh state from license_history.json
            found_item = None
            is_revoked_in_file = False
            for h_item in load_license_history():
                m = h_item.get("machine_id", "").upper().strip()
                if m == hwid:
                    if h_item.get("status") == "revoked":
                        is_revoked_in_file = True
                        break
                    else:
                        found_item = h_item
                        break

            # If explicitly revoked either in file or in persistent disk list
            if is_revoked_in_file or hwid in disk_revoked:
                if self.bot_instance:
                    if hasattr(self.bot_instance, "revoked_hwids"):
                        self.bot_instance.revoked_hwids.add(hwid)
                    if hwid in self.bot_instance.approved_licenses:
                        del self.bot_instance.approved_licenses[hwid]
                self._send_json(200, {
                    "status": "revoked",
                    "hwid": hwid,
                    "message": "License has been revoked by Admin"
                })
                return

            # If not revoked and has active record in file -> APPROVED!
            if found_item:
                if self.bot_instance:
                    if hasattr(self.bot_instance, "revoked_hwids"):
                        self.bot_instance.revoked_hwids.discard(hwid)
                    self.bot_instance.approved_licenses[hwid] = found_item
                self._send_json(200, {
                    "status": "approved",
                    "hwid": hwid,
                    "key": found_item.get("key", ""),
                    "customer_name": found_item.get("customer_name", "VIP"),
                    "plan": found_item.get("plan", "VIP"),
                    "expiry_date": found_item.get("expiry_date", ""),
                    "duration": found_item.get("duration", "")
                })
                return

            # If in bot memory revoked
            if self.bot_instance and hasattr(self.bot_instance, "revoked_hwids") and hwid in self.bot_instance.revoked_hwids:
                self._send_json(200, {
                    "status": "revoked",
                    "hwid": hwid,
                    "message": "License has been revoked by Admin"
                })
                return

            # If removed from file, purge from memory cache
            if self.bot_instance and hwid in self.bot_instance.approved_licenses:
                del self.bot_instance.approved_licenses[hwid]

            self._send_json(200, {
                "status": "pending",
                "hwid": hwid,
                "message": "Waiting for Admin approval"
            })
            return

        self._send_json(404, {"status": "not_found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/revoke":
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode('utf-8'))
            except Exception:
                data = {}
            hwid = data.get("hwid", "").upper().strip()
            if hwid and self.bot_instance:
                self.bot_instance.revoke_license(hwid)
                self._send_json(200, {"status": "revoked", "hwid": hwid, "message": "License revoked"})
                return
            self._send_json(400, {"status": "error", "message": "Missing hwid"})
            return

        if path == "/request":
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body.decode('utf-8'))
            except Exception:
                data = {}

            hwid = data.get("hwid", "").upper().strip()
            raw_user = data.get("user_name", "").strip() or data.get("telegram_user", "").strip()
            
            # Extract clean Telegram username if user entered @username
            clean_username = ""
            user_display = raw_user
            if "@" in raw_user:
                m_tg = re.search(r'@([A-Za-z0-9_]{3,32})', raw_user)
                if m_tg:
                    clean_username = m_tg.group(1)
            
            if not user_display or user_display.lower() in ["susu", "admin", "user", "owner", "desktop", "laptop"]:
                user_display = "អតិថិជន VIP"

            if not hwid:
                self._send_json(400, {"status": "error", "message": "Missing hwid"})
                return

            if self.bot_instance:
                self.bot_instance.handle_customer_request(
                    chat_id=0,
                    user_name=user_display,
                    username=clean_username,
                    hwid=hwid,
                    is_online=True
                )
                self._send_json(200, {
                    "status": "submitted",
                    "hwid": hwid,
                    "message": "Request forwarded to Admin Telegram"
                })
                return

        self._send_json(404, {"status": "not_found"})

class TelegramLicenseBot:
    def __init__(self):
        self.config = load_config()
        self.bot_token = self.config.get("bot_token", "").strip()
        self.admin_chat_id = str(self.config.get("admin_chat_id", "")).strip()
        self.pending_requests = {} # req_id -> {customer_chat_id, user_name, username, hwid, time}
        self.approved_licenses = {} # hwid -> {key, customer_name, plan, expiry_date, duration}
        self.revoked_hwids = set()
        self.last_update_id = 0
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

        # Preload approved licenses and persistent revoked licenses
        try:
            self.revoked_hwids.update(load_revoked_hwids())
            for item in load_license_history():
                m_id = item.get("machine_id", "").upper().strip()
                if m_id:
                    if item.get("status") == "revoked":
                        self.revoked_hwids.add(m_id)
                        save_revoked_hwid(m_id)
                    elif m_id not in self.revoked_hwids:
                        self.approved_licenses[m_id] = item
            print(f"Loaded {len(self.approved_licenses)} active and {len(self.revoked_hwids)} revoked licenses.")
        except Exception as e:
            print(f"Notice: preloading history: {e}")

        # Start background HTTP Server for Auto-Activation
        self.start_http_server()

    def revoke_license(self, hwid):
        hwid = hwid.upper().strip()
        if not hasattr(self, "revoked_hwids"):
            self.revoked_hwids = set()
        self.revoked_hwids.add(hwid)
        if hwid in self.approved_licenses:
            del self.approved_licenses[hwid]
        try:
            save_revoked_hwid(hwid)
            hist = load_license_history()
            updated = []
            for item in hist:
                if item.get("machine_id", "").upper().strip() == hwid:
                    item["status"] = "revoked"
                    item["revoked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                updated.append(item)
            save_license_history(updated)
        except Exception as e:
            print(f"Error saving revoked license: {e}")

    def start_http_server(self):
        LicenseHttpHandler.bot_instance = self
        port = int(os.environ.get("PORT", self.config.get("api_port", 8080)))

        class ReusableTCPServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True

        def run_server():
            try:
                with ReusableTCPServer(("0.0.0.0", port), LicenseHttpHandler) as httpd:
                    print(f"🚀 Auto-Activation API Server running on port {port} (0.0.0.0:{port})")
                    httpd.serve_forever()
            except Exception as e:
                print(f"HTTP Server warning: {e}")

        t = threading.Thread(target=run_server, daemon=True)
        t.start()

    def send_api(self, method, payload):
        try:
            r = requests.post(f"{self.api_url}/{method}", json=payload, timeout=20)
            return r.json()
        except Exception as e:
            print(f"API Error ({method}): {e}")
            return {"ok": False, "error": str(e)}

    def send_message(self, chat_id, text, reply_markup=None, parse_mode="Markdown"):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.send_api("sendMessage", payload)

    def edit_message(self, chat_id, message_id, text, reply_markup=None, parse_mode="Markdown"):
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.send_api("editMessageText", payload)

    def answer_callback(self, callback_id, text=""):
        return self.send_api("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": text
        })

    def handle_customer_request(self, chat_id, user_name, username, hwid, is_online=False):
        req_id = f"req_{int(time.time())}_{chat_id}"
        self.pending_requests[req_id] = {
            "chat_id": chat_id,
            "user_name": user_name,
            "username": username,
            "hwid": hwid,
            "is_online": is_online,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Case 1: If the sender IS the Admin testing or generating for themselves/customer
        if self.admin_chat_id and str(chat_id) == str(self.admin_chat_id):
            admin_msg = (
                f"👑 *[ផ្ទាំងបង្កើត License Key ដោយផ្ទាល់ - Admin]*\n\n"
                f"💻 *Machine ID:* `{hwid}`\n"
                f"👤 *អ្នកស្នើ:* លោក Admin (@{username or 'TiengThoeurn'})\n"
                f"⏰ *កាលបរិច្ឆេទ:* {datetime.now().strftime('%H:%M:%S • %d/%m/%Y')}\n\n"
                f"👉 *សូមចុចជ្រើសរើសរយៈពេល License Key ដែលលោកចង់បង្កើត៖*"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "👑 30 ថ្ងៃ", "callback_data": f"appr:{req_id}:30"},
                        {"text": "👑 90 ថ្ងៃ", "callback_data": f"appr:{req_id}:90"}
                    ],
                    [
                        {"text": "👑 1 ឆ្នាំ (365 ថ្ងៃ)", "callback_data": f"appr:{req_id}:365"},
                        {"text": "💎 មួយជីវិត (Lifetime)", "callback_data": f"appr:{req_id}:LIFETIME"}
                    ],
                    [
                        {"text": "❌ បោះបង់ (Cancel)", "callback_data": f"rej:{req_id}"}
                    ]
                ]
            }
            self.send_message(chat_id, admin_msg, reply_markup=keyboard)
            return

        # Case 2: Customer request
        if not is_online and chat_id:
            admin_mention = f"@{self.config.get('admin_username', 'TiengThoeurn')}"
            cust_msg = (
                f"⏳ *សំណើសុំ License Key ត្រូវបានបញ្ជូនទៅ Admin រួចរាល់!*\n\n"
                f"💻 *Machine ID:* `{hwid}`\n"
                f"👤 *គណនីរបស់អ្នក:* {user_name} (@{username or 'គ្មាន'})\n\n"
                f"👉 សូមទាក់ទងទូទាត់ប្រាក់ជាមួយ Admin: {admin_mention}\n\n"
                f"🔔 _បន្ទាប់ពី Admin បានពិនិត្យ និងអនុម័តរួច កម្មវិធី Movie TR របស់អ្នកនឹង Auto-Activate បើកដំណើរការដោយស្វ័យប្រវត្តិតែម្តង!_"
            )
            self.send_message(chat_id, cust_msg)

        # Notify Admin
        if self.admin_chat_id:
            request_source = "ពីក្នុងកម្មវិធី Movie TR (Auto-Activate)" if is_online else "តាមរយៈ Telegram Bot"
            display_tg_user = f"{user_name} (@{username})" if (username and f"@{username}" not in user_name) else user_name
            admin_msg = (
                f"🔔 *[មានសំណើបើកសិទ្ធិប្រើប្រាស់ថ្មី]*\n\n"
                f"💻 *Machine ID:* `{hwid}`\n"
                f"👤 *អតិថិជន (Telegram):* {display_tg_user}\n"
                f"📡 *ប្រភព:* {request_source}\n"
                f"⏰ *ម៉ោងស្នើសុំ:* {datetime.now().strftime('%H:%M:%S • %d/%m/%Y')}\n\n"
                f"👉 _លោក Admin គ្រាន់តែចុចប៊ូតុងខាងក្រោម កម្មវិធី Movie TR លើ PC អតិថិជននឹងបើកដំណើរការភ្លាមៗ (Auto-Activate មិនបាច់វាយ Key)៖_"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "👑 30 ថ្ងៃ", "callback_data": f"appr:{req_id}:30"},
                        {"text": "👑 90 ថ្ងៃ", "callback_data": f"appr:{req_id}:90"}
                    ],
                    [
                        {"text": "👑 1 ឆ្នាំ (365 ថ្ងៃ)", "callback_data": f"appr:{req_id}:365"},
                        {"text": "💎 មួយជីវិត (Lifetime)", "callback_data": f"appr:{req_id}:LIFETIME"}
                    ],
                    [
                        {"text": "❌ បដិសេធ (Reject)", "callback_data": f"rej:{req_id}"}
                    ]
                ]
            }
            self.send_message(self.admin_chat_id, admin_msg, reply_markup=keyboard)
        else:
            print("Notice: admin_chat_id is not set.")

    def handle_admin_callback(self, callback_id, from_id, message_id, data):
        if str(from_id) != str(self.admin_chat_id):
            self.answer_callback(callback_id, "⚠️ អ្នកមិនមែនជា Admin ទេ!")
            return

        parts = data.split(":")
        action = parts[0]
        req_id = parts[1]

        req = self.pending_requests.get(req_id)
        if not req:
            self.answer_callback(callback_id, "⚠️ សំណើនេះត្រូវបានដំណើរការរួចរាល់ ឬផុតកំណត់!")
            return

        cust_chat_id = req["chat_id"]
        hwid = req["hwid"]
        cust_name = req["user_name"]
        is_online = req.get("is_online", False)
        is_admin_self = (str(cust_chat_id) == str(self.admin_chat_id))

        if action == "rej":
            self.answer_callback(callback_id, "❌ បានបដិសេធ/បោះបង់")
            self.edit_message(
                self.admin_chat_id, message_id,
                f"❌ *បានបោះបង់សំណើសម្រាប់:* {cust_name}\n💻 Machine ID: `{hwid}`"
            )
            if not is_admin_self and cust_chat_id:
                self.send_message(
                    cust_chat_id,
                    f"⚠️ *ការស្នើសុំ License Key របស់អ្នកមិនត្រូវបានអនុម័តឡើយ។*\n\n"
                    f"សូមទាក់ទងមកកាន់ Admin: @{self.config.get('admin_username', 'TiengThoeurn')} ដើម្បីដោះស្រាយ។"
                )
            del self.pending_requests[req_id]
            return

        if action == "appr":
            duration = parts[2]
            if duration == "LIFETIME":
                exp_date = "LIFETIME"
                exp_khmer = "ពេញមួយជីវិត (Lifetime)"
            else:
                days = int(duration)
                exp_dt = datetime.now() + timedelta(days=days)
                exp_date = exp_dt.strftime("%Y-%m-%d")
                exp_khmer = f"{days} ថ្ងៃ (ដល់ {exp_date})"

            # Generate Cryptographic License Key
            username = req.get("username", "").strip()
            if is_admin_self:
                key_username = f"Admin (@{self.config.get('admin_username', 'TiengThoeurn')})"
            elif username and f"@{username}" not in cust_name:
                key_username = f"{cust_name} (@{username})"
            else:
                key_username = cust_name

            key = generate_license_key(hwid, key_username, exp_date, plan="VIP")
            # Clear from revoked list if previously revoked
            if hasattr(self, "revoked_hwids") and hwid in self.revoked_hwids:
                self.revoked_hwids.remove(hwid)
            try:
                remove_revoked_hwid(hwid)
            except Exception:
                pass

            # 1. Save to approved_licenses memory cache for instant Auto-Activation!
            self.approved_licenses[hwid] = {
                "key": key,
                "customer_name": key_username,
                "plan": "VIP",
                "expiry_date": exp_date,
                "duration": exp_khmer
            }

            # 2. Record to unified license history
            try:
                channel_name = "App Auto-Activation" if is_online else "Telegram Bot"
                record_license_to_history(
                    hwid, key_username, exp_date, "VIP", key,
                    duration=exp_khmer, notes=f"Approved by Admin ({channel_name})",
                    channel=channel_name
                )
            except Exception as ex:
                print(f"Error logging to history: {ex}")

            self.answer_callback(callback_id, f"✅ បានអនុម័ត {exp_khmer}")

            # 3. Update message for Admin
            self.edit_message(
                self.admin_chat_id, message_id,
                f"✅ *បានអនុម័ត និងបើកសិទ្ធិ (Auto-Activate) ជោគជ័យ!*\n\n"
                f"👤 *ឈ្មោះ:* {key_username}\n"
                f"👑 *គម្រោង:* VIP ({exp_khmer})\n"
                f"💻 *Machine ID:* `{hwid}`\n\n"
                f"✨ *ស្ថានភាព:* កម្មវិធី Movie TR លើ PC អតិថិជននឹង Unlock បើកដំណើរការដោយស្វ័យប្រវត្តិតែម្តង (មិនបាច់ Copy ឬ Paste Key ឡើយ)!\n\n"
                f"🔑 *LICENSE KEY:*\n`{key}`\n\n"
                f"*(👉 ចុចលើ Key ខាងលើដើម្បី Copy ប្រសិនបើតម្រូវការ)*"
            )

            # 4. If customer requested via Telegram, also notify them
            if not is_admin_self and cust_chat_id:
                cust_success_msg = (
                    f"🎉 *ការស្នើសុំ License Key ត្រូវបាន Admin អនុម័តជោគជ័យ!*\n\n"
                    f"✨ កម្មវិធី Movie TR លើកុំព្យូទ័ររបស់អ្នកបានបើកដំណើរការ (Auto-Activate) រួចរាល់ហើយ!\n\n"
                    f"👑 *គម្រោង:* VIP\n"
                    f"📅 *សុពលភាព:* {exp_khmer}\n"
                    f"💻 *សម្រាប់ម៉ាស៊ីន:* `{hwid}`\n\n"
                    f"🔑 *License Key សម្ងាត់ (រក្សាទុកជាឯកសារយោង):*\n`{key}`"
                )
                self.send_message(cust_chat_id, cust_success_msg)

            del self.pending_requests[req_id]

    def handle_admin_command(self, chat_id, text):
        parts = text.strip().split()
        cmd = parts[0].lower()

        if cmd == "/admin":
            if len(parts) > 1 and parts[1] == self.config.get("secret_admin_pin", "TR2026"):
                self.admin_chat_id = str(chat_id)
                self.config["admin_chat_id"] = self.admin_chat_id
                save_config(self.config)
                self.send_message(
                    chat_id,
                    f"👑 *សូមស្វាគមន៍ Admin @{self.config.get('admin_username')}!*\n\n"
                    f"Chat ID `{chat_id}` ត្រូវបានភ្ជាប់ជា Admin ជោគជ័យ។\n"
                    f"រាល់សំណើ License Key ពីអតិថិជននឹងលោតមកទីនេះភ្លាមៗ!"
                )
            else:
                self.send_message(chat_id, "⚠️ PIN មិនត្រឹមត្រូវឡើយ!")
            return

        if cmd == "/gen" and str(chat_id) == str(self.admin_chat_id):
            # Format: /gen <HWID> [CustomerName] [Days_or_LIFETIME]
            if len(parts) < 2:
                self.send_message(
                    chat_id,
                    "👉 *របៀបបង្កើត Key ដោយផ្ទាល់:*\n`/gen <Machine_ID> [ឈ្មោះ] [ចំនួនថ្ងៃ]`\n\n"
                    "ឧទាហរណ៍៖\n`/gen TR-2A18-3C06-C6A7-235D SokSan 30`\n"
                    "`/gen TR-2A18-3C06-C6A7-235D SokSan LIFETIME`"
                )
                return

            hwid = parts[1].upper().strip()
            user_name = parts[2] if len(parts) > 2 else "Customer"
            dur = parts[3].upper() if len(parts) > 3 else "365"

            if dur == "LIFETIME":
                exp_date = "LIFETIME"
                exp_khmer = "ពេញមួយជីវិត (Lifetime)"
            else:
                try:
                    days = int(dur)
                    exp_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
                    exp_khmer = f"{days} ថ្ងៃ (ដល់ {exp_date})"
                except Exception:
                    exp_date = dur
                    exp_khmer = f"ដល់ {exp_date}"

            key = generate_license_key(hwid, user_name, exp_date, plan="VIP")
            if hasattr(self, "revoked_hwids"):
                self.revoked_hwids.discard(hwid)
            try:
                import license_manager
                license_manager.remove_revoked_hwid(hwid)
            except Exception:
                pass

            # Record to history
            try:
                import license_manager
                license_manager.record_license_to_history(
                    hwid, user_name, exp_date, "VIP", key,
                    duration=exp_khmer, notes="Direct /gen Telegram command",
                    channel="Telegram Bot"
                )
            except Exception as ex:
                print(f"Error logging /gen to history: {ex}")
            resp = (
                f"🔑 *LICENSE KEY បានបង្កើតរួចរាល់:*\n\n"
                f"`{key}`\n\n"
                f"👤 *ឈ្មោះ:* {user_name}\n"
                f"📅 *សុពលភាព:* {exp_khmer}\n"
                f"💻 *Machine ID:* `{hwid}`"
            )
            self.send_message(chat_id, resp)
            return

        if (cmd == "/revoke" or cmd == "/block") and str(chat_id) == str(self.admin_chat_id):
            if len(parts) < 2:
                self.send_message(
                    chat_id,
                    "👉 *របៀបផ្តាច់សិទ្ធិ License:*\n`/revoke <Machine_ID>`\n\n"
                    "ឧទាហរណ៍៖\n`/revoke TR-2A18-3C06-C6A7-235D`"
                )
                return
            target_hwid = parts[1].upper().strip()
            self.revoke_license(target_hwid)
            self.send_message(
                chat_id,
                f"🚫 *បានផ្តាច់ និងបិទសិទ្ធិ (Revoked) ជោគជ័យ!*\n\n"
                f"💻 *Machine ID:* `{target_hwid}`\n\n"
                f"✨ កម្មវិធី Movie TR លើកុំព្យូទ័រនោះ នឹងត្រូវចាក់សោ (Lock) ភ្លាមៗតែម្តង!"
            )
            return

        if cmd in ["/users", "/stats", "/list"] and str(chat_id) == str(self.admin_chat_id):
            hist = load_license_history()
            revoked = load_revoked_hwids()
            active_list = []
            for h in hist:
                mid = h.get("machine_id", "").upper().strip()
                if mid and mid not in revoked and h.get("status") != "revoked":
                    active_list.append(h)

            lines = [
                f"📊 *ស្ថិតិអ្នកប្រើប្រាស់ Movie TR AI Tool:*\n",
                f"👥 *ចំនួន PC កំពុងដំណើរការ (Active):* `{len(active_list)}` គ្រឿង",
                f"🚫 *ចំនួន PC ត្រូវបានបិទ (Revoked):* `{len(revoked)}` គ្រឿង",
                f"📁 *ប្រវត្តិសរុប:* `{len(hist)}` កំណត់ត្រា\n"
            ]
            if active_list:
                lines.append("📋 *បញ្ជី PC ដែលកំពុងដំណើរការ (ចុងក្រោយ):*")
                for idx, act in enumerate(active_list[:15], 1):
                    c_name = act.get("customer_name", "User")
                    m_id = act.get("machine_id", "")
                    exp = act.get("expiry_date", "")
                    lines.append(f"{idx}️⃣ *{c_name}* (`{m_id}`) • ដល់: {exp}")
            else:
                lines.append("ℹ️ _មិនទាន់មាន PC ណាមួយកំពុងដំណើរការនៅឡើយទេ។_")

            self.send_message(chat_id, "\n".join(lines))
            return

        if cmd in ["/unrevoke", "/restore", "/unblock"] and str(chat_id) == str(self.admin_chat_id):
            if len(parts) < 2:
                self.send_message(chat_id, "👉 *របៀបបើកសិទ្ធិឡើងវិញ:*\n`/unrevoke <Machine_ID>`")
                return
            target_hwid = parts[1].upper().strip()
            if hasattr(self, "revoked_hwids"):
                self.revoked_hwids.discard(target_hwid)
            remove_revoked_hwid(target_hwid)
            hist = load_license_history()
            for h in hist:
                if h.get("machine_id", "").upper().strip() == target_hwid:
                    h["status"] = "active"
            save_license_history(hist)
            self.send_message(
                chat_id,
                f"✅ *បានបើកសិទ្ធិ (Unrevoked) ឡើងវិញជោគជ័យ!*\n\n"
                f"💻 *Machine ID:* `{target_hwid}`\n"
                f"✨ កម្មវិធី Movie TR លើកុំព្យូទ័រនោះ អាចប្រើប្រាស់ឡើងវិញបានធម្មតា!"
            )
            return

    def process_update(self, update):
        # 1. Callback Query (Admin taps approval buttons)
        if "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb["id"]
            from_id = cb["from"]["id"]
            msg_id = cb["message"]["message_id"]
            data = cb["data"]
            self.handle_admin_callback(cb_id, from_id, msg_id, data)
            return

        # 2. Text Message
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "").strip()
            user_obj = msg.get("from", {})
            first_name = user_obj.get("first_name", "")
            last_name = user_obj.get("last_name", "")
            user_name = f"{first_name} {last_name}".strip() or "User"
            username = user_obj.get("username", "")

            if not text:
                return

            # Commands
            if text.startswith("/"):
                if text.startswith("/start"):
                    if self.admin_chat_id and str(chat_id) == str(self.admin_chat_id):
                        welcome = (
                            f"👑 *សូមស្វាគមន៍លោក Admin @{self.config.get('admin_username', 'TiengThoeurn')}!*\n\n"
                            f"🟢 *ស្ថានភាព Bot:* កំពុងដំណើរការ (Online 100%)\n"
                            f"🆔 *Chat ID របស់អ្នក:* `{chat_id}`\n\n"
                            f"✨ *របៀបប្រើប្រាស់លើទូរស័ព្ទដៃ:*\n"
                            f"1️⃣ *ពេលអតិថិជនផ្ញើ Machine ID មក:* Bot នឹងលោតសារជូនដំណឹងភ្លាមៗ រួមជាមួយប៊ូតុងចុចអនុម័ត 30 ថ្ងៃ, 90 ថ្ងៃ, 1 ឆ្នាំ, មួយជីវិត។\n"
                            f"2️⃣ *បង្កើត Key ដោយផ្ទាល់:* Paste លេខ Machine ID មកទីនេះ ឬវាយ `/gen <Machine_ID> [ឈ្មោះ] [ចំនួនថ្ងៃ]`\n"
                            f"3️⃣ *ដឹងចំនួនអ្នកប្រើ:* វាយ `/users` ឬ `/stats` ដើម្បីមើលចំនួន PC កំពុងដំណើរការ\n"
                            f"4️⃣ *បិទសិទ្ធិ (Lock):* វាយ `/revoke <Machine_ID>` (PC នោះនឹងត្រូវ Lock ភ្លាម)\n"
                            f"5️⃣ *បើកសិទ្ធិវិញ:* វាយ `/unrevoke <Machine_ID>`"
                        )
                    else:
                        welcome = (
                            f"🎬 *សូមស្វាគមន៍មកកាន់ប្រព័ន្ធ License Movie TR AI Dubbing Tool!*\n\n"
                            f"👉 ដើម្បីទទួលបាន ឬបន្ត License Key សូម Copy លេខសម្គាល់កុំព្យូទ័រ (*Machine ID*) របស់អ្នកពីក្នុងកម្មវិធី Movie TR រួច Paste ផ្ញើមកកាន់ទីនេះ។\n\n"
                            f"ឧទាហរណ៍៖ `TR-2A18-3C06-C6A7-235D`"
                        )
                    self.send_message(chat_id, welcome)
                    return
                else:
                    self.handle_admin_command(chat_id, text)
                    return

            # Check if text contains a Machine ID: TR-XXXX-XXXX-XXXX-XXXX
            m = re.search(r'(TR-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4})', text.upper())
            if m:
                extracted_hwid = m.group(1)
                self.handle_customer_request(chat_id, user_name, username, extracted_hwid)
            else:
                self.send_message(
                    chat_id,
                    "⚠️ *សូមផ្ញើលេខ Machine ID ឱ្យបានត្រឹមត្រូវ!*\n"
                    "ទម្រង់ត្រឹមត្រូវគឺ៖ `TR-XXXX-XXXX-XXXX-XXXX`\n\n"
                    "👉 បើកកម្មវិធី Movie TR រួចចុចប៊ូតុង *[ 📋 ចម្លង (Copy ID) ]* ឬ *[ ✈️ ផ្ញើទៅ Telegram Admin ]* ជាការស្រេច។"
                )

    def run(self):
        if not self.bot_token:
            print("================================================================")
            print("⚠️ TELEGRAM BOT TOKEN មិនទាន់បានកំណត់នៅឡើយទេ!")
            print("សូមបញ្ចូល Bot Token ពី @BotFather នៅក្នុង bot_config.json")
            print("================================================================")
            return

        print("================================================================")
        print("🚀 Telegram License Bot កំពុងដំណើរការ...")
        print(f"Admin Username: @{self.config.get('admin_username')}")
        print(f"Admin Chat ID: {self.admin_chat_id or 'មិនទាន់ភ្ជាប់ (សូមផ្ញើ /admin TR2026 ទៅកាន់ Bot)'}")
        print("================================================================")

        while True:
            try:
                r = requests.get(
                    f"{self.api_url}/getUpdates",
                    params={"offset": self.last_update_id + 1, "timeout": 30},
                    timeout=40
                )
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        self.last_update_id = update["update_id"]
                        self.process_update(update)
                else:
                    err_desc = data.get("description", "Unknown error")
                    err_code = data.get("error_code", 0)
                    print(f"⚠️ Telegram API notice [{err_code}]: {err_desc}")
                    time.sleep(5)
            except requests.exceptions.RequestException as e:
                time.sleep(3)
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(2)

if __name__ == "__main__":
    bot = TelegramLicenseBot()
    bot.run()
