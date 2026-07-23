#!/usr/bin/env python3
"""
SHOPSY ULTIMATE BOT – FINAL STABLE
- OTP Login as always
- JSON Login with bootstrap + verify
- Robust DC handling
Author: Tera Bhai
"""

import asyncio, time, json, re, uuid, random, os, sys, base64
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("❌ 'curl_cffi' missing. Install: pip install curl_cffi")
    sys.exit(1)

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

# ===================== CONFIG =====================
BOT_TOKEN = "8816143638:AAGxY0uxFxlgaJR2zHiSsUujyjSqDQFVTnI"
CHANNEL_USERNAME = ""
CHANNEL_URL = ""
REFERRAL_REQUIRED = 0

APP_VERSION = "2291175"
DEVICE_MODEL = "Pixel 9a"
DEVICE_BRAND = "Google"
DEFAULT_PINCODE = "226001"

GAMES = [
    {"id": "runner-3d",  "name": "Super Runner",  "play_time": 94, "gems": 200},
    {"id": "city-builder","name": "City Builder",  "play_time": 47, "gems": 100},
    {"id": "match-3",    "name": "Fruit Crush",   "play_time": 35, "gems": 100},
    {"id": "goods-triple","name": "Grocery Match", "play_time": 40, "gems": 100},
    {"id": "ludo",       "name": "Ludo",          "play_time": 50, "gems": 100},
    {"id": "nazaria",    "name": "Nazar Pop",     "play_time": 45, "gems": 100},
]

# ===================== SESSION & REFERRAL FILES =====================
SESSION_DIR = Path("sessions")
SESSION_DIR.mkdir(exist_ok=True)
REFERRAL_FILE = Path("referrals.json")
if not REFERRAL_FILE.exists():
    REFERRAL_FILE.write_text("{}")

def get_session_path(user_id: int) -> Path:
    return SESSION_DIR / f"{user_id}.json"

def load_referrals() -> dict:
    return json.loads(REFERRAL_FILE.read_text())

def save_referrals(data: dict):
    REFERRAL_FILE.write_text(json.dumps(data, indent=2))

# ===================== SHOPSY CLIENT =====================
class ShopsyBotClient:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.session_file = get_session_path(user_id)
        self.session = cffi_requests.Session(impersonate="chrome120")
        self._user_cache = None
        self.otp_request_id = None
        self.load_state()

    def load_state(self):
        if self.session_file.exists():
            try:
                data = json.loads(self.session_file.read_text())
                self.device_id = data.get("device_id", uuid.uuid4().hex)
                self.visit_id = data.get("visit_id", f"{uuid.uuid4().hex}-{int(time.time()*1000)}")
                self.dc_id = data.get("dc_id", "1")
                self.at = data.get("at", "")
                self.sn = data.get("sn", "")
                self.secure_token = data.get("secure_token", "")
                self.secure_cookie = data.get("secure_cookie", "")
                self.account_id = data.get("account_id", "")
                self.user_name = data.get("user_name", "")
                self.is_logged_in = data.get("is_logged_in", False)
            except:
                self._reset_state()
        else:
            self._reset_state()

    def _reset_state(self):
        self.device_id = uuid.uuid4().hex
        self.visit_id = f"{uuid.uuid4().hex}-{int(time.time()*1000)}"
        self.dc_id = "1"
        self.at = ""
        self.sn = ""
        self.secure_token = ""
        self.secure_cookie = ""
        self.account_id = ""
        self.user_name = ""
        self.is_logged_in = False

    def save_state(self):
        data = {
            "device_id": self.device_id,
            "visit_id": self.visit_id,
            "dc_id": self.dc_id,
            "at": self.at,
            "sn": self.sn,
            "secure_token": self.secure_token,
            "secure_cookie": self.secure_cookie,
            "account_id": self.account_id,
            "user_name": self.user_name,
            "is_logged_in": self.is_logged_in
        }
        self.session_file.write_text(json.dumps(data, indent=2))

    # ---------- Headers & URL ----------
    @property
    def x_user_agent(self):
        return (
            f"Mozilla/5.0 (Linux; Android 15; {DEVICE_MODEL} Build/BD4A.250505.003) "
            f"FKUA/Retail/{APP_VERSION}/Android/Mobile "
            f"({DEVICE_BRAND}/{DEVICE_MODEL}/{self.device_id})"
        )

    @property
    def base_url(self):
        return f"https://{self.dc_id}.rome.api.flipkart.net"

    def _game_headers(self):
        h = {
            "User-Agent": "okhttp/4.9.2",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept-Encoding": "gzip",
            "x-user-agent": self.x_user_agent,
            "sessionid": "session_id",
            "X-NewRelic-ID": "VwEHU1dSCxABUVlaAAQHU1UA",
        }
        if self.account_id:
            h["x-user-id"] = self.account_id
        if self.secure_token:
            h["secureToken"] = self.secure_token
        if self.secure_cookie:
            h["secureCookie"] = self.secure_cookie
        return h

    def _partner_headers(self, layout=False):
        h = {
            "User-Agent": "okhttp/4.9.2",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept-Encoding": "gzip",
            "X-PARTNER-CONTEXT": '{"source":"reseller"}',
            "FK-TENANT-ID": "SHOPSY",
            "business": "reseller",
            "X-User-Agent": self.x_user_agent,
            "X-Visit-Id": self.visit_id,
            "X-NewRelic-ID": "VwEHU1dSCxABUVlaAAQHU1UA",
        }
        if layout: h["X-Layout-Version"] = '{"appVersion":"910000","frameworkVersion":"1.0"}'
        if self.at: h["at"] = self.at
        if self.sn: h["sn"] = self.sn
        if self.secure_token: h["secureToken"] = self.secure_token
        if self.secure_cookie: h["secureCookie"] = self.secure_cookie
        return h

    def _apply_session(self, data):
        sess = data.get("SESSION", {})
        if not sess: return
        self.at = sess.get("at", self.at)
        self.sn = sess.get("sn", self.sn)
        self.secure_token = sess.get("secureToken", self.secure_token)
        self.account_id = sess.get("accountId", self.account_id)
        self.is_logged_in = bool(sess.get("isLoggedIn"))
        if sess.get("firstName"):
            self.user_name = f"{sess['firstName']} {sess.get('lastName','')}".strip()
        self.save_state()

    def _capture_cookie(self, resp):
        c = resp.headers.get("securecookie") or resp.headers.get("secureCookie")
        if c: self.secure_cookie = c

    # ---------- DC helpers ----------
    @staticmethod
    def _extract_dc_from_token(at_token: str) -> str | None:
        try:
            payload = at_token.split(".")[1]
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)
            z = data.get("z")
            mapping = {"HYD": "2", "BLR": "1", "MAA": "3", "DEL": "4"}
            return mapping.get(z.upper()) if z else None
        except:
            return None

    @staticmethod
    def _extract_dc_from_response(data: dict) -> str | None:
        meta = data.get("META_INFO", {})
        if isinstance(meta, dict):
            dc_info = meta.get("dcInfo") or meta.get("dc_info")
            if isinstance(dc_info, dict):
                dc = dc_info.get("id") or dc_info.get("dc") or dc_info.get("dcId")
                if dc: return str(dc)
        resp_block = data.get("RESPONSE", {})
        if isinstance(resp_block, dict):
            dc = resp_block.get("id") or resp_block.get("dc") or resp_block.get("dcId")
            if dc: return str(dc)
        dc = data.get("dc") or data.get("dcId")
        if dc: return str(dc)
        return None

    @staticmethod
    def _fallback_dc(tried: set, current_dc: str) -> str:
        for dc in ["1", "2", "3", "4"]:
            if dc not in tried:
                return dc
        return "1"

    # ---------- Standard POST ----------
    def _post(self, path, payload, game=False, layout=False, max_retries=10):
        tried_dcs = set()
        for attempt in range(max_retries):
            if self.dc_id in tried_dcs:
                self.dc_id = self._fallback_dc(tried_dcs, self.dc_id)
                self.save_state()
            tried_dcs.add(self.dc_id)
            url = f"{self.base_url}{path}"
            headers = self._game_headers() if game else self._partner_headers(layout)
            try:
                resp = self.session.post(url, json=payload, headers=headers, timeout=30)
            except Exception:
                time.sleep(2)
                continue

            self._capture_cookie(resp)
            if not resp.headers.get("content-type", "").startswith("application/json"):
                time.sleep(2)
                continue

            try:
                data = resp.json()
            except json.JSONDecodeError:
                raise RuntimeError(f"Invalid JSON: {resp.text[:200]}")

            if resp.status_code == 406 or data.get("STATUS_CODE") == 406:
                if data.get("ERROR_MESSAGE") == "DC Change" or data.get("ERROR_CODE") == 2000:
                    new_dc = self._extract_dc_from_response(data)
                    if new_dc and new_dc != self.dc_id:
                        self.dc_id = new_dc
                    else:
                        if self.at:
                            token_dc = self._extract_dc_from_token(self.at)
                            if token_dc and token_dc != self.dc_id:
                                self.dc_id = token_dc
                            else:
                                self.dc_id = self._fallback_dc(tried_dcs, self.dc_id)
                        else:
                            self.dc_id = self._fallback_dc(tried_dcs, self.dc_id)
                    self.save_state()
                    continue

            if not game:
                self._apply_session(data)

            if resp.status_code >= 400 or data.get("STATUS_CODE", 200) >= 400:
                raise RuntimeError(f"API error: {data}")

            return data
        raise RuntimeError("DC retry limit exceeded")

    # ---------- Minimal POST ----------
    def _post_minimal(self, path, payload, dc=None, max_retries=5):
        if dc is None:
            dc = self.dc_id
        tried = set()
        headers = {
            "User-Agent": "okhttp/4.9.2",
            "Content-Type": "application/json; charset=UTF-8",
            "X-User-Agent": self.x_user_agent,
            "X-Visit-Id": self.visit_id,
            "Accept-Encoding": "gzip",
        }
        for attempt in range(max_retries):
            if dc in tried:
                dc = self._fallback_dc(tried, dc)
            tried.add(dc)
            url = f"https://{dc}.rome.api.flipkart.net{path}"
            try:
                resp = self.session.post(url, json=payload, headers=headers, timeout=30)
            except Exception:
                time.sleep(1)
                continue

            if not resp.headers.get("content-type", "").startswith("application/json"):
                time.sleep(1)
                continue

            data = resp.json()
            if resp.status_code == 406 or data.get("STATUS_CODE") == 406:
                if data.get("ERROR_MESSAGE") == "DC Change" or data.get("ERROR_CODE") == 2000:
                    new_dc = self._extract_dc_from_response(data)
                    if new_dc and new_dc != dc:
                        dc = new_dc
                        self.dc_id = dc
                    else:
                        if self.at:
                            token_dc = self._extract_dc_from_token(self.at)
                            if token_dc and token_dc != dc:
                                dc = token_dc
                                self.dc_id = dc
                            else:
                                dc = self._fallback_dc(tried, dc)
                                self.dc_id = dc
                        else:
                            dc = self._fallback_dc(tried, dc)
                            self.dc_id = dc
                    self.save_state()
                    continue
            if resp.status_code >= 400 or data.get("STATUS_CODE", 200) >= 400:
                raise RuntimeError(f"Minimal API error: {data}")
            return data
        raise RuntimeError("Minimal DC retry limit exceeded")

    # ---------- Bootstrap & Login ----------
    def bootstrap(self):
        payload = {
            "pageUri": "/shopsy2-login-page-store",
            "pageContext": {"paginatedFetch": False, "pageNumber": 1},
            "locationContext": {"pincode": DEFAULT_PINCODE}
        }
        data = self._post("/4/page/fetch", payload, layout=True)
        if not self.at or not self.sn:
            try:
                user_payload = {
                    "location": {"pincode": None},
                    "ad": {"adId": str(uuid.uuid4()), "doNotPersonalizeAds": False, "sdkAdId": "", "adSdkVersion": "2.12.0"},
                    "locale": {"deviceLanguage": "en", "shouldRefreshLanguage": False},
                    "versions": {"cart": 1167987101, "userAccountState": 0, "abResponse": -2054295432, "abVariables": 0, "accountDetails": 1220048498, "wishlist": 0, "notifications": 861101, "location": 23273, "lockinResponse": 426889274}
                }
                self._post("/4/user/state", user_payload)
            except:
                pass
        self.save_state()

    def send_otp(self, phone):
        phone = re.sub(r'\D', '', phone)[-10:]
        payload = {
            "actionRequestContext": {
                "type": "LOGIN_IDENTITY_VERIFY_SHOPSY2",
                "loginId": phone,
                "loginIdPrefix": "+91",
                "phoneNumberFormat": "E164",
                "addAppHash": True,
                "loginType": "MOBILE",
                "verificationType": "OTP",
                "sourceContext": "DEFAULT"
            }
        }
        try:
            data = self._post("/1/action/view", payload)
            ctx = data.get("RESPONSE", {}).get("actionResponseContext", {})
            if ctx.get("requestId"):
                self.otp_request_id = ctx["requestId"]
                return True
        except Exception as e:
            print(f"Primary OTP fail: {e}")

        try:
            data = self._post_minimal("/1/action/view", payload)
            ctx = data.get("RESPONSE", {}).get("actionResponseContext", {})
            if ctx.get("requestId"):
                self.otp_request_id = ctx["requestId"]
                return True
            else:
                raise RuntimeError(f"Fallback OTP missing requestId: {data}")
        except Exception as e:
            raise RuntimeError(f"OTP send failed completely: {e}")

    def verify_otp(self, phone, otp):
        phone = re.sub(r'\D', '', phone)[-10:]
        payload = {
            "actionRequestContext": {
                "type": "LOGIN_SHOPSY2",
                "loginId": phone,
                "loginIdPrefix": "+91",
                "otp": otp.strip(),
                "otpRequestId": self.otp_request_id,
                "remainingAttempts": 5,
                "phoneNumberFormat": "E164",
                "loginType": "MOBILE",
                "verificationType": "OTP",
                "sourceContext": "DEFAULT"
            }
        }
        try:
            data = self._post("/1/action/view", payload)
            ctx = data.get("RESPONSE", {}).get("actionResponseContext", {})
            if ctx.get("authenticationSuccess"):
                self.is_logged_in = True
                self.account_id = ctx.get("accountId") or data.get("RESPONSE", {}).get("SESSION", {}).get("accountId", "")
                self._apply_session(data)
                if self.at:
                    token_dc = self._extract_dc_from_token(self.at)
                    if token_dc:
                        self.dc_id = token_dc
                self.save_state()
                return True
        except Exception as e:
            print(f"Primary verify fail: {e}")

        try:
            data = self._post_minimal("/1/action/view", payload)
            ctx = data.get("RESPONSE", {}).get("actionResponseContext", {})
            if ctx.get("authenticationSuccess"):
                self.is_logged_in = True
                self._apply_session(data)
                if self.at:
                    token_dc = self._extract_dc_from_token(self.at)
                    if token_dc:
                        self.dc_id = token_dc
                self.save_state()
                return True
            else:
                raise RuntimeError("Wrong OTP (fallback)")
        except Exception as e:
            raise RuntimeError(f"OTP verification failed: {e}")

    # ---------- Game APIs ----------
    def get_user(self):
        payload = {
            "requestMethod": "GET",
            "routeUri": "user/get-user",
            "payload": {"userId": self.account_id, "userName": self.user_name or "User"}
        }
        data = self._post("/1/shopsy/games", payload, game=True)
        if not data.get("success"):
            raise RuntimeError(f"User fetch fail. Response: {data}")
        self._user_cache = data["data"]
        return self._user_cache

    def claim_gullak(self):
        payload = {
            "requestMethod": "POST",
            "routeUri": "gullak/claim-gullak",
            "payload": {"userId": self.account_id}
        }
        data = self._post("/1/shopsy/games", payload, game=True)
        return data.get("success", False)

    def _game_already_done(self, game_id, user):
        for g in user.get("gameStats", {}).get("games", []):
            if g.get("gameId") == game_id and g.get("rewards", {}).get("isMaxGameBonusEarned"):
                return True
        return False

    def play_game(self, game, fast=True):
        game_id = game["id"]
        name = game["name"]
        user = self.get_user()
        if self._game_already_done(game_id, user):
            return None, "already_done"
        secs = game["play_time"] if not fast else (game["play_time"] if game["play_time"] >= 60 else 15)
        start = self._post("/1/shopsy/games", {
            "requestMethod": "POST",
            "routeUri": "game/game-started",
            "payload": {"userId": self.account_id, "gameId": game_id}
        }, game=True)
        if not start.get("success"):
            return None, "start_fail"
        sess_id = start["data"]["sessionId"]
        time.sleep(secs)
        end = self._post("/1/shopsy/games", {
            "requestMethod": "POST",
            "routeUri": "game/game-ended",
            "payload": {
                "userId": self.account_id,
                "gameId": game_id,
                "sessionId": sess_id,
                "gemsEarned": game["gems"],
                "playTimeInSec": secs
            }
        }, game=True)
        if end.get("success"):
            coins = end["data"].get("coinsEarnedForGame", 0)
            return coins, "success"
        return None, "end_fail"

    async def run_normal_async(self, msg: types.Message):
        status_msg = await msg.answer("⏳ Normal mode starting...")
        total = 0
        for i, game in enumerate(GAMES, 1):
            await status_msg.edit_text(f"⏳ Playing {game['name']} ({i}/{len(GAMES)})...")
            loop = asyncio.get_event_loop()
            result, status = await loop.run_in_executor(None, self.play_game, game, True)
            if status == "success":
                total += result
                await status_msg.edit_text(f"✅ {game['name']} +{result} coins | Total: {total}")
            elif status == "already_done":
                await status_msg.edit_text(f"⏭️ {game['name']} already done | Total: {total}")
            else:
                await status_msg.edit_text(f"❌ {game['name']} failed | Total: {total}")
            await asyncio.sleep(1)
        await status_msg.edit_text(f"✅ Normal run finished! +{total} coins total")
        return total

    async def run_exploit_async(self, msg: types.Message, parallel=50, burst_delay=7, rounds=2, start_delay=0.2):
        status_msg = await msg.answer("🔥 Exploit started...")
        total = 0
        for game in GAMES:
            user = await asyncio.get_event_loop().run_in_executor(None, self.get_user)
            if self._game_already_done(game["id"], user):
                await status_msg.edit_text(f"⏭️ {game['name']} already done, skipping")
                continue
            for r in range(1, rounds + 1):
                await status_msg.edit_text(f"🔥 {game['name']} Round {r}/{rounds} (creating sessions)...")
                sessions = []
                loop = asyncio.get_event_loop()
                for _ in range(parallel):
                    resp = await loop.run_in_executor(None, lambda: self._post("/1/shopsy/games", {
                        "requestMethod": "POST",
                        "routeUri": "game/game-started",
                        "payload": {"userId": self.account_id, "gameId": game["id"]}
                    }, game=True))
                    if resp.get("success"):
                        sessions.append(resp["data"]["sessionId"])
                    await asyncio.sleep(start_delay)
                if not sessions:
                    await status_msg.edit_text(f"❌ {game['name']} Round {r}: no sessions")
                    break
                await asyncio.sleep(burst_delay)
                await status_msg.edit_text(f"💥 {game['name']} Round {r}: ending {len(sessions)} sessions...")
                def end_worker(sess_id):
                    resp = self._post("/1/shopsy/games", {
                        "requestMethod": "POST",
                        "routeUri": "game/game-ended",
                        "payload": {
                            "userId": self.account_id,
                            "gameId": game["id"],
                            "sessionId": sess_id,
                            "gemsEarned": game["gems"],
                            "playTimeInSec": game["play_time"] if game["play_time"] >= 60 else 15
                        }
                    }, game=True)
                    if resp.get("success"):
                        return resp["data"].get("coinsEarnedForGame", 0)
                    return 0
                with ThreadPoolExecutor(max_workers=min(parallel, 50)) as ex:
                    results = await loop.run_in_executor(None, lambda: list(ex.map(end_worker, sessions)))
                round_total = sum(results)
                total += round_total
                success_count = sum(1 for c in results if c > 0)
                await status_msg.edit_text(f"✅ {game['name']} Round {r}: {success_count}/{len(sessions)} success, +{round_total} coins | Total: {total}")
        await status_msg.edit_text(f"🎉 Exploit finished! Total +{total} coins")
        return total

# ===================== REFERRAL SYSTEM =====================
def add_referral(user_id: int, referrer_id: int):
    referrals = load_referrals()
    user_id_str = str(user_id)
    referrer_str = str(referrer_id)
    if user_id == referrer_id:
        return False
    if user_id_str not in referrals:
        referrals[user_id_str] = {"referred_by": referrer_str, "referrals": 0, "access": False}
    if referrer_str not in referrals:
        referrals[referrer_str] = {"referred_by": None, "referrals": 0, "access": False}
    if "ref_ids" not in referrals[referrer_str]:
        referrals[referrer_str]["ref_ids"] = []
    if user_id not in referrals[referrer_str]["ref_ids"]:
        referrals[referrer_str]["ref_ids"].append(user_id)
        referrals[referrer_str]["referrals"] = len(referrals[referrer_str]["ref_ids"])
    if referrals[referrer_str]["referrals"] >= REFERRAL_REQUIRED:
        referrals[referrer_str]["access"] = True
    save_referrals(referrals)
    return True

def get_referral_count(user_id: int) -> int:
    referrals = load_referrals()
    return referrals.get(str(user_id), {}).get("referrals", 0)

def has_access(user_id:int)->bool:
    return True

# ===================== KEYBOARDS =====================
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Login"), KeyboardButton(text="📥 JSON Login")],
        [KeyboardButton(text="💰 Balance"), KeyboardButton(text="👥 Referrals")],
        [KeyboardButton(text="ℹ️ Help")]
    ],
    resize_keyboard=True
)

logged_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⚡ Run Normal"), KeyboardButton(text="🔥 Exploit")],
        [KeyboardButton(text="💰 Balance"), KeyboardButton(text="👥 Referrals")],
        [KeyboardButton(text="🚪 Logout")]
    ],
    resize_keyboard=True
)


# ===================== BOT HANDLERS =====================
router = Router()

class LoginState(StatesGroup):
    waiting_phone = State()
    waiting_otp = State()
    waiting_json = State()

def get_client(user_id: int) -> ShopsyBotClient:
    return ShopsyBotClient(user_id)

@router.message(Command("start"))
async def start_cmd(msg: types.Message, command: CommandObject, **kwargs):
    user_id = msg.from_user.id
    bot = msg.bot
    args = command.args
    if args and args.startswith("ref"):
        try:
            referrer_id = int(args[3:])
            if referrer_id != user_id:
                add_referral(user_id, referrer_id)
        except:
            pass

    await msg.answer(
        "🛒 <b>Shopsy Ultimate Bot</b>\nChoose an option:",
        reply_markup=main_kb,
        parse_mode="HTML"
    )

@router.message(F.text == "👥 Referrals")

async def show_referrals(msg: types.Message, **kwargs):
    user_id = msg.from_user.id
    count = get_referral_count(user_id)
    has_acc = has_access(user_id)
    bot_username = (await msg.bot.me()).username
    link = f"https://t.me/{bot_username}?start=ref{user_id}"
    text = (
        f"👥 <b>Your Referrals</b>\n"
        f"Count: {count}/{REFERRAL_REQUIRED}\n"
        f"Status: {'✅ Unlocked' if has_acc else '🔒 Locked'}\n\n"
        f"Your referral link:\n<code>{link}</code>\n\n"
        f"Share this with friends. When they start the bot, you get +1 referral."
    )
    await msg.answer(text, parse_mode="HTML")

# ---- OTP Login ----
@router.message(F.text == "🚀 Login")


async def start_login(msg: types.Message, state: FSMContext, **kwargs):
    await msg.answer("📱 10-digit mobile number bhejo:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(LoginState.waiting_phone)

@router.message(LoginState.waiting_phone)


async def process_phone(msg: types.Message, state: FSMContext, **kwargs):
    phone = msg.text.strip()
    if not phone.isdigit() or len(phone) != 10:
        await msg.answer("❌ Galat number. Sahi 10‑digit daalo.")
        return
    await state.update_data(phone=phone)
    client = get_client(msg.from_user.id)
    try:
        client.bootstrap()
        client.send_otp(phone)
        await state.update_data(client_state=client)
        await msg.answer(f"📬 OTP bhej diya +91{phone}.\nOTP enter karo:")
        await state.set_state(LoginState.waiting_otp)
    except Exception as e:
        await msg.answer(f"❌ Error: {e}")
        await state.clear()

@router.message(LoginState.waiting_otp)


async def process_otp(msg: types.Message, state: FSMContext, **kwargs):
    data = await state.get_data()
    client = data.get("client_state")
    if not client:
        await msg.answer("⚠️ Session expired. Login again.")
        await state.clear()
        return
    otp = msg.text.strip()
    try:
        client.verify_otp(data["phone"], otp)
        await msg.answer("✅ Login successful!", reply_markup=logged_kb)
        await state.clear()
    except Exception as e:
        await msg.answer(f"❌ {e}")

# ---- JSON Login (bootstrap before verify) ----
@router.message(F.text == "📥 JSON Login")


async def start_json_login(msg: types.Message, state: FSMContext, **kwargs):
    await msg.answer("📋 <b>Paste your session JSON</b>\n\nExample:\n<code>{...}</code>", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.set_state(LoginState.waiting_json)

@router.message(LoginState.waiting_json)


async def process_json_login(msg: types.Message, state: FSMContext, **kwargs):
    text = msg.text.strip()
    try:
        data = json.loads(text)
    except Exception:
        await msg.answer("❌ Invalid JSON format.")
        return

    required_keys = ["accountId", "at", "sn", "secureToken"]
    if not all(k in data for k in required_keys):
        await msg.answer(f"❌ JSON must contain: {', '.join(required_keys)}")
        return

    user_id = msg.from_user.id
    dc_from_token = ShopsyBotClient._extract_dc_from_token(data["at"])
    dc_id = dc_from_token or data.get("dc_id", "1")

    session_data = {
        "device_id": uuid.uuid4().hex,
        "visit_id": f"{uuid.uuid4().hex}-{int(time.time()*1000)}",
        "dc_id": dc_id,
        "at": data["at"],
        "sn": data["sn"],
        "secure_token": data["secureToken"],
        "secure_cookie": data.get("secureCookie", ""),
        "account_id": data["accountId"],
        "user_name": f"{data.get('firstName', '')} {data.get('lastName', '')}".strip() or "User",
        "is_logged_in": True
    }

    try:
        get_session_path(user_id).write_text(json.dumps(session_data, indent=2))
    except Exception as e:
        await msg.answer(f"❌ Error saving session: {e}")
        return

    client = ShopsyBotClient(user_id)
    try:
        client.bootstrap()          # 🔥 Lock release
        user_info = client.get_user()
        await msg.answer("✅ JSON imported and verified! You are now logged in.", reply_markup=logged_kb)
        await state.clear()
    except Exception as e:
        if get_session_path(user_id).exists():
            get_session_path(user_id).unlink()
        await msg.answer(f"❌ JSON tokens invalid or expired. Error: {e}")

# ---- Other commands ----
@router.message(F.text == "🚪 Logout")


async def logout(msg: types.Message, state: FSMContext, **kwargs):
    session_path = get_session_path(msg.from_user.id)
    if session_path.exists():
        session_path.unlink()
    await msg.answer("👋 Logged out.", reply_markup=main_kb)

@router.message(F.text == "💰 Balance")


async def show_balance(msg: types.Message, **kwargs):
    client = get_client(msg.from_user.id)
    if not client.is_logged_in:
        await msg.answer("❌ Pehle login karo.")
        return
    try:
        user = client.get_user()
        coins = user.get("earnings", {}).get("coinsEarnedTotal", 0)
        await msg.answer(f"💰 Balance: {coins} SuperCoins")
    except Exception as e:
        await msg.answer(f"❌ {e}")

@router.message(F.text == "⚡ Run Normal")


async def run_normal(msg: types.Message, **kwargs):
    client = get_client(msg.from_user.id)
    if not client.is_logged_in:
        await msg.answer("❌ Pehle login karo.")
        return
    try:
        await client.run_normal_async(msg)
        user = client.get_user()
        coins = user.get("earnings", {}).get("coinsEarnedTotal", 0)
        await msg.answer(f"💰 Final Balance: {coins} SuperCoins")
    except Exception as e:
        await msg.answer(f"❌ Error: {e}")

@router.message(F.text == "🔥 Exploit")


async def exploit(msg: types.Message, **kwargs):
    client = get_client(msg.from_user.id)
    if not client.is_logged_in:
        await msg.answer("❌ Pehle login karo.")
        return
    try:
        await client.run_exploit_async(msg, parallel=50, burst_delay=7, rounds=2, start_delay=0.2)
        user = client.get_user()
        coins = user.get("earnings", {}).get("coinsEarnedTotal", 0)
        await msg.answer(f"💰 Final Balance: {coins} SuperCoins")
    except Exception as e:
        await msg.answer(f"❌ Error: {e}")

@router.message(F.text == "ℹ️ Help")
async def help_cmd(msg: types.Message, **kwargs):
    await msg.answer(
        "🛒 <b>Shopsy Ultimate Bot</b>\n\n"
        "🚀 Login – OTP login\n"
        "📥 JSON Login – Import existing session (verified)\n"
        "⚡ Run Normal – Play games normally\n"
        "🔥 Exploit – Parallel exploit (50 sessions, burst 7s, 2 rounds)\n"
        "💰 Balance – Check coins\n"
        "👥 Referrals – Your referral count & link\n"
        "🚪 Logout – Remove session\n\n"
        "",
        parse_mode="HTML"
    )

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")