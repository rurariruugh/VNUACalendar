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
    code = base64.b64encode(json.dumps({
        "username": USERNAME,
        "password": PASSWORD,
        "uri": f"{BASE_URL}/#/home"
    }).encode()).decode()

    resp = S.get(f"{BASE_URL}/api/pn-signin", params={
        "code": code, "gopage": "", "mgr": "1"
    })
    print("Login:", resp.status_code)
    return resp.ok

# ── Lấy học kì hiện tại ───────────────────────────────────────────────────────
def get_current_hocky():
    resp = S.get(f"{BASE_URL}/api/sch/w-locdshockytkbuser")
    ds   = resp.json()["data"]["ds_hoc_ky"]
    for hk in ds:
        if hk.get("hientai") or hk.get("is_hien_tai"):
            return hk
    return ds[0]  # fallback

# ── Lấy TKB toàn học kì ───────────────────────────────────────────────────────
def get_tkb(hoc_ky_id):
    resp = S.post(f"{BASE_URL}/api/sch/w-locdstktbanusertheohocky", json={
        "hoc_ky": hoc_ky_id
    })
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

    hk = get_current_hocky()
    hk_id = hk.get("hoc_ky") or hk.get("id") or hk.get("nhhk")
    print(f"Học kì: {hk_id}")

    data = get_tkb(hk_id)
    ics  = build_ics(data)

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT, "wb") as f:
        f.write(ics)
    print(f"Saved: {OUTPUT}")
