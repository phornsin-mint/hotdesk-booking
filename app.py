from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # คีย์สำหรับ session

# ไฟล์ฐานข้อมูล JSON
DB_FILE = 'database.json'

# โหลดข้อมูลจาก JSON
def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"bookings": []}
    return {"bookings": []}

# บันทึกข้อมูลลง JSON
def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))  # บังคับล็อกอิน
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username and password:
            session['user'] = username  # เก็บ session
            return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            data = load_data()
            username = session.get('user', 'Guest')
            date = request.form['date']
            start_time = request.form['start_time']
            end_time = request.form['end_time']
            room = request.form['room']
            seat = request.form['seat']

            # ตรวจสอบข้อมูลที่จำเป็น
            if not date or not start_time or not end_time or not room or not seat:
                return jsonify({"error": "กรุณากรอกข้อมูลให้ครบถ้วน"}), 400

            # ตรวจสอบว่าที่นั่งนี้ถูกจองซ้อนช่วงเวลากันหรือไม่
            for b in data['bookings']:
                if (
                    b['room'] == room and
                    b['date'] == date and
                    b['seat'] == seat and
                    not (end_time <= b['start_time'] or start_time >= b['end_time'])  # เวลาทับซ้อน
                ):
                    return jsonify({"error": "ที่นั่งนี้ถูกจองในช่วงเวลาดังกล่าวแล้ว!"}), 400

            # บันทึกการจอง
            new_booking = {
                "user": username,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "room": room,
                "seat": seat
            }
            data['bookings'].append(new_booking)
            save_data(data)

            return jsonify({"success": True, "message": "จองสำเร็จ!"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return render_template('booking.html')

@app.route('/cancel/<seat>', methods=['POST'])
def cancel_booking(seat):
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']
    data = load_data()

    new_bookings = [b for b in data['bookings'] if not (b['seat'] == seat and b['user'] == username)]

    if len(new_bookings) == len(data['bookings']):
        return jsonify({"error": "คุณไม่มีสิทธิ์ยกเลิกที่นั่งนี้"}), 403

    data['bookings'] = new_bookings
    save_data(data)
    return jsonify({"success": True, "message": "ยกเลิกการจองสำเร็จ!"}), 200

@app.route('/api/booked_seats', methods=['GET'])
def get_booked_seats():
    room = request.args.get('room', '')
    date = request.args.get('date', '')
    start_time = request.args.get('start_time', '')
    end_time = request.args.get('end_time', '')

    try:
        data = load_data()
        result = []

        for b in data['bookings']:
            # ใช้ .get() เพื่อป้องกัน KeyError
            b_room = b.get('room')
            b_date = b.get('date')
            b_start = b.get('start_time')
            b_end = b.get('end_time')
            b_seat = b.get('seat')
            b_user = b.get('user', 'ไม่ทราบชื่อ')

            # ข้ามรายการที่ไม่มีข้อมูลสำคัญ
            if not (b_room and b_date and b_start and b_end and b_seat):
                continue

            # เงื่อนไขเวลาทับซ้อน
            if b_room == room and b_date == date and not (end_time <= b_start or start_time >= b_end):
                result.append({
                    "seat": str(b_seat),
                    "user": b_user
                })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/room_status', methods=['GET'])
def api_room_status():
    date = request.args.get('date', '')

    data = load_data()
    room_status = { "1": 10, "2": 20, "3": 15, "4": 10, "5": 30 }
    booked = { room: sum(1 for b in data['bookings'] if b['room'] == room and b['date'] == date) for room in room_status }

    return jsonify([
        {"id": room, "name": f"ห้อง {room}", "availableSeats": room_status[room] - booked.get(room, 0), "totalSeats": room_status[room]}
        for room in room_status
    ])

@app.route('/api/bookings', methods=['GET'])
def api_bookings():
    date = request.args.get('date', '')

    data = load_data()
    filtered_bookings = [b for b in data['bookings'] if b['date'] == date] if date else data['bookings']

    return jsonify(filtered_bookings)

if __name__ == '__main__':
    app.run(debug=True)
