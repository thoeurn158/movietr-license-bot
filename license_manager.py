# -*- coding: utf-8 -*-
import os
import sys
import json
import base64
import hashlib
import hmac
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
        
    # Check Hardware Lock
    key_machine = payload_obj.get("m", "").upper().strip()
    cur_id = current_machine_id.upper().strip()
    stored_id = get_system_stored_hwid().upper().strip()

    # Check Revocation (Blacklist)
    try:
        revoked_set = load_revoked_hwids()
        if cur_id in revoked_set or key_machine in revoked_set:
            return False, "License សម្រាប់ម៉ាស៊ីននេះត្រូវបានផ្តាច់ និងបិទសិទ្ធិ (Revoked) ដោយ Admin រួចហើយ!"
    except Exception:
        pass

    if key_machine != cur_id:
        # Check against previously activated hardware ID in registry
        if stored_id and key_machine == stored_id:
            pass # Valid match with system-stored hardware profile
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

def record_license_to_history(machine_id, user_name, expiry_date, plan, key, duration=None, notes="", channel="PC Generator"):
    """
    Record an issued license to history.
    If the key or (machine_id + plan) already exists, update the timestamp and expiry.
    """
    history = load_license_history()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
        "machine_id": str(machine_id).upper().strip(),
        "plan": str(plan).strip().upper() or "VIP",
        "duration": duration,
        "expiry_date": str(expiry_date).strip(),
        "key": str(key).strip(),
        "notes": notes,
        "channel": channel
    }

    # Avoid exact key duplicate, prepend newest on top
    updated = False
    for i, item in enumerate(history):
        if item.get("key") == entry["key"] or (item.get("machine_id") == entry["machine_id"] and item.get("key") == entry["key"]):
            history[i] = entry
            updated = True
            break

    if not updated:
        history.insert(0, entry)

    save_license_history(history)
    return entry

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

def load_revoked_hwids():
    path = get_revoked_file_path()
    revoked = set()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    revoked = set(x.upper().strip() for x in data if x)
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
                        revoked.update(x.upper().strip() for x in d if x)
            except Exception:
                pass
    return revoked

def save_revoked_hwids(hwids_set):
    hwids_list = sorted(list(set(x.upper().strip() for x in hwids_set if x)))
    path = get_revoked_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(hwids_list, f, indent=4)
    except Exception:
        pass
    appdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        try:
            backup_dir = os.path.join(appdata, "Movie_TR")
            os.makedirs(backup_dir, exist_ok=True)
            with open(os.path.join(backup_dir, REVOKED_FILE_NAME), "w", encoding="utf-8") as f:
                json.dump(hwids_list, f, indent=4)
        except Exception:
            pass

def add_revoked_hwid(hwid):
    if not hwid:
        return
    hwid = hwid.upper().strip()
    s = load_revoked_hwids()
    s.add(hwid)
    save_revoked_hwids(s)

def remove_revoked_hwid(hwid):
    if not hwid:
        return
    hwid = hwid.upper().strip()
    s = load_revoked_hwids()
    if hwid in s:
        s.discard(hwid)
        save_revoked_hwids(s)

