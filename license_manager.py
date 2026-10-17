# -*- coding: utf-8 -*-
import os
import sys
import json
import base64
import hashlib
import hmac
import re
try:
    import winreg
except ImportError:
    winreg = None
import subprocess
from datetime import datetime

# Secret Salt for cryptographic HMAC-SHA256 signature
SECRET_SALT = "TR_AI_SECURE_KEY_2026_@KhmerMovieDubbing#PRO"

_CACHED_HWID = None
_CACHED_SYS_UUID = None

def get_machine_guid():
    """Retrieve Windows Cryptography MachineGuid."""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        if guid and str(guid).strip():
            return str(guid).strip()
    except Exception:
        pass
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ)
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        if guid and str(guid).strip():
            return str(guid).strip()
    except Exception:
        pass
    return ""

def get_system_uuid():
    """Retrieve motherboard/system UUID via WMIC or PowerShell (Fast & Cached)."""
    global _CACHED_SYS_UUID
    if _CACHED_SYS_UUID is not None:
        return _CACHED_SYS_UUID

    # 1. Try WMIC first (fastest on Windows 10/11, ~0.05s)
    try:
        output = subprocess.check_output(
            ["wmic", "csproduct", "get", "uuid"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            text=True,
            timeout=2
        ).strip().splitlines()
        for line in output:
            l = line.strip()
            if l and "uuid" not in l.lower() and l.lower() != "none":
                _CACHED_SYS_UUID = l
                return _CACHED_SYS_UUID
    except Exception:
        pass

    # 2. Try PowerShell CimInstance (with strict timeout)
    try:
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            text=True,
            timeout=4
        ).strip()
        if output and output.lower() != "none":
            _CACHED_SYS_UUID = output
            return _CACHED_SYS_UUID
    except Exception:
        pass

    # 3. Fallback to Windows Registry BIOS/Motherboard product info if available
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS", 0, winreg.KEY_READ)
        vals = []
        for vname in ["BaseBoardProduct", "BaseBoardSerialNumber", "SystemProductName", "SystemManufacturer"]:
            try:
                v, _ = winreg.QueryValueEx(key, vname)
                if v and str(v).strip():
                    vals.append(str(v).strip())
            except Exception:
                pass
        winreg.CloseKey(key)
        if vals:
            _CACHED_SYS_UUID = "_".join(vals)
            return _CACHED_SYS_UUID
    except Exception:
        pass

    _CACHED_SYS_UUID = ""
    return ""

def get_hardware_id():
    """
    Generate a stable, unique Hardware Machine ID (HWID).
    Cached in memory to prevent repeated process spawns and timing discrepancies.
    Returns formatted ID: TR-XXXX-XXXX-XXXX-XXXX
    """
    global _CACHED_HWID
    if _CACHED_HWID is not None:
        return _CACHED_HWID

    # 1. Prefer previously saved/locked HWID on this system (100% immune to boot timing & WMIC timeout)
    stored = get_system_stored_hwid()
    if stored and (stored.startswith("TR-") or stored.startswith("TRDL-")) and len(stored) >= 19:
        _CACHED_HWID = stored
        return _CACHED_HWID

    m_guid = get_machine_guid()
    sys_uuid = get_system_uuid()
    
    if not m_guid and not sys_uuid:
        import uuid
        mac = str(uuid.getnode())
        raw = f"TR_AI_FALLBACK_{mac}"
    else:
        raw = f"TR_AI_{m_guid}_{sys_uuid}"
        
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    _CACHED_HWID = f"TR-{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"

    # Auto-save HWID immediately to Registry & LocalAppData so it remains permanent across boots
    try:
        if winreg:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Movie_TR")
            winreg.SetValueEx(key, "HardwareID", 0, winreg.REG_SZ, _CACHED_HWID)
            winreg.CloseKey(key)
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            lic_dir = os.path.join(appdata, "Movie_TR")
            os.makedirs(lic_dir, exist_ok=True)
            with open(os.path.join(lic_dir, "hardware_id.txt"), "w", encoding="utf-8") as f:
                f.write(_CACHED_HWID)
    except Exception:
        pass

    return _CACHED_HWID

def save_license_to_system(key_str, hwid=None):
    """
    Save the activated license key to Windows Registry (HKCU) and LocalAppData
    to guarantee it is never lost even if dubber_settings.json is moved or overwritten.
    """
    if not key_str or not isinstance(key_str, str):
        return
    clean_k = key_str.strip()
    if not clean_k:
        return

    # 1. Save to Windows Registry HKCU\Software\Movie_TR
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Movie_TR")
        winreg.SetValueEx(key, "LicenseKey", 0, winreg.REG_SZ, clean_k)
        if hwid:
            winreg.SetValueEx(key, "HardwareID", 0, winreg.REG_SZ, str(hwid).strip())
        winreg.CloseKey(key)
    except Exception:
        pass

    # 2. Save to %LOCALAPPDATA%\Movie_TR\license_key.txt
    try:
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            lic_dir = os.path.join(appdata, "Movie_TR")
            os.makedirs(lic_dir, exist_ok=True)
            with open(os.path.join(lic_dir, "license_key.txt"), "w", encoding="utf-8") as f:
                f.write(clean_k)
            if hwid:
                with open(os.path.join(lic_dir, "hardware_id.txt"), "w", encoding="utf-8") as f:
                    f.write(str(hwid).strip())
    except Exception:
        pass

def load_license_from_system():
    """
    Retrieve previously saved license key from Windows Registry or LocalAppData.
    """
    # 1. Check Windows Registry HKCU\Software\Movie_TR
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Movie_TR", 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, "LicenseKey")
        winreg.CloseKey(key)
        if val and str(val).strip():
            return str(val).strip()
    except Exception:
        pass

    # 2. Check %LOCALAPPDATA%\Movie_TR\license_key.txt
    try:
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            lic_file = os.path.join(appdata, "Movie_TR", "license_key.txt")
            if os.path.exists(lic_file):
                with open(lic_file, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                    if val:
                        return val
    except Exception:
        pass

    return ""

def remove_license_from_system():
    """
    Remove/Deactivate license key from Windows Registry and LocalAppData.
    """
    # 1. Remove from Windows Registry HKCU\Software\Movie_TR
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Movie_TR", 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, "LicenseKey")
        except Exception:
            pass
        winreg.CloseKey(key)
    except Exception:
        pass

    # 2. Remove %LOCALAPPDATA%\Movie_TR\license_key.txt
    try:
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            lic_file = os.path.join(appdata, "Movie_TR", "license_key.txt")
            if os.path.exists(lic_file):
                os.remove(lic_file)
    except Exception:
        pass

def get_system_stored_hwid():
    """Retrieve HWID saved during previous activation."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Movie_TR", 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, "HardwareID")
        winreg.CloseKey(key)
        if val and str(val).strip():
            return str(val).strip()
    except Exception:
        pass

    try:
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            hw_file = os.path.join(appdata, "Movie_TR", "hardware_id.txt")
            if os.path.exists(hw_file):
                with open(hw_file, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                    if val:
                        return val
    except Exception:
        pass

    return ""

def generate_license_key(machine_id, user_name, expiry_date, plan="VIP"):
    """
    Generate a cryptographically signed license key locked to the given machine_id.
    """
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

def get_valid_hardware_ids():
    """
    Returns a set of all valid hardware ID variations for this machine.
    This guarantees that even if WMIC / PowerShell timed out on a cold boot,
    the Key will never be rejected.
    """
    valid = set()
    stored = get_system_stored_hwid()
    if stored:
        valid.add(stored.upper().strip())

    m_guid = get_machine_guid()
    sys_uuid = get_system_uuid()

    if m_guid and sys_uuid:
        raw_full = f"TR_AI_{m_guid}_{sys_uuid}"
        h_full = hashlib.sha256(raw_full.encode("utf-8")).hexdigest().upper()
        valid.add(f"TR-{h_full[0:4]}-{h_full[4:8]}-{h_full[8:12]}-{h_full[12:16]}")

    if m_guid:
        raw_guid = f"TR_AI_{m_guid}_"
        h_guid = hashlib.sha256(raw_guid.encode("utf-8")).hexdigest().upper()
        valid.add(f"TR-{h_guid[0:4]}-{h_guid[4:8]}-{h_guid[8:12]}-{h_guid[12:16]}")

    try:
        import uuid
        mac = str(uuid.getnode())
        raw_mac = f"TR_AI_FALLBACK_{mac}"
        h_mac = hashlib.sha256(raw_mac.encode("utf-8")).hexdigest().upper()
        valid.add(f"TR-{h_mac[0:4]}-{h_mac[4:8]}-{h_mac[8:12]}-{h_mac[12:16]}")
    except Exception:
        pass

    return valid

def verify_license_key(key_str, current_machine_id=None):
    """
    Verify if a license key is valid, authentic, and matches current machine.
    Returns: (is_valid: bool, result_or_message: dict or str)
    """
    if not key_str or not isinstance(key_str, str):
        return False, "សូមបញ្ចូល License Key!"
        
    if current_machine_id is None:
        current_machine_id = get_hardware_id()
        
    clean_key = key_str.strip()
    if clean_key.startswith("TRDL-") or "TR_TOOL_DL" in clean_key:
        return False, (
            "⚠️ នេះជា License Key របស់កម្មវិធី TR TOOL DL (Video Downloader)!\n"
            "មិនអាចយកមកដំណើរការលើកម្មវិធី Movie TR (Movie Dubbing) បានទេ!\n\n"
            "សូមប្រើប្រាស់ Key សម្រាប់កម្មវិធី Movie TR ដែលផ្ដើមដោយ 'TRVIP-'។"
        )
    parts = clean_key.split('-')
    if len(parts) < 3 or parts[0] != "TRVIP":
        return False, "ទម្រង់ License Key មិនត្រឹមត្រូវ!"
        
    payload_b64 = parts[1]
    provided_sig = parts[2]
    
    pad = len(payload_b64) % 4
    if pad:
        payload_b64 += "=" * (4 - pad)
        
    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode('utf-8'))
        payload_str = payload_bytes.decode('utf-8')
        payload_obj = json.loads(payload_str)
    except Exception:
        return False, "មិនអាចអានទិន្នន័យ License Key បានទេ!"
        
    # Check HMAC signature
    expected_sig = hmac.new(SECRET_SALT.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()[:16].upper()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return False, "License Key ក្លែងក្លាយ ឬត្រូវបានកែប្រែដោយគ្មានការអនុញ្ញាត!"
        
    # Check Hardware Lock with Multi-HWID tolerance
    key_machine = payload_obj.get("m", "").upper().strip()
    cur_id = current_machine_id.upper().strip()
    valid_ids = get_valid_hardware_ids()

    # Check Revocation (Blacklist for Key, Signature, and Machine ID)
    try:
        revoked_set = load_revoked_keys()
        if clean_key in revoked_set or provided_sig in revoked_set:
            return False, "License Key នេះត្រូវបានផ្តាច់ (Revoked) ឬជំនួសដោយ Key ថ្មីរួចហើយ!\nសូមបញ្ចូល Key ថ្មីដែលមានសុពលភាព។"
        if cur_id in revoked_set or key_machine in revoked_set:
            return False, "License សម្រាប់ម៉ាស៊ីននេះត្រូវបានផ្តាច់ និងបិទសិទ្ធិ (Revoked) ដោយ Admin រួចហើយ!"
    except Exception:
        pass

    if key_machine in valid_ids or (cur_id and key_machine == cur_id):
        # Successfully matched one of the machine's hardware signatures!
        # Lock this exact hardware ID to the system so future checks remain instant and consistent
        save_license_to_system(clean_key, hwid=key_machine)
    else:
        return False, f"Key នេះមិនត្រូវគ្នាជាមួយម៉ាស៊ីននេះទេ!\n(Key សម្រាប់ម៉ាស៊ីន {key_machine}, ប៉ុន្តែម៉ាស៊ីននេះគឺ {current_machine_id})"
        
    # Check Expiry
    exp_str = payload_obj.get("e", "")
    if exp_str != "LIFETIME":
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            if today > exp_date:
                days_diff = (today - exp_date).days
                return False, f"License Key បានផុតកំណត់ហើយ ({days_diff} ថ្ងៃមុន)!\nថ្ងៃផុតកំណត់: {exp_str}"
        except Exception:
            return False, "កាលបរិច្ឆេទក្នុង Key មិនត្រឹមត្រូវ!"
            
    return True, payload_obj

# ==============================================================================
# License History Management & Statistics
# ==============================================================================

HISTORY_FILE_NAME = "license_history.json"

def get_history_file_path():
    """Get stable path to license history file."""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base_dir = os.getcwd()
    
    local_path = os.path.join(base_dir, HISTORY_FILE_NAME)
    return local_path

def load_license_history():
    """Load list of all issued licenses from history file."""
    path = get_history_file_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass

    # Fallback to LocalAppData if local not found
    appdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        appdata_path = os.path.join(appdata, "Movie_TR", HISTORY_FILE_NAME)
        if os.path.exists(appdata_path):
            try:
                with open(appdata_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
    return []

def merge_license_history(new_items):
    """Merge incoming history records with local history without duplicates."""
    if not isinstance(new_items, list) or not new_items:
        return load_license_history()
    local = load_license_history()
    existing_map = {}
    for item in local:
        mid = item.get("machine_id", "").upper().strip()
        existing_map[mid] = item

    modified = False
    for item in new_items:
        mid = item.get("machine_id", "").upper().strip()
        if not mid:
            continue
        if mid not in existing_map:
            local.insert(0, item)
            existing_map[mid] = item
            modified = True
        else:
            # Update fields if incoming has richer or newer data
            for k, v in item.items():
                if v and not existing_map[mid].get(k):
                    existing_map[mid][k] = v
                    modified = True

    if modified:
        save_license_history(local)
    return local

def sync_license_history_from_cloud(server_url="https://movietr-license-bot.onrender.com"):
    """Fetch all active licenses from Cloud Server and merge with local history."""
    try:
        import requests
        urls = [server_url, "https://movietr-license-bot.onrender.com"]
        urls = list(dict.fromkeys([u.strip() for u in urls if u and u.strip()]))
        for base in urls:
            try:
                # 1. Try /history
                r = requests.get(f"{base.rstrip('/')}/history", timeout=2.5)
                if r.status_code == 200:
                    d = r.json()
                    cloud_hist = d.get("history", [])
                    if cloud_hist:
                        return merge_license_history(cloud_hist)

                # 2. Try /users fallback
                r2 = requests.get(f"{base.rstrip('/')}/users", timeout=2.5)
                if r2.status_code == 200:
                    d2 = r2.json()
                    active_users = d2.get("active_users", [])
                    if active_users:
                        converted = []
                        for u in active_users:
                            hwid = u.get("hwid", "").upper().strip()
                            cust = u.get("customer", "VIP")
                            exp = u.get("expiry", "LIFETIME")
                            dur = u.get("duration", "")
                            if hwid:
                                k = generate_license_key(hwid, cust, exp, "VIP")
                                converted.append({
                                    "id": f"CLOUD-{hwid[-4:]}",
                                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "customer_name": cust,
                                    "machine_id": hwid,
                                    "plan": "VIP",
                                    "duration": dur,
                                    "expiry_date": exp,
                                    "key": k,
                                    "notes": "Synced from Cloud Telegram Bot",
                                    "channel": "Telegram Cloud",
                                    "status": "approved"
                                })
                        return merge_license_history(converted)
            except Exception:
                continue
    except Exception:
        pass
    return load_license_history()

def save_license_history(history_list):
    """Save updated history to disk and backup in LocalAppData."""
    if not isinstance(history_list, list):
        return False

    path = get_history_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history_list, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

    # Also backup to LocalAppData
    appdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        try:
            backup_dir = os.path.join(appdata, "Movie_TR")
            os.makedirs(backup_dir, exist_ok=True)
            with open(os.path.join(backup_dir, HISTORY_FILE_NAME), "w", encoding="utf-8") as f:
                json.dump(history_list, f, indent=4, ensure_ascii=False)
        except Exception:
            pass
    return True

def record_license_to_history(machine_id, user_name, expiry_date, plan, key, duration=None, notes="", channel="PC Generator", app=None):
    """
    Record an issued license to history.
    Automatically revokes/invalidates previous old keys for this machine_id ONLY within the same app,
    guaranteeing only the newest key remains active without affecting other applications.
    """
    history = load_license_history()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine app kind: "TR_TOOL_DL" or "Movie_TR"
    key_str = str(key).strip()
    mid_str = str(machine_id).upper().strip()
    if not app:
        app = "TR_TOOL_DL" if (key_str.startswith("TRDL-") or mid_str.startswith("TRDL-")) else "Movie_TR"

    # Determine duration label if not given
    if not duration:
        if expiry_date == "LIFETIME":
            duration = "មួយជីវិត (Lifetime)"
        else:
            try:
                exp_dt = datetime.strptime(expiry_date, "%Y-%m-%d").date()
                days_left = (exp_dt - datetime.now().date()).days
                duration = f"{days_left} ថ្ងៃ"
            except Exception:
                duration = expiry_date

    entry = {
        "id": f"LIC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(history)+1:03d}",
        "created_at": now_str,
        "customer_name": str(user_name).strip() or "Customer",
        "machine_id": mid_str,
        "app": str(app).strip(),
        "plan": str(plan).strip().upper() or "VIP",
        "duration": duration,
        "expiry_date": str(expiry_date).strip(),
        "key": key_str,
        "status": "active",
        "notes": notes,
        "channel": channel
    }

    norm_mid = mid_str
    norm_app = entry["app"]
    prev_keys_to_revoke = []
    updated = False

    for i, item in enumerate(history):
        item_mid = str(item.get("machine_id", "")).upper().strip()
        item_k = str(item.get("key", "")).strip()
        item_app = str(item.get("app", "TR_TOOL_DL" if item_k.startswith("TRDL-") else "Movie_TR")).strip()

        # ONLY match if it is the EXACT same app on the same machine, or exact same key!
        is_same_app_machine = (item_mid == norm_mid and item_app == norm_app)
        is_same_key = (item_k and item_k == entry["key"])

        if is_same_app_machine or is_same_key:
            old_k = item.get("key")
            if old_k and old_k != entry["key"]:
                prev_keys_to_revoke.append(old_k)
                existing_prev = item.get("previous_keys", [])
                if old_k not in existing_prev:
                    existing_prev.append(old_k)
                entry["previous_keys"] = existing_prev
            entry["id"] = item.get("id", entry["id"])
            entry["first_created_at"] = item.get("first_created_at") or item.get("created_at")
            entry["updated_at"] = now_str
            entry["status"] = "active"
            history[i] = entry
            updated = True
            break

    if not updated:
        entry["first_created_at"] = now_str
        entry["status"] = "active"
        history.insert(0, entry)

    # Unrevoke this machine ID and this new key from revocation lists
    try:
        remove_revoked_hwid(norm_mid)
        remove_revoked_key(entry["key"])
    except Exception:
        pass

    # AUTOMATICALLY BLACKLIST ALL OLD PREVIOUS KEYS SO THEY CAN NEVER BE USED AGAIN!
    for old_k in prev_keys_to_revoke:
        try:
            if old_k and old_k != entry["key"]:
                add_revoked_key(old_k)
        except Exception:
            pass

    save_license_history(history)
    return entry

def normalize_hwid(hwid_str):
    """Normalize any HWID input to standard uppercase 16-hex core."""
    if not hwid_str:
        return ""
    clean = str(hwid_str).strip().upper()
    m = re.search(r'(?:TR|TRDL)-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})-([A-Z0-9]{4})', clean)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"
    hex_only = re.sub(r'[^A-Z0-9]', '', clean)
    if len(hex_only) >= 16:
        return hex_only[:16]
    return hex_only

def find_customer_by_hwid(hwid_str):
    """Find existing customer record by Machine ID."""
    if not hwid_str:
        return None
    norm = normalize_hwid(hwid_str)
    if not norm:
        return None
    history = load_license_history()
    for item in history:
        if normalize_hwid(item.get("machine_id", "")) == norm:
            return item
    return None

def delete_license_from_history(entry_id_or_key):
    """Delete an entry by ID or Key."""
    history = load_license_history()
    filtered = [
        item for item in history
        if item.get("id") != entry_id_or_key and item.get("key") != entry_id_or_key
    ]
    if len(filtered) != len(history):
        save_license_history(filtered)
        return True
    return False

def get_license_statistics():
    """Calculate totals and status counts for issued licenses."""
    history = load_license_history()
    total = len(history)
    active = 0
    expired = 0
    lifetime = 0
    plans = {}
    today = datetime.now().date()

    for item in history:
        plan = item.get("plan", "VIP")
        plans[plan] = plans.get(plan, 0) + 1

        exp_str = item.get("expiry_date", "")
        if exp_str == "LIFETIME":
            active += 1
            lifetime += 1
        else:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                if exp_date >= today:
                    active += 1
                else:
                    expired += 1
            except Exception:
                active += 1

    return {
        "total": total,
        "active": active,
        "expired": expired,
        "lifetime": lifetime,
        "plans": plans
    }

REVOKED_FILE_NAME = "revoked_licenses.json"

def get_revoked_file_path():
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0])) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, REVOKED_FILE_NAME)

def load_revoked_keys():
    """Load set of revoked license keys, signatures, and blacklisted HWIDs."""
    path = get_revoked_file_path()
    revoked = set()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    revoked = set(str(x).strip() for x in data if x)
        except Exception:
            pass
    appdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        app_p = os.path.join(appdata, "Movie_TR", REVOKED_FILE_NAME)
        if os.path.exists(app_p):
            try:
                with open(app_p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if isinstance(d, list):
                        revoked.update(str(x).strip() for x in d if x)
            except Exception:
                pass
    return revoked

def save_revoked_keys(keys_set):
    """Save set of revoked keys to disk and LocalAppData."""
    keys_list = sorted(list(set(str(x).strip() for x in keys_set if x)))
    path = get_revoked_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(keys_list, f, indent=4)
    except Exception:
        pass
    appdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        try:
            backup_dir = os.path.join(appdata, "Movie_TR")
            os.makedirs(backup_dir, exist_ok=True)
            with open(os.path.join(backup_dir, REVOKED_FILE_NAME), "w", encoding="utf-8") as f:
                json.dump(keys_list, f, indent=4)
        except Exception:
            pass

def add_revoked_key(key_str):
    """Add a license key or signature to revocation list."""
    if not key_str:
        return
    k = str(key_str).strip()
    s = load_revoked_keys()
    s.add(k)
    parts = k.split('-')
    if len(parts) >= 3:
        s.add(parts[-1])
    save_revoked_keys(s)

def remove_revoked_key(key_str):
    """Remove a license key or signature from revocation list."""
    if not key_str:
        return
    k = str(key_str).strip()
    s = load_revoked_keys()
    s.discard(k)
    parts = k.split('-')
    if len(parts) >= 3:
        s.discard(parts[-1])
        try:
            payload_b64 = parts[1]
            pad = len(payload_b64) % 4
            if pad:
                payload_b64 += "=" * (4 - pad)
            p_bytes = base64.urlsafe_b64decode(payload_b64.encode('utf-8'))
            p_obj = json.loads(p_bytes.decode('utf-8'))
            mid = p_obj.get("m", "")
            if mid:
                s.discard(mid.upper().strip())
                m_norm = normalize_hwid(mid)
                if m_norm:
                    s.discard(m_norm)
                m_suf = mid.split('-')[-1] if '-' in mid else ""
                if m_suf and len(m_suf) == 4:
                    s.discard(m_suf)
        except Exception:
            pass
    save_revoked_keys(s)

def load_revoked_hwids():
    return load_revoked_keys()

def save_revoked_hwids(hwids_set):
    save_revoked_keys(hwids_set)

def add_revoked_hwid(hwid):
    add_revoked_key(hwid)

def remove_revoked_hwid(hwid):
    if not hwid:
        return
    h = str(hwid).upper().strip()
    norm = normalize_hwid(h)
    suffix = h.split('-')[-1] if '-' in h else ""
    s = load_revoked_keys()
    s.discard(h)
    if norm:
        s.discard(norm)
    if suffix and len(suffix) == 4:
        s.discard(suffix)
    save_revoked_keys(s)

