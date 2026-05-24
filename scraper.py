"""
VNUA Schedule → Google Calendar (.ics)
pip install requests icalendar
"""

import os, json, base64, uuid
import requests
from datetime import datetime
from icalendar import Calendar, Event

BASE_URL = "https://daotao.vnua.edu.vn"
USERNAME = os.environ.get("SCHOOL_USER", "")
PASSWORD = os.environ.get("SCHOOL_PASS", "")
OUTPUT   = "docs/schedule.ics"

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0", "Referer": BASE_URL})

# ── Login ─────────────────────────────────────────────────────────────────────
def login():
    from urllib.parse import parse_qs

    code = base64.b64encode(json.dumps({
        "username": USERNAME,
        "password": PASSWORD,
        "uri": f"{BASE_URL}/#/home"
    }).encode()).decode()

    resp = S.get(f"{BASE_URL}/api/pn-signin", params={
        "code": code, "gopage": "", "mgr": "1"
    }, allow_redirects=False)

    # Lấy CurrUser từ fragment của redirect URL
    location = resp.headers.get("Location", "")
    fragment = location.split("#")[-1]          # "/home?CurrUser=eyJ..."
    query    = fragment.split("?")[-1]          # "CurrUser=eyJ..."
    params   = parse_qs(query)
    curr_b64 = params.get("CurrUser", [""])[0]

    # Thêm padding nếu thiếu
    curr_b64 += "=" * (-len(curr_b64) % 4)
    user_data    = json.loads(base64.b64decode(curr_b64))
    access_token = user_data["access_token"]

    S.headers["Authorization"] = f"Bearer {access_token}"
    S.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Idpc": "0",
    })
    print("Login OK | Token:", access_token[:30], "...")
    return True

# ── Lấy học kì hiện tại ───────────────────────────────────────────────────────
def get_current_hocky():
    resp = S.post(f"{BASE_URL}/api/sch/w-locdshockytkbuser", json={})
    print("HocKy response:", resp.text[:500])
    ds   = resp.json()["data"]["ds_hoc_ky"]
    for hk in ds:
        if hk.get("hientai") or hk.get("is_hien_tai"):
            return hk
    return ds[0]  # fallback

# ── Lấy TKB toàn học kì ───────────────────────────────────────────────────────
def get_current_hocky():
    resp = S.post(f"{BASE_URL}/api/sch/w-locdshockytkbuser", json={})
    data = resp.json()["data"]
    # Dùng field hoc_ky_theo_ngay_hien_tai thay vì guess
    return data["hoc_ky_theo_ngay_hien_tai"]

def get_tkb(hoc_ky_id):
    resp = S.post(f"{BASE_URL}/api/sch/w-locdstktbanusertheohocky", json={
        "filter": {
            "hoc_ky": hoc_ky_id,
            "ten_hoc_ky": ""
        },
        "additional": {
            "paging": {"limit": 100, "page": 1},
            "ordering": [{"name": None, "order_type": None}]
        }
    })
    print("TKB response:", resp.text[:200])
    return resp.json()["data"]

# ── Build .ics ────────────────────────────────────────────────────────────────
def build_ics(data):
    tiet_map = {t["tiet"]: (t["gio_bat_dau"], t["gio_ket_thuc"])
                for t in data["ds_tiet_trong_ngay"]}

    cal = Calendar()
    cal.add("prodid", "-//VNUA Schedule//VN")
    cal.add("version", "2.0")
    cal.add("X-WR-CALNAME", "Lịch học VNUA")
    cal.add("X-WR-TIMEZONE", "Asia/Ho_Chi_Minh")

    count = 0
    for tuan in data["ds_tuan_tkb"]:
        for tkb in tuan["ds_thoi_khoa_bieu"]:
            if tkb.get("is_nghi_day"):
                continue

            tiet_bd = tkb["tiet_bat_dau"]
            tiet_kt = tiet_bd + tkb["so_tiet"] - 1
            tiet_kt = min(tiet_kt, max(tiet_map.keys()))

            if tiet_bd not in tiet_map:
                continue

            ngay     = datetime.fromisoformat(tkb["ngay_hoc"]).date()
            dt_start = datetime.strptime(f"{ngay} {tiet_map[tiet_bd][0]}", "%Y-%m-%d %H:%M")
            dt_end   = datetime.strptime(f"{ngay} {tiet_map[tiet_kt][1]}", "%Y-%m-%d %H:%M")

            ev = Event()
            ev.add("uid",      str(uuid.uuid4()))
            ev.add("summary",  tkb["ten_mon"])
            ev.add("dtstart",  dt_start)
            ev.add("dtend",    dt_end)
            ev.add("location", tkb["ma_phong"].split("-")[0].strip())
            ev.add("description", (
                f"GV: {tkb['ten_giang_vien']}\n"
                f"Phòng: {tkb['ma_phong']}\n"
                f"Tiết {tiet_bd}–{tiet_kt} | Nhóm {tkb['ma_nhom']}"
            ))
            cal.add_component(ev)
            count += 1

    print(f"Tạo {count} sự kiện")
    return cal.to_ical()

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    assert login(), "Login thất bại"

    hk_id = get_current_hocky()
    print(f"Học kì: {hk_id}")

    data = get_tkb(hk_id)
    ics  = build_ics(data)

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT, "wb") as f:
        f.write(ics)
    print(f"Saved: {OUTPUT}")
