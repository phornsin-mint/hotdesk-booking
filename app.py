from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from uuid import uuid4
from datetime import datetime
import json
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # คีย์สำหรับ session

# ไฟล์ฐานข้อมูล JSON
DB_FILE = 'database.json'

# ---------- Utilities ----------
def load_data():
    """โหลดข้อมูลจาก JSON"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"bookings": []}
    return {"bookings": []}

def save_data(data):
    """บันทึกข้อมูลลง JSON"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def compute_status(rec) -> str:
    """
    คำนวณสถานะการจอง:
      - completed: เวลาที่จองเริ่มต้นผ่านมาแล้ว
      - confirmed: เริ่มต้นในอนาคต (ใช้กับรายการที่ถูกบันทึกแล้ว)
    """
    try:
        dt = datetime.strptime(f"{rec['date']} {rec['start_time']}", "%Y-%m-%d %H:%M")
        return "completed" if dt < datetime.now() else "confirmed"
    except Exception:
        return "confirmed"

# ---------- Routes ----------
@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))  # บังคับล็อกอิน
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if username and password:
            session['user'] = username  # เก็บ session
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# -------- Booking page / create booking --------
@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            data = load_data()
            username = session.get('user', 'Guest')
            date = request.form.get('date', '').strip()
            start_time = request.form.get('start_time', '').strip()  # HH:MM
            end_time = request.form.get('end_time', '').strip()      # HH:MM
            room = request.form.get('room', '').strip()
            seat = request.form.get('seat', '').strip()

            # ตรวจสอบข้อมูลที่จำเป็น
            if not date or not start_time or not end_time or not room or not seat:
                return jsonify({"error": "กรุณากรอกข้อมูลให้ครบถ้วน"}), 400

            # กันกรณีเวลาผิด
            if end_time <= start_time:
                return jsonify({"error": "กรุณาเลือกช่วงเวลาให้ถูกต้อง"}), 400

            # ตรวจสอบว่าที่นั่งนี้ถูกจองซ้อนช่วงเวลากันหรือไม่ (เทียบเป็นสตริงเวลา HH:MM ได้)
            for b in data.get('bookings', []):
                if (
                    b.get('room') == room and
                    b.get('date') == date and
                    str(b.get('seat')) == str(seat) and
                    not (end_time <= b.get('start_time') or start_time >= b.get('end_time'))
                ):
                    return jsonify({"error": "ที่นั่งนี้ถูกจองในช่วงเวลาดังกล่าวแล้ว!"}), 400

            # บันทึกการจอง (ใส่ id ให้ทุกครั้ง)
            new_booking = {
                "id": str(uuid4()),
                "user": username,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "room": room,
                "seat": seat
            }
            data.setdefault('bookings', []).append(new_booking)
            save_data(data)

            return jsonify({"success": True, "message": "จองสำเร็จ!", "id": new_booking["id"]}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return render_template('booking.html')

# (เดิม) ยกเลิกตาม seat + user — คงไว้เพื่อความเข้ากันได้
@app.route('/cancel/<seat>', methods=['POST'])
def cancel_booking(seat):
    if 'user' not in session:
        return redirect(url_for('login'))
    username = session['user']
    data = load_data()

    new_bookings = [
        b for b in data.get('bookings', [])
        if not (str(b.get('seat')) == str(seat) and b.get('user') == username)
    ]

    if len(new_bookings) == len(data.get('bookings', [])):
        return jsonify({"error": "คุณไม่มีสิทธิ์ยกเลิกที่นั่งนี้"}), 403

    data['bookings'] = new_bookings
    save_data(data)
    return jsonify({"success": True, "message": "ยกเลิกการจองสำเร็จ!"}), 200

# --------- APIs used by booking.html ----------
@app.route('/api/booked_seats', methods=['GET'])
def get_booked_seats():
    room = request.args.get('room', '').strip()
    date = request.args.get('date', '').strip()
    start_time = request.args.get('start_time', '').strip()
    end_time = request.args.get('end_time', '').strip()

    try:
        data = load_data()
        result = []
        for b in data.get('bookings', []):
            b_room = b.get('room')
            b_date = b.get('date')
            b_start = b.get('start_time')
            b_end = b.get('end_time')
            b_seat = b.get('seat')
            b_user = b.get('user', 'ไม่ทราบชื่อ')

            if not (b_room and b_date and b_start and b_end and b_seat):
                continue

            # เวลาทับซ้อน
            if b_room == room and b_date == date and not (end_time <= b_start or start_time >= b_end):
                result.append({"seat": str(b_seat), "user": b_user})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/room_status', methods=['GET'])
def api_room_status():
    date = request.args.get('date', '').strip()
    data = load_data()
    room_status = {"1": 10, "2": 20, "3": 15, "4": 10, "5": 30}
    booked = {
        room: sum(1 for b in data.get('bookings', [])
                  if b.get('room') == room and b.get('date') == date)
        for room in room_status
    }
    return jsonify([
        {"id": room, "name": f"ห้อง {room}",
         "availableSeats": room_status[room] - booked.get(room, 0),
         "totalSeats": room_status[room]}
        for room in room_status
    ])

@app.route('/api/bookings', methods=['GET'])
def api_bookings():
    date = request.args.get('date', '').strip()
    data = load_data()
    filtered = [b for b in data.get('bookings', []) if b.get('date') == date] if date else data.get('bookings', [])
    return jsonify(filtered)

# ---------- My Reservations (ใหม่) ----------
@app.route('/my-reservations')
def my_reservations_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('my_reservations.html')

@app.get('/api/my_reservations')
def api_my_reservations():
    """คืนการจองเฉพาะของผู้ใช้ที่ล็อกอินอยู่"""
    if 'user' not in session:
        return jsonify([])

    username = session['user']
    db = load_data()
    out = []
    for b in db.get('bookings', []):
        if b.get('user') != username:
            continue
        rec = {
            "id": b.get("id") or "",
            "date": b.get("date", ""),
            "start_time": b.get("start_time", ""),
            "end_time": b.get("end_time", ""),
            "room": b.get("room", ""),
            "seat": b.get("seat", ""),
            "status": compute_status({"date": b.get("date", ""), "start_time": b.get("start_time", "")})
        }
        out.append(rec)
    return jsonify(out)

@app.post('/api/cancel_booking')
def api_cancel_booking():
    """ยกเลิกการจองตาม id (เฉพาะเจ้าของเท่านั้น)"""
    if 'user' not in session:
        return jsonify({"error": "unauthorized"}), 401

    username = session['user']
    payload = request.get_json(silent=True) or {}
    bid = str(payload.get('id', '')).strip()
    if not bid:
        return jsonify({"error": "missing id"}), 400

    db = load_data()
    changed = False
    new_list = []
    for b in db.get('bookings', []):
        if str(b.get('id')) == bid:
            if b.get('user') != username:
                return jsonify({"error": "คุณไม่มีสิทธิ์ยกเลิกการจองนี้"}), 403
            changed = True
            continue
        new_list.append(b)

    if not changed:
        return jsonify({"error": "ไม่พบการจอง"}), 404

    db['bookings'] = new_list
    save_data(db)
    return jsonify({"ok": True, "message": "ยกเลิกการจองสำเร็จ"})

# ---------- Main ----------
if __name__ == '__main__':
    app.run(debug=True)
