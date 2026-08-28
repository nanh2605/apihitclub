import json
import threading
import time
import os
import logging
from urllib.request import urlopen, Request
from flask import Flask, jsonify
from collections import Counter
import random

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HOST = '0.0.0.0'
POLL_INTERVAL = 5
RETRY_DELAY = 5
MAX_HISTORY = 100

lock_100 = threading.Lock()
lock_101 = threading.Lock()

# Sửa id thành admin Duy Bảo
latest_result_100 = {
    "Phien": 0, "Xuc_xac_1": 0, "Xuc_xac_2": 0, "Xuc_xac_3": 0,
    "Tong": 0, "Ket_qua": "Chưa có", "id": "admin Duy Bảo",
    "Du_doan": "Chưa có", "Do_tin_cay": 0
}
latest_result_101 = {
    "Phien": 0, "Xuc_xac_1": 0, "Xuc_xac_2": 0, "Xuc_xac_3": 0,
    "Tong": 0, "Ket_qua": "Chưa có", "id": "admin Duy Bảo",
    "Du_doan": "Chưa có", "Do_tin_cay": 0
}

history_100 = []
history_101 = []

last_sid_100 = None
last_sid_101 = None
sid_for_tx = None

def get_tai_xiu(d1, d2, d3):
    total = d1 + d2 + d3
    return "Xỉu" if total <= 10 else "Tài"

def update_result(store, history, lock, result):
    with lock:
        store.clear()
        store.update(result)
        history.insert(0, result.copy())
        if len(history) > MAX_HISTORY:
            history.pop()

# === THUẬT TOÁN DỰ ĐOÁN ===

def analyze_pattern(history_data, window_size=10):
    """
    Phân tích mẫu hình từ lịch sử
    """
    if len(history_data) < window_size:
        return None
    
    recent = history_data[:window_size]
    results = [item['Ket_qua'] for item in recent if item['Ket_qua'] != 'Chưa có']
    
    if len(results) < 5:
        return None
    
    # Thống kê tần suất
    counter = Counter(results)
    total = len(results)
    
    tai_ratio = counter.get('Tài', 0) / total
    xiu_ratio = counter.get('Xỉu', 0) / total
    
    # Phân tích chuỗi
    consecutive = 1
    max_consecutive = 1
    current = results[0]
    for i in range(1, len(results)):
        if results[i] == current:
            consecutive += 1
        else:
            consecutive = 1
            current = results[i]
        max_consecutive = max(max_consecutive, consecutive)
    
    # Dự đoán
    prediction = {}
    
    # Chiến lược 1: Bắt bệt (nếu chuỗi dài >= 3)
    if max_consecutive >= 3:
        prediction['Ket_qua'] = current
        prediction['Do_tin_cay'] = min(0.85, 0.5 + max_consecutive * 0.08)
        prediction['Chien_luoc'] = 'Bắt bệt'
    
    # Chiến lược 2: Bắt cầu đảo (nếu tỷ lệ chênh lệch > 20%)
    elif abs(tai_ratio - xiu_ratio) >= 0.2:
        if tai_ratio < xiu_ratio:
            prediction['Ket_qua'] = 'Tài'
        else:
            prediction['Ket_qua'] = 'Xỉu'
        prediction['Do_tin_cay'] = 0.7
        prediction['Chien_luoc'] = 'Bắt cầu đảo'
    
    # Chiến lược 3: Theo xu hướng
    elif len(results) >= 4:
        last_4 = results[:4]
        if last_4.count('Tài') >= 3:
            prediction['Ket_qua'] = 'Tài'
            prediction['Do_tin_cay'] = 0.65
            prediction['Chien_luoc'] = 'Theo xu hướng Tài'
        elif last_4.count('Xỉu') >= 3:
            prediction['Ket_qua'] = 'Xỉu'
            prediction['Do_tin_cay'] = 0.65
            prediction['Chien_luoc'] = 'Theo xu hướng Xỉu'
        else:
            # Mô hình Markov đơn giản
            if results[0] == results[1] and results[1] != results[2]:
                prediction['Ket_qua'] = results[2]
                prediction['Do_tin_cay'] = 0.6
                prediction['Chien_luoc'] = 'Mô hình 2-1'
            else:
                prediction['Ket_qua'] = random.choice(['Tài', 'Xỉu'])
                prediction['Do_tin_cay'] = 0.5
                prediction['Chien_luoc'] = 'Dự đoán ngẫu nhiên'
    else:
        prediction['Ket_qua'] = random.choice(['Tài', 'Xỉu'])
        prediction['Do_tin_cay'] = 0.5
        prediction['Chien_luoc'] = 'Dự đoán ngẫu nhiên'
    
    # Dự đoán tổng điểm
    recent_tong = [item['Tong'] for item in recent if item['Tong'] > 0]
    if recent_tong:
        avg_tong = sum(recent_tong) / len(recent_tong)
        if prediction['Ket_qua'] == 'Tài':
            tong_du_doan = int(avg_tong + random.randint(1, 5))
        else:
            tong_du_doan = int(avg_tong - random.randint(1, 5))
        prediction['Tong_du_doan'] = max(3, min(18, tong_du_doan))
    else:
        prediction['Tong_du_doan'] = random.randint(3, 18)
    
    prediction['Ty_le_Tai'] = round(tai_ratio * 100, 1)
    prediction['Ty_le_Xiu'] = round(xiu_ratio * 100, 1)
    prediction['Chuoi_lien_tiep'] = max_consecutive
    
    return prediction

def predict_next(history_data):
    """
    Dự đoán kết quả tiếp theo
    """
    if len(history_data) < 5:
        return {
            'Ket_qua': 'Chưa đủ dữ liệu',
            'Do_tin_cay': 0,
            'So_van_can': 5 - len(history_data)
        }
    
    # Phân tích với nhiều cửa sổ khác nhau
    predictions = []
    for window in [5, 7, 10, 12, 15]:
        pred = analyze_pattern(history_data, window)
        if pred:
            predictions.append(pred)
    
    if not predictions:
        return {
            'Ket_qua': random.choice(['Tài', 'Xỉu']),
            'Do_tin_cay': 0.5,
            'Chien_luoc': 'Mặc định'
        }
    
    # Tổng hợp kết quả
    ket_qua_votes = [p['Ket_qua'] for p in predictions]
    do_tin_cay_avg = sum(p['Do_tin_cay'] for p in predictions) / len(predictions)
    tong_du_doan = int(sum(p.get('Tong_du_doan', 9) for p in predictions) / len(predictions))
    
    final_prediction = Counter(ket_qua_votes).most_common(1)[0][0]
    
    # Lấy chiến lược phổ biến nhất
    chien_luoc_list = [p.get('Chien_luoc', 'Khác') for p in predictions]
    main_strategy = Counter(chien_luoc_list).most_common(1)[0][0]
    
    return {
        'Ket_qua': final_prediction,
        'Do_tin_cay': round(do_tin_cay_avg, 3),
        'Tong_du_doan': tong_du_doan,
        'Chien_luoc': main_strategy,
        'So_mau_phan_tich': len(predictions)
    }

def poll_api(gid, lock, result_store, history, is_md5):
    global last_sid_100, last_sid_101, sid_for_tx
    url = f"https://jakpotgwab.geightdors.net/glms/v1/notify/taixiu?platform_id=g8&gid={gid}"
    while True:
        try:
            req = Request(url, headers={'User-Agent': 'Python-Proxy/1.0'})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') == 'OK' and isinstance(data.get('data'), list):
                for game in data['data']:
                    cmd = game.get("cmd")
                    if not is_md5 and cmd == 1008:
                        sid_for_tx = game.get("sid")
                for game in data['data']:
                    cmd = game.get("cmd")
                    if is_md5 and cmd == 2006:
                        sid = game.get("sid")
                        d1, d2, d3 = game.get("d1"), game.get("d2"), game.get("d3")
                        if sid and sid != last_sid_101 and None not in (d1, d2, d3):
                            last_sid_101 = sid
                            total = d1 + d2 + d3
                            ket_qua = get_tai_xiu(d1, d2, d3)
                            
                            # Dự đoán cho ván tiếp theo
                            du_doan = predict_next(history)
                            
                            result = {
                                "Phien": sid,
                                "Xuc_xac_1": d1,
                                "Xuc_xac_2": d2,
                                "Xuc_xac_3": d3,
                                "Tong": total,
                                "Ket_qua": ket_qua,
                                "id": "admin Duy Bảo",
                                "Du_doan": du_doan.get('Ket_qua', 'Chưa có'),
                                "Do_tin_cay": du_doan.get('Do_tin_cay', 0),
                                "Tong_du_doan": du_doan.get('Tong_du_doan', 0),
                                "Chien_luoc": du_doan.get('Chien_luoc', 'Đang phân tích'),
                                "So_van_phan_tich": len(history)
                            }
                            update_result(result_store, history, lock, result)
                            logger.info(f"[MD5] Phiên {sid} - Tổng: {total}, Kết quả: {ket_qua}, Dự đoán: {du_doan.get('Ket_qua', 'N/A')} ({du_doan.get('Do_tin_cay', 0)})")
                    elif not is_md5 and cmd == 1003:
                        d1, d2, d3 = game.get("d1"), game.get("d2"), game.get("d3")
                        sid = sid_for_tx
                        if sid and sid != last_sid_100 and None not in (d1, d2, d3):
                            last_sid_100 = sid
                            total = d1 + d2 + d3
                            ket_qua = get_tai_xiu(d1, d2, d3)
                            
                            # Dự đoán cho ván tiếp theo
                            du_doan = predict_next(history)
                            
                            result = {
                                "Phien": sid,
                                "Xuc_xac_1": d1,
                                "Xuc_xac_2": d2,
                                "Xuc_xac_3": d3,
                                "Tong": total,
                                "Ket_qua": ket_qua,
                                "id": "admin Duy Bảo",
                                "Du_doan": du_doan.get('Ket_qua', 'Chưa có'),
                                "Do_tin_cay": du_doan.get('Do_tin_cay', 0),
                                "Tong_du_doan": du_doan.get('Tong_du_doan', 0),
                                "Chien_luoc": du_doan.get('Chien_luoc', 'Đang phân tích'),
                                "So_van_phan_tich": len(history)
                            }
                            update_result(result_store, history, lock, result)
                            logger.info(f"[TX] Phiên {sid} - Tổng: {total}, Kết quả: {ket_qua}, Dự đoán: {du_doan.get('Ket_qua', 'N/A')} ({du_doan.get('Do_tin_cay', 0)})")
                            sid_for_tx = None
        except Exception as e:
            logger.error(f"Lỗi khi lấy dữ liệu API {gid}: {e}")
            time.sleep(RETRY_DELAY)
        time.sleep(POLL_INTERVAL)

app = Flask(__name__)

@app.route("/api/taixiu", methods=["GET"])
def get_taixiu_100():
    with lock_100:
        return jsonify(latest_result_100)

@app.route("/api/taixiumd5", methods=["GET"])
def get_taixiu_101():
    with lock_101:
        return jsonify(latest_result_101)

@app.route("/api/history", methods=["GET"])
def get_history():
    with lock_100, lock_101:
        return jsonify({
            "taixiu": history_100,
            "taixiumd5": history_101
        })

@app.route("/")
def index():
    return """
    API Server for TaiXiu is running. 
    Endpoints: 
    - /api/taixiu (có dự đoán ván tiếp theo)
    - /api/taixiumd5 (có dự đoán ván tiếp theo)
    - /api/history
    """

if __name__ == "__main__":
    logger.info("Khởi động hệ thống API Tài Xỉu với AI dự đoán...")
    thread_100 = threading.Thread(target=poll_api, args=("vgmn_100", lock_100, latest_result_100, history_100, False), daemon=True)
    thread_101 = threading.Thread(target=poll_api, args=("vgmn_101", lock_101, latest_result_101, history_101, True), daemon=True)
    thread_100.start()
    thread_101.start()
    logger.info("Đã bắt đầu polling dữ liệu.")
    port = int(os.environ.get("PORT", 8000))
    app.run(host=HOST, port=port)
