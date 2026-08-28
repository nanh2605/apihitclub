import json
import threading
import time
import os
import logging
from urllib.request import urlopen, Request
from flask import Flask, jsonify, request
from datetime import datetime
import random

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HOST = '0.0.0.0'
POLL_INTERVAL = 5
RETRY_DELAY = 5
MAX_HISTORY = 100

lock_100 = threading.Lock()
lock_101 = threading.Lock()

# ============== FILE LƯU TRỮ ==============
DATA_FILE_100 = 'data_taixiu_100.json'
DATA_FILE_101 = 'data_taixiu_101.json'

def save_data(file_path, data):
    """Lưu dữ liệu vào file JSON"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Lỗi lưu file {file_path}: {e}")
        return False

def load_data(file_path, default_data):
    """Đọc dữ liệu từ file JSON"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for key in default_data:
                        if key not in data:
                            data[key] = default_data[key]
                return data
    except Exception as e:
        logger.error(f"Lỗi đọc file {file_path}: {e}")
    return default_data.copy()

def load_history(file_path):
    """Đọc lịch sử từ file"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Lỗi đọc history {file_path}: {e}")
    return []

def save_history(file_path, history):
    """Lưu lịch sử vào file"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Lỗi lưu history {file_path}: {e}")
        return False

# ============== DỮ LIỆU KHỞI TẠO ==============

default_result = {
    "Phien": 0,
    "Xuc_xac_1": 0,
    "Xuc_xac_2": 0,
    "Xuc_xac_3": 0,
    "Tong": 0,
    "Ket_qua": "Chưa có",
    "Du_doan": "Chưa đủ dữ liệu",
    "Do_tin_cay": 0,
    "admin": "Duy Bảo"
}

# Khởi tạo dữ liệu từ file hoặc tạo mới
latest_result_100 = load_data(DATA_FILE_100, default_result)
latest_result_101 = load_data(DATA_FILE_101, default_result)

# Đảm bảo có admin
latest_result_100["admin"] = "Duy Bảo"
latest_result_101["admin"] = "Duy Bảo"

# Load lịch sử
history_100 = load_history('history_100.json')
history_101 = load_history('history_101.json')

# Đảm bảo MAX_HISTORY
if len(history_100) > MAX_HISTORY:
    history_100 = history_100[:MAX_HISTORY]
if len(history_101) > MAX_HISTORY:
    history_101 = history_101[:MAX_HISTORY]

# ============== LƯU LỊCH SỬ CHO DỰ ĐOÁN ==============
predict_history_100 = load_history('predict_history_100.json')
predict_history_101 = load_history('predict_history_101.json')
MAX_PREDICT_HISTORY = 100

last_sid_100 = None
last_sid_101 = None
sid_for_tx = None

# Biến lưu phiên hiện tại để kiểm tra cập nhật
current_session_100 = 0
current_session_101 = 0

# ============== THUẬT TOÁN DỰ ĐOÁN ==============

def du_doan_ket_qua(predict_history):
    """
    Dự đoán kết quả tiếp theo
    predict_history: list các dict có key 'ket_qua'
    """
    
    if len(predict_history) < 3:
        return {
            "Du_doan": "Chưa đủ dữ liệu",
            "Do_tin_cay": 0,
            "Ly_do": f"Cần ít nhất 3 phiên, hiện có {len(predict_history)} phiên"
        }
    
    # Lấy kết quả gần nhất
    recent = [r["ket_qua"] for r in predict_history[:10]]
    tai_count = recent.count("Tài")
    xiu_count = recent.count("Xỉu")
    total = len(recent)
    
    # ===== LOGIC DỰ ĐOÁN =====
    
    # 1. Kiểm tra chuỗi 3 phiên liên tiếp
    last_3 = predict_history[:3]
    last_3_result = [r["ket_qua"] for r in last_3]
    
    if last_3_result == ["Tài", "Tài", "Tài"]:
        return {
            "Du_doan": "Xỉu",
            "Do_tin_cay": 72,
            "Ly_do": "3 phiên Tài liên tiếp, khả năng đảo chiều sang Xỉu"
        }
    
    if last_3_result == ["Xỉu", "Xỉu", "Xỉu"]:
        return {
            "Du_doan": "Tài",
            "Do_tin_cay": 72,
            "Ly_do": "3 phiên Xỉu liên tiếp, khả năng đảo chiều sang Tài"
        }
    
    # 2. Pattern xen kẽ
    if len(last_3_result) >= 3:
        if last_3_result[0] == "Tài" and last_3_result[1] == "Xỉu" and last_3_result[2] == "Tài":
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": 65,
                "Ly_do": "Pattern Tài-Xỉu-Tài, dự đoán Xỉu tiếp theo"
            }
        if last_3_result[0] == "Xỉu" and last_3_result[1] == "Tài" and last_3_result[2] == "Xỉu":
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": 65,
                "Ly_do": "Pattern Xỉu-Tài-Xỉu, dự đoán Tài tiếp theo"
            }
    
    # 3. Tỷ lệ
    tai_ratio = tai_count / total * 100
    xiu_ratio = xiu_count / total * 100
    
    if tai_ratio >= 65:
        return {
            "Du_doan": "Tài",
            "Do_tin_cay": round(tai_ratio, 1),
            "Ly_do": f"Tài chiếm {round(tai_ratio, 1)}% trong {total} phiên gần nhất"
        }
    
    if xiu_ratio >= 65:
        return {
            "Du_doan": "Xỉu",
            "Do_tin_cay": round(xiu_ratio, 1),
            "Ly_do": f"Xỉu chiếm {round(xiu_ratio, 1)}% trong {total} phiên gần nhất"
        }
    
    # 4. Tổng điểm trung bình
    tong_list = [r.get("tong", 0) for r in predict_history[:5] if r.get("tong")]
    if tong_list:
        tong_trung_binh = sum(tong_list) / len(tong_list)
        
        if tong_trung_binh > 11:
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": 55,
                "Ly_do": f"Tổng TB {round(tong_trung_binh, 1)} > 11, nghiêng về Tài"
            }
        
        if tong_trung_binh < 10:
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": 55,
                "Ly_do": f"Tổng TB {round(tong_trung_binh, 1)} < 10, nghiêng về Xỉu"
            }
    
    # 5. Mặc định
    if tai_count > xiu_count:
        return {
            "Du_doan": "Tài",
            "Do_tin_cay": 52,
            "Ly_do": f"Tài có xu hướng nhỉnh hơn ({tai_count}/{total} phiên)"
        }
    else:
        return {
            "Du_doan": "Xỉu",
            "Do_tin_cay": 52,
            "Ly_do": f"Xỉu có xu hướng nhỉnh hơn ({xiu_count}/{total} phiên)"
        }

# ============== HÀM CHÍNH ==============

def get_tai_xiu(d1, d2, d3):
    total = d1 + d2 + d3
    return "Xỉu" if total <= 10 else "Tài"

def update_result(store, history, lock, result, predict_history, is_md5, data_file, hist_file, pred_file):
    global current_session_100, current_session_101
    
    with lock:
        # Lấy phiên cũ để so sánh
        old_phien = store.get("Phien", 0)
        
        store.clear()
        store.update(result)
        history.insert(0, result.copy())
        if len(history) > MAX_HISTORY:
            history.pop()
        
        # Lưu vào lịch sử dự đoán
        if result.get("Ket_qua") and result.get("Ket_qua") != "Chưa có":
            predict_history.insert(0, {
                "phien": result.get("Phien"),
                "ket_qua": result.get("Ket_qua"),
                "tong": result.get("Tong"),
                "xuc_xac": [result.get("Xuc_xac_1"), result.get("Xuc_xac_2"), result.get("Xuc_xac_3")]
            })
            if len(predict_history) > MAX_PREDICT_HISTORY:
                predict_history.pop()
        
        # Cập nhật dự đoán vào store
        du_doan_result = du_doan_ket_qua(predict_history)
        store["Du_doan"] = du_doan_result.get("Du_doan", "Chưa đủ dữ liệu")
        store["Do_tin_cay"] = du_doan_result.get("Do_tin_cay", 0)
        
        # Lưu vào file
        save_data(data_file, store)
        save_history(hist_file, history)
        save_history(pred_file, predict_history)
        
        # Kiểm tra xem có phiên mới không
        new_phien = store.get("Phien", 0)
        if new_phien != old_phien and new_phien > 0:
            if is_md5:
                current_session_101 = new_phien
                logger.info(f"[MD5] 🔄 PHIÊN MỚI: {new_phien} - Web sẽ tự động cập nhật")
            else:
                current_session_100 = new_phien
                logger.info(f"[TX] 🔄 PHIÊN MỚI: {new_phien} - Web sẽ tự động cập nhật")

# ============== POLL API ==============

def poll_api(gid, lock, result_store, history, is_md5):
    global last_sid_100, last_sid_101, sid_for_tx
    url = f"https://jakpotgwab.geightdors.net/glms/v1/notify/taixiu?platform_id=g8&gid={gid}"
    
    # Chọn file và history tương ứng
    if is_md5:
        predict_history = predict_history_101
        data_file = DATA_FILE_101
        hist_file = 'history_101.json'
        pred_file = 'predict_history_101.json'
    else:
        predict_history = predict_history_100
        data_file = DATA_FILE_100
        hist_file = 'history_100.json'
        pred_file = 'predict_history_100.json'
    
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
                            result = {
                                "Phien": sid,
                                "Xuc_xac_1": d1,
                                "Xuc_xac_2": d2,
                                "Xuc_xac_3": d3,
                                "Tong": total,
                                "Ket_qua": ket_qua,
                                "admin": "Duy Bảo"
                            }
                            update_result(result_store, history, lock, result, predict_history_101, True, 
                                        data_file, hist_file, pred_file)
                            logger.info(f"[MD5] Phiên {sid} - Tổng: {total}, Kết quả: {ket_qua}")
                    elif not is_md5 and cmd == 1003:
                        d1, d2, d3 = game.get("d1"), game.get("d2"), game.get("d3")
                        sid = sid_for_tx
                        if sid and sid != last_sid_100 and None not in (d1, d2, d3):
                            last_sid_100 = sid
                            total = d1 + d2 + d3
                            ket_qua = get_tai_xiu(d1, d2, d3)
                            result = {
                                "Phien": sid,
                                "Xuc_xac_1": d1,
                                "Xuc_xac_2": d2,
                                "Xuc_xac_3": d3,
                                "Tong": total,
                                "Ket_qua": ket_qua,
                                "admin": "Duy Bảo"
                            }
                            update_result(result_store, history, lock, result, predict_history_100, False,
                                        data_file, hist_file, pred_file)
                            logger.info(f"[TX] Phiên {sid} - Tổng: {total}, Kết quả: {ket_qua}")
                            sid_for_tx = None
        except Exception as e:
            logger.error(f"Lỗi khi lấy dữ liệu API {gid}: {e}")
            time.sleep(RETRY_DELAY)
        time.sleep(POLL_INTERVAL)

# ============== FLASK APP ==============

app = Flask(__name__)

# ============== API ==============

@app.route("/api/taixiu", methods=["GET"])
def get_taixiu_100():
    with lock_100:
        data = load_data(DATA_FILE_100, default_result)
        data["admin"] = "Duy Bảo"
        response = jsonify(data)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

@app.route("/api/taixiumd5", methods=["GET"])
def get_taixiu_101():
    with lock_101:
        data = load_data(DATA_FILE_101, default_result)
        data["admin"] = "Duy Bảo"
        response = jsonify(data)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

@app.route("/api/history", methods=["GET"])
def get_history():
    limit = request.args.get('limit', 50, type=int)
    with lock_100, lock_101:
        hist_100 = load_history('history_100.json')
        hist_101 = load_history('history_101.json')
        response = jsonify({
            "taixiu": hist_100[:limit],
            "taixiumd5": hist_101[:limit],
            "admin": "Duy Bảo"
        })
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

@app.route("/api/check_update", methods=["GET"])
def check_update():
    """API kiểm tra xem có phiên mới không"""
    gid = request.args.get('gid', '100')
    current = request.args.get('current', 0, type=int)
    
    if gid == '100':
        latest = current_session_100
    else:
        latest = current_session_101
    
    return jsonify({
        "has_update": latest > current,
        "current_session": current,
        "latest_session": latest,
        "admin": "Duy Bảo"
    })

# ============== TRANG CHỦ - TỰ ĐỘNG CẬP NHẬT ==============

@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
        <title>🎲 HIT API - Tài Xỉu</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background: #0a0e17;
                color: #e0e0e0;
                padding: 16px;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: flex-start;
            }
            .container {
                max-width: 800px;
                width: 100%;
                margin: 0 auto;
            }
            .header {
                background: linear-gradient(135deg, #1a1a2e, #16213e);
                border-radius: 16px;
                padding: 20px;
                margin-bottom: 20px;
                text-align: center;
                border: 1px solid #2a3a5e;
                position: relative;
            }
            .header h1 {
                font-size: 24px;
                color: #ffd700;
                margin-bottom: 4px;
            }
            .header .admin {
                font-size: 14px;
                color: #88ccff;
                opacity: 0.8;
            }
            .header .status {
                font-size: 13px;
                color: #66dd88;
                margin-top: 6px;
            }
            .header .auto-update {
                font-size: 12px;
                color: #88ccff;
                margin-top: 4px;
                animation: blink 2s infinite;
            }
            @keyframes blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.3; }
            }
            .card {
                background: #111827;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 16px;
                border: 1px solid #1f2937;
                transition: all 0.3s ease;
            }
            .card.new-update {
                border-color: #ffd700;
                box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
            }
            .card h2 {
                font-size: 16px;
                color: #88ccff;
                margin-bottom: 12px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .card h2 .badge {
                font-size: 11px;
                background: #1f2937;
                padding: 2px 10px;
                border-radius: 20px;
                color: #9ca3af;
            }
            .card h2 .update-indicator {
                font-size: 11px;
                color: #ffd700;
                display: none;
            }
            .card h2 .update-indicator.show {
                display: inline;
                animation: blink 1s infinite;
            }
            .dice {
                display: flex;
                gap: 12px;
                justify-content: center;
                margin: 12px 0;
            }
            .dice-box {
                background: #1a2236;
                border-radius: 12px;
                padding: 12px 16px;
                text-align: center;
                min-width: 60px;
                border: 1px solid #2a3a5e;
                transition: all 0.5s ease;
            }
            .dice-box.pop {
                animation: pop 0.5s ease;
            }
            @keyframes pop {
                0% { transform: scale(1); }
                50% { transform: scale(1.2); background: #2a3a5e; }
                100% { transform: scale(1); }
            }
            .dice-box .number {
                font-size: 32px;
                font-weight: 700;
                transition: all 0.3s ease;
            }
            .dice-box .number.pop-number {
                animation: popNumber 0.5s ease;
            }
            @keyframes popNumber {
                0% { transform: scale(1); }
                50% { transform: scale(1.5); color: #ffd700; }
                100% { transform: scale(1); }
            }
            .dice-box .label {
                font-size: 11px;
                color: #6b7a8f;
                margin-top: 2px;
            }
            .result-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 0;
                border-bottom: 1px solid #1f2937;
                flex-wrap: wrap;
                gap: 8px;
            }
            .result-row:last-child {
                border-bottom: none;
            }
            .result-row .label {
                font-size: 14px;
                color: #9ca3af;
            }
            .result-row .value {
                font-size: 16px;
                font-weight: 600;
                transition: all 0.3s ease;
            }
            .result-row .value.pulse {
                animation: pulse 0.5s ease;
            }
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.3); }
                100% { transform: scale(1); }
            }
            .value.tai {
                color: #ff6b6b;
            }
            .value.xiu {
                color: #4ecdc4;
            }
            .value.gold {
                color: #ffd700;
            }
            .value.blue {
                color: #88ccff;
            }
            .predict-box {
                background: #0f1a2e;
                border-radius: 10px;
                padding: 14px;
                margin-top: 10px;
                border: 1px solid #1f3a5e;
                transition: all 0.5s ease;
            }
            .predict-box.new-predict {
                border-color: #ffd700;
                background: #1a2a3a;
            }
            .predict-box .title {
                font-size: 13px;
                color: #9ca3af;
                margin-bottom: 6px;
            }
            .predict-box .main {
                font-size: 22px;
                font-weight: 700;
                transition: all 0.3s ease;
            }
            .predict-box .main.tai {
                color: #ff6b6b;
            }
            .predict-box .main.xiu {
                color: #4ecdc4;
            }
            .predict-box .main.pop-predict {
                animation: popPredict 0.5s ease;
            }
            @keyframes popPredict {
                0% { transform: scale(1); }
                50% { transform: scale(1.3); }
                100% { transform: scale(1); }
            }
            .predict-box .sub {
                font-size: 13px;
                color: #9ca3af;
                margin-top: 4px;
            }
            .predict-box .confidence {
                margin-top: 8px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .predict-box .confidence .bar {
                flex: 1;
                height: 6px;
                background: #1f2937;
                border-radius: 4px;
                overflow: hidden;
            }
            .predict-box .confidence .bar .fill {
                height: 100%;
                border-radius: 4px;
                background: linear-gradient(90deg, #ff6b6b, #ffd700, #4ecdc4);
                transition: width 0.5s ease;
            }
            .predict-box .confidence .text {
                font-size: 13px;
                font-weight: 600;
                min-width: 40px;
                text-align: right;
            }
            .endpoints {
                margin-top: 16px;
            }
            .endpoints .item {
                background: #0f1a2e;
                padding: 10px 14px;
                border-radius: 8px;
                margin-bottom: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 8px;
                border: 1px solid #1f2937;
            }
            .endpoints .item code {
                font-size: 12px;
                background: #1a2236;
                padding: 4px 10px;
                border-radius: 6px;
                color: #88ccff;
                word-break: break-all;
            }
            .endpoints .item .desc {
                font-size: 13px;
                color: #9ca3af;
            }
            .endpoints .item .method {
                font-size: 11px;
                font-weight: 600;
                color: #66dd88;
                background: #1a2a1a;
                padding: 2px 10px;
                border-radius: 12px;
            }
            .footer {
                text-align: center;
                font-size: 12px;
                color: #4a5a6f;
                padding: 16px 0;
                border-top: 1px solid #1f2937;
                margin-top: 16px;
            }
            .refresh-btn {
                background: #1f2937;
                border: 1px solid #2a3a5e;
                color: #e0e0e0;
                padding: 8px 20px;
                border-radius: 8px;
                font-size: 14px;
                cursor: pointer;
                transition: 0.2s;
                width: 100%;
                margin-top: 8px;
            }
            .refresh-btn:hover {
                background: #2a3a5e;
            }
            .refresh-btn:active {
                transform: scale(0.97);
            }
            .loading {
                color: #6b7a8f;
                font-size: 14px;
                text-align: center;
                padding: 20px;
            }
            .toast {
                position: fixed;
                top: 20px;
                right: 20px;
                background: #1a2a3a;
                border: 1px solid #ffd700;
                border-radius: 12px;
                padding: 12px 20px;
                color: #ffd700;
                font-size: 14px;
                z-index: 999;
                opacity: 0;
                transform: translateY(-20px);
                transition: all 0.5s ease;
                pointer-events: none;
            }
            .toast.show {
                opacity: 1;
                transform: translateY(0);
            }
            @media (max-width: 480px) {
                body { padding: 10px; }
                .header h1 { font-size: 20px; }
                .dice-box { min-width: 50px; padding: 8px 12px; }
                .dice-box .number { font-size: 24px; }
                .predict-box .main { font-size: 18px; }
                .result-row .value { font-size: 14px; }
                .endpoints .item { flex-direction: column; align-items: stretch; }
                .endpoints .item code { font-size: 11px; }
                .toast { top: 10px; right: 10px; left: 10px; font-size: 12px; }
            }
        </style>
    </head>
    <body>
        <div class="toast" id="toast">🔄 Phiên mới đã cập nhật!</div>
        
        <div class="container" id="app">
            <div class="header">
                <h1>🎲 HIT Tài Xỉu</h1>
                <div class="admin">👤 Admin: Duy Bảo</div>
                <div class="status" id="status">🟢 Đang kết nối...</div>
                <div class="auto-update">⚡ Tự động cập nhật khi có phiên mới</div>
            </div>

            <!-- BÀN THƯỜNG -->
            <div class="card" id="card_100">
                <h2>
                    🎯 Bàn Thường 
                    <span class="badge" id="phien_100">#---</span>
                    <span class="update-indicator" id="indicator_100">🆕 Có phiên mới!</span>
                </h2>
                <div class="dice" id="dice_100">
                    <div class="dice-box" id="box1_100"><div class="number" id="d1_100">-</div><div class="label">Xúc xắc 1</div></div>
                    <div class="dice-box" id="box2_100"><div class="number" id="d2_100">-</div><div class="label">Xúc xắc 2</div></div>
                    <div class="dice-box" id="box3_100"><div class="number" id="d3_100">-</div><div class="label">Xúc xắc 3</div></div>
                </div>
                <div class="result-row">
                    <span class="label">📊 Tổng điểm</span>
                    <span class="value gold" id="tong_100">0</span>
                </div>
                <div class="result-row">
                    <span class="label">✅ Kết quả</span>
                    <span class="value" id="ketqua_100">Chưa có</span>
                </div>
                <div class="predict-box" id="predict_100">
                    <div class="title">🔮 Dự đoán phiên tiếp theo</div>
                    <div class="main" id="dudoan_100">Chưa đủ dữ liệu</div>
                    <div class="sub" id="lydo_100"></div>
                    <div class="confidence">
                        <span style="font-size:13px;color:#9ca3af;">Độ tin cậy</span>
                        <div class="bar"><div class="fill" id="do_tin_cay_100" style="width:0%"></div></div>
                        <span class="text" id="do_tin_cay_text_100">0%</span>
                    </div>
                </div>
                <button class="refresh-btn" onclick="fetchData()">🔄 Cập nhật</button>
            </div>

            <!-- BÀN MD5 -->
            <div class="card" id="card_101">
                <h2>
                    🔐 Bàn MD5 
                    <span class="badge" id="phien_101">#---</span>
                    <span class="update-indicator" id="indicator_101">🆕 Có phiên mới!</span>
                </h2>
                <div class="dice" id="dice_101">
                    <div class="dice-box" id="box1_101"><div class="number" id="d1_101">-</div><div class="label">Xúc xắc 1</div></div>
                    <div class="dice-box" id="box2_101"><div class="number" id="d2_101">-</div><div class="label">Xúc xắc 2</div></div>
                    <div class="dice-box" id="box3_101"><div class="number" id="d3_101">-</div><div class="label">Xúc xắc 3</div></div>
                </div>
                <div class="result-row">
                    <span class="label">📊 Tổng điểm</span>
                    <span class="value gold" id="tong_101">0</span>
                </div>
                <div class="result-row">
                    <span class="label">✅ Kết quả</span>
                    <span class="value" id="ketqua_101">Chưa có</span>
                </div>
                <div class="predict-box" id="predict_101">
                    <div class="title">🔮 Dự đoán phiên tiếp theo</div>
                    <div class="main" id="dudoan_101">Chưa đủ dữ liệu</div>
                    <div class="sub" id="lydo_101"></div>
                    <div class="confidence">
                        <span style="font-size:13px;color:#9ca3af;">Độ tin cậy</span>
                        <div class="bar"><div class="fill" id="do_tin_cay_101" style="width:0%"></div></div>
                        <span class="text" id="do_tin_cay_text_101">0%</span>
                    </div>
                </div>
            </div>

            <!-- ENDPOINTS -->
            <div class="card">
                <h2>📡 API Endpoints</h2>
                <div class="endpoints">
                    <div class="item">
                        <span class="method">GET</span>
                        <code>/api/taixiu</code>
                        <span class="desc">Bàn thường</span>
                    </div>
                    <div class="item">
                        <span class="method">GET</span>
                        <code>/api/taixiumd5</code>
                        <span class="desc">Bàn MD5</span>
                    </div>
                    <div class="item">
                        <span class="method">GET</span>
                        <code>/api/history</code>
                        <span class="desc">Lịch sử</span>
                    </div>
                </div>
            </div>

            <div class="footer">
                🚀 HIT API v3.0 | Tự động cập nhật | Duy Bảo Admin
            </div>
        </div>

        <script>
            // ========== BIẾN ==========
            let currentSession100 = 0;
            let currentSession101 = 0;
            let data100 = {};
            let data101 = {};
            let isUpdating = false;

            // ========== FETCH DATA ==========
            async function fetchData() {
                if (isUpdating) return;
                isUpdating = true;

                try {
                    // Fetch bàn thường
                    const res100 = await fetch('/api/taixiu');
                    const newData100 = await res100.json();
                    
                    // Fetch bàn MD5
                    const res101 = await fetch('/api/taixiumd5');
                    const newData101 = await res101.json();

                    // Kiểm tra cập nhật
                    const oldPhien100 = data100.Phien || 0;
                    const oldPhien101 = data101.Phien || 0;
                    
                    const hasUpdate100 = newData100.Phien > oldPhien100 && newData100.Phien > 0;
                    const hasUpdate101 = newData101.Phien > oldPhien101 && newData101.Phien > 0;

                    // Cập nhật dữ liệu
                    data100 = newData100;
                    data101 = newData101;

                    // Cập nhật UI
                    updateUI(data100, '100', hasUpdate100);
                    updateUI(data101, '101', hasUpdate101);

                    // Cập nhật phiên hiện tại
                    if (hasUpdate100) {
                        currentSession100 = data100.Phien;
                        showToast('🔄 Bàn Thường - Phiên ' + data100.Phien);
                    }
                    if (hasUpdate101) {
                        currentSession101 = data101.Phien;
                        showToast('🔄 Bàn MD5 - Phiên ' + data101.Phien);
                    }

                    document.getElementById('status').textContent = '🟢 Đã cập nhật - ' + new Date().toLocaleTimeString();
                    document.getElementById('status').style.color = '#66dd88';

                } catch (e) {
                    document.getElementById('status').textContent = '🔴 Lỗi kết nối';
                    document.getElementById('status').style.color = '#ff6b6b';
                    console.error('Fetch error:', e);
                }
                
                isUpdating = false;
            }

            // ========== UPDATE UI ==========
            function updateUI(data, suffix, hasUpdate) {
                // Card
                const card = document.getElementById('card_' + suffix);
                if (hasUpdate) {
                    card.classList.add('new-update');
                    document.getElementById('indicator_' + suffix).classList.add('show');
                } else {
                    card.classList.remove('new-update');
                    document.getElementById('indicator_' + suffix).classList.remove('show');
                }
                
                // Phiên
                const phien = data.Phien || 0;
                document.getElementById('phien_' + suffix).textContent = '#' + (phien || '---');
                
                // Xúc xắc - có hiệu ứng pop
                const d1 = data.Xuc_xac_1 || '-';
                const d2 = data.Xuc_xac_2 || '-';
                const d3 = data.Xuc_xac_3 || '-';
                
                const d1El = document.getElementById('d1_' + suffix);
                const d2El = document.getElementById('d2_' + suffix);
                const d3El = document.getElementById('d3_' + suffix);
                
                if (hasUpdate && d1 !== '-') {
                    d1El.textContent = d1;
                    d2El.textContent = d2;
                    d3El.textContent = d3;
                    
                    // Hiệu ứng pop
                    const box1 = document.getElementById('box1_' + suffix);
                    const box2 = document.getElementById('box2_' + suffix);
                    const box3 = document.getElementById('box3_' + suffix);
                    
                    box1.classList.remove('pop');
                    box2.classList.remove('pop');
                    box3.classList.remove('pop');
                    d1El.classList.remove('pop-number');
                    d2El.classList.remove('pop-number');
                    d3El.classList.remove('pop-number');
                    
                    void box1.offsetWidth; // Trigger reflow
                    box1.classList.add('pop');
                    box2.classList.add('pop');
                    box3.classList.add('pop');
                    d1El.classList.add('pop-number');
                    d2El.classList.add('pop-number');
                    d3El.classList.add('pop-number');
                } else {
                    d1El.textContent = d1;
                    d2El.textContent = d2;
                    d3El.textContent = d3;
                }
                
                // Tổng
                const tong = data.Tong || 0;
                const tongEl = document.getElementById('tong_' + suffix);
                tongEl.textContent = tong;
                if (hasUpdate) {
                    tongEl.classList.remove('pulse');
                    void tongEl.offsetWidth;
                    tongEl.classList.add('pulse');
                }
                
                // Kết quả
                const ketqua = data.Ket_qua || 'Chưa có';
                const ketquaEl = document.getElementById('ketqua_' + suffix);
                ketquaEl.textContent = ketqua;
                ketquaEl.className = 'value ' + (ketqua === 'Tài' ? 'tai' : ketqua === 'Xỉu' ? 'xiu' : '');
                if (hasUpdate && ketqua !== 'Chưa có') {
                    ketquaEl.classList.remove('pulse');
                    void ketquaEl.offsetWidth;
                    ketquaEl.classList.add('pulse');
                }
                
                // Dự đoán
                const dudoan = data.Du_doan || 'Chưa đủ dữ liệu';
                const dudoanEl = document.getElementById('dudoan_' + suffix);
                dudoanEl.textContent = dudoan;
                dudoanEl.className = 'main ' + (dudoan === 'Tài' ? 'tai' : dudoan === 'Xỉu' ? 'xiu' : '');
                
                const predictBox = document.getElementById('predict_' + suffix);
                if (hasUpdate && dudoan !== 'Chưa đủ dữ liệu') {
                    predictBox.classList.add('new-predict');
                    dudoanEl.classList.remove('pop-predict');
                    void dudoanEl.offsetWidth;
                    dudoanEl.classList.add('pop-predict');
                } else {
                    predictBox.classList.remove('new-predict');
                }
                
                // Lý do
                document.getElementById('lydo_' + suffix).textContent = data.Ly_do || '';
                
                // Độ tin cậy
                const doTinCay = data.Do_tin_cay || 0;
                document.getElementById('do_tin_cay_' + suffix).style.width = doTinCay + '%';
                document.getElementById('do_tin_cay_text_' + suffix).textContent = doTinCay + '%';
            }

            // ========== TOAST ==========
            function showToast(message) {
                const toast = document.getElementById('toast');
                toast.textContent = message;
                toast.classList.add('show');
                clearTimeout(toast.timeout);
                toast.timeout = setTimeout(() => {
                    toast.classList.remove('show');
                }, 3000);
            }

            // ========== CHECK UPDATE TỰ ĐỘNG ==========
            async function checkAutoUpdate() {
                try {
                    // Kiểm tra bàn thường
                    const res100 = await fetch('/api/check_update?gid=100&current=' + currentSession100);
                    const check100 = await res100.json();
                    
                    // Kiểm tra bàn MD5
                    const res101 = await fetch('/api/check_update?gid=101&current=' + currentSession101);
                    const check101 = await res101.json();
                    
                    if (check100.has_update || check101.has_update) {
                        fetchData();
                    }
                } catch (e) {
                    // Silent fail
                }
            }

            // ========== KHỞI TẠO ==========
            fetchData();
            
            // Tự động cập nhật dữ liệu mỗi 5 giây
            setInterval(fetchData, 5000);
            
            // Kiểm tra phiên mới mỗi 2 giây (nhanh hơn)
            setInterval(checkAutoUpdate, 2000);
            
            // Kiểm tra kết nối
            setInterval(() => {
                const status = document.getElementById('status');
                if (!status.textContent.includes('Đã cập nhật')) {
                    status.textContent = '🟡 Đang chờ...';
                    status.style.color = '#ffd700';
                }
            }, 30000);
        </script>
    </body>
    </html>
    """

# ============== MAIN ==============

if __name__ == "__main__":
    logger.info("Khởi động hệ thống API Tài Xỉu với tự động cập nhật...")
    logger.info(f"Đã tải {len(history_100)} bản ghi bàn thường")
    logger.info(f"Đã tải {len(history_101)} bản ghi bàn MD5")
    
    thread_100 = threading.Thread(target=poll_api, args=("vgmn_100", lock_100, latest_result_100, history_100, False), daemon=True)
    thread_101 = threading.Thread(target=poll_api, args=("vgmn_101", lock_101, latest_result_101, history_101, True), daemon=True)
    thread_100.start()
    thread_101.start()
    logger.info("Đã bắt đầu polling dữ liệu.")
    port = int(os.environ.get("PORT", 8000))
    app.run(host=HOST, port=port)
