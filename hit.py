import json
import threading
import time
import os
import logging
from urllib.request import urlopen, Request
from flask import Flask, jsonify, request
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HOST = '0.0.0.0'
POLL_INTERVAL = 5
RETRY_DELAY = 5
MAX_HISTORY = 50

lock_100 = threading.Lock()
lock_101 = threading.Lock()

# ============== DỮ LIỆU BÀN THƯỜNG ==============
latest_result_100 = {
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

# ============== DỮ LIỆU BÀN MD5 ==============
latest_result_101 = {
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

history_100 = []
history_101 = []

last_sid_100 = None
last_sid_101 = None
sid_for_tx = None

# ============== LƯU LỊCH SỬ CHO DỰ ĐOÁN ==============
predict_history_100 = []  # Lịch sử bàn thường
predict_history_101 = []  # Lịch sử bàn MD5
MAX_PREDICT_HISTORY = 100

# ============== THUẬT TOÁN DỰ ĐOÁN NÂNG CAO ==============

def phan_tich_cau(predict_history, window_size=10):
    """
    Phân tích cầu từ lịch sử
    """
    if len(predict_history) < window_size:
        return None
    
    recent = predict_history[:window_size]
    results = [r["ket_qua"] for r in recent if r.get("ket_qua")]
    
    if len(results) < 3:
        return None
    
    # Thống kê tần suất
    tai_count = results.count("Tài")
    xiu_count = results.count("Xỉu")
    total = len(results)
    
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
    
    # Phân tích tổng điểm
    tong_list = [r.get("tong", 0) for r in recent if r.get("tong", 0) > 0]
    tong_trung_binh = sum(tong_list) / len(tong_list) if tong_list else 10.5
    
    return {
        "tai_ratio": tai_count / total,
        "xiu_ratio": xiu_count / total,
        "max_consecutive": max_consecutive,
        "current_result": current,
        "tong_trung_binh": tong_trung_binh,
        "total_analyzed": total
    }

def du_doan_thong_minh(predict_history):
    """
    Dự đoán thông minh với nhiều chiến lược
    """
    if len(predict_history) < 3:
        return {
            "Du_doan": "Chưa đủ dữ liệu",
            "Do_tin_cay": 0,
            "Ly_do": f"Cần ít nhất 3 phiên, hiện có {len(predict_history)} phiên",
            "Chien_luoc": "Chờ dữ liệu"
        }
    
    # Lấy kết quả gần nhất
    recent_results = [r["ket_qua"] for r in predict_history[:10]]
    tai_count = recent_results.count("Tài")
    xiu_count = recent_results.count("Xỉu")
    total = len(recent_results)
    
    # ===== CHIẾN LƯỢC 1: BẮT BỆT =====
    # Kiểm tra 3 phiên gần nhất
    last_3 = [r["ket_qua"] for r in predict_history[:3]]
    last_5 = [r["ket_qua"] for r in predict_history[:5]]
    
    if len(last_3) == 3:
        # 3 Tài liên tiếp -> dự đoán Xỉu
        if last_3 == ["Tài", "Tài", "Tài"]:
            # Kiểm tra thêm nếu đang trong chuỗi dài
            if len(last_5) >= 5 and last_5[:4].count("Tài") == 4:
                return {
                    "Du_doan": "Xỉu",
                    "Do_tin_cay": 78,
                    "Ly_do": "4 phiên Tài liên tiếp, xác suất đảo chiều cao",
                    "Chien_luoc": "Bắt bệt đảo"
                }
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": 72,
                "Ly_do": "3 phiên Tài liên tiếp, khả năng đảo chiều sang Xỉu",
                "Chien_luoc": "Bắt bệt"
            }
        
        # 3 Xỉu liên tiếp -> dự đoán Tài
        if last_3 == ["Xỉu", "Xỉu", "Xỉu"]:
            if len(last_5) >= 5 and last_5[:4].count("Xỉu") == 4:
                return {
                    "Du_doan": "Tài",
                    "Do_tin_cay": 78,
                    "Ly_do": "4 phiên Xỉu liên tiếp, xác suất đảo chiều cao",
                    "Chien_luoc": "Bắt bệt đảo"
                }
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": 72,
                "Ly_do": "3 phiên Xỉu liên tiếp, khả năng đảo chiều sang Tài",
                "Chien_luoc": "Bắt bệt"
            }
    
    # ===== CHIẾN LƯỢC 2: PATTERN XEN KẼ =====
    if len(last_3) == 3:
        # Pattern Tài-Xỉu-Tài
        if last_3[0] == "Tài" and last_3[1] == "Xỉu" and last_3[2] == "Tài":
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": 65,
                "Ly_do": "Pattern Tài-Xỉu-Tài, dự đoán Xỉu tiếp theo",
                "Chien_luoc": "Pattern xen kẽ"
            }
        # Pattern Xỉu-Tài-Xỉu
        if last_3[0] == "Xỉu" and last_3[1] == "Tài" and last_3[2] == "Xỉu":
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": 65,
                "Ly_do": "Pattern Xỉu-Tài-Xỉu, dự đoán Tài tiếp theo",
                "Chien_luoc": "Pattern xen kẽ"
            }
    
    # ===== CHIẾN LƯỢC 3: THEO XU HƯỚNG =====
    # Phân tích 5 phiên gần nhất
    if len(last_5) >= 5:
        tai_in_5 = last_5.count("Tài")
        xiu_in_5 = last_5.count("Xỉu")
        
        # Nếu Tài chiếm ưu thế (4/5)
        if tai_in_5 >= 4:
            # Nhưng phiên cuối là Xỉu thì có thể đang đảo
            if last_5[0] == "Xỉu":
                return {
                    "Du_doan": "Xỉu",
                    "Do_tin_cay": 60,
                    "Ly_do": "Xu hướng Tài nhưng đang đảo sang Xỉu",
                    "Chien_luoc": "Theo xu hướng đảo"
                }
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": 62,
                "Ly_do": f"Tài chiếm {tai_in_5}/5 phiên gần nhất",
                "Chien_luoc": "Theo xu hướng Tài"
            }
        
        if xiu_in_5 >= 4:
            if last_5[0] == "Tài":
                return {
                    "Du_doan": "Tài",
                    "Do_tin_cay": 60,
                    "Ly_do": "Xu hướng Xỉu nhưng đang đảo sang Tài",
                    "Chien_luoc": "Theo xu hướng đảo"
                }
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": 62,
                "Ly_do": f"Xỉu chiếm {xiu_in_5}/5 phiên gần nhất",
                "Chien_luoc": "Theo xu hướng Xỉu"
            }
    
    # ===== CHIẾN LƯỢC 4: TỔNG ĐIỂM =====
    tong_list = [r.get("tong", 0) for r in predict_history[:5] if r.get("tong", 0) > 0]
    if tong_list:
        tong_trung_binh = sum(tong_list) / len(tong_list)
        
        # Tổng trung bình > 12 -> nghiêng Tài
        if tong_trung_binh > 12:
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": 55,
                "Ly_do": f"Tổng TB {round(tong_trung_binh, 1)} > 12, nghiêng về Tài",
                "Chien_luoc": "Phân tích tổng"
            }
        
        # Tổng trung bình < 9 -> nghiêng Xỉu
        if tong_trung_binh < 9:
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": 55,
                "Ly_do": f"Tổng TB {round(tong_trung_binh, 1)} < 9, nghiêng về Xỉu",
                "Chien_luoc": "Phân tích tổng"
            }
    
    # ===== CHIẾN LƯỢC 5: TỶ LỆ TỔNG THỂ =====
    if total >= 5:
        tai_ratio = tai_count / total * 100
        xiu_ratio = xiu_count / total * 100
        
        # Nếu 1 bên chiếm > 60%
        if tai_ratio >= 60:
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": round(tai_ratio, 1),
                "Ly_do": f"Tài chiếm {round(tai_ratio, 1)}% trong {total} phiên gần nhất",
                "Chien_luoc": "Tỷ lệ tổng thể"
            }
        
        if xiu_ratio >= 60:
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": round(xiu_ratio, 1),
                "Ly_do": f"Xỉu chiếm {round(xiu_ratio, 1)}% trong {total} phiên gần nhất",
                "Chien_luoc": "Tỷ lệ tổng thể"
            }
    
    # ===== CHIẾN LƯỢC 6: MẶC ĐỊNH =====
    # Dự đoán theo xu hướng gần nhất
    if total > 0:
        last_result = predict_history[0].get("ket_qua")
        if last_result in ["Tài", "Xỉu"]:
            # Nếu 2 phiên gần nhất khác nhau -> dự đoán theo phiên cuối
            if len(predict_history) >= 2:
                prev_result = predict_history[1].get("ket_qua")
                if prev_result != last_result:
                    return {
                        "Du_doan": last_result,
                        "Do_tin_cay": 55,
                        "Ly_do": f"Xu hướng đang là {last_result} (phiên gần nhất)",
                        "Chien_luoc": "Theo xu hướng cuối"
                    }
    
    # Nếu tất cả đều cân bằng
    return {
        "Du_doan": random.choice(["Tài", "Xỉu"]),
        "Do_tin_cay": 50,
        "Ly_do": "Dữ liệu cân bằng, dự đoán ngẫu nhiên",
        "Chien_luoc": "Ngẫu nhiên"
    }

# ============== HÀM CHÍNH ==============

def get_tai_xiu(d1, d2, d3):
    total = d1 + d2 + d3
    return "Xỉu" if total <= 10 else "Tài"

def update_result(store, history, lock, result, predict_history, is_md5):
    with lock:
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
        du_doan_result = du_doan_thong_minh(predict_history)
        store["Du_doan"] = du_doan_result.get("Du_doan", "Chưa đủ dữ liệu")
        store["Do_tin_cay"] = du_doan_result.get("Do_tin_cay", 0)
        store["Ly_do"] = du_doan_result.get("Ly_do", "")
        store["Chien_luoc"] = du_doan_result.get("Chien_luoc", "")

# ============== POLL API ==============

def poll_api(gid, lock, result_store, history, is_md5):
    global last_sid_100, last_sid_101, sid_for_tx
    url = f"https://jakpotgwab.geightdors.net/glms/v1/notify/taixiu?platform_id=g8&gid={gid}"
    
    # Chọn lịch sử dự đoán tương ứng
    predict_history = predict_history_101 if is_md5 else predict_history_100
    
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
                            update_result(result_store, history, lock, result, predict_history_101, True)
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
                            update_result(result_store, history, lock, result, predict_history_100, False)
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
        response = jsonify(latest_result_100)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

@app.route("/api/taixiumd5", methods=["GET"])
def get_taixiu_101():
    with lock_101:
        response = jsonify(latest_result_101)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

@app.route("/api/history", methods=["GET"])
def get_history():
    limit = request.args.get('limit', 50, type=int)
    with lock_100, lock_101:
        response = jsonify({
            "taixiu": history_100[:limit],
            "taixiumd5": history_101[:limit],
            "admin": "Duy Bảo"
        })
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

# ============== TRANG CHỦ ==============

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
            .card {
                background: #111827;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 16px;
                border: 1px solid #1f2937;
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
            }
            .dice-box .number {
                font-size: 32px;
                font-weight: 700;
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
            }
            .predict-box .title {
                font-size: 13px;
                color: #9ca3af;
                margin-bottom: 6px;
            }
            .predict-box .main {
                font-size: 22px;
                font-weight: 700;
            }
            .predict-box .main.tai {
                color: #ff6b6b;
            }
            .predict-box .main.xiu {
                color: #4ecdc4;
            }
            .predict-box .sub {
                font-size: 13px;
                color: #9ca3af;
                margin-top: 4px;
            }
            .predict-box .strategy {
                font-size: 12px;
                color: #88ccff;
                margin-top: 4px;
                background: #1a2236;
                padding: 4px 10px;
                border-radius: 6px;
                display: inline-block;
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
                transition: width 0.5s;
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
            .strategy-badge {
                font-size: 11px;
                background: #1a2a3a;
                padding: 2px 12px;
                border-radius: 12px;
                color: #88ccff;
                border: 1px solid #2a3a5e;
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
            }
        </style>
    </head>
    <body>
        <div class="container" id="app">
            <div class="header">
                <h1>🎲 HIT Tài Xỉu</h1>
                <div class="admin">👤 Admin: Duy Bảo</div>
                <div class="status" id="status">🟢 Đang kết nối...</div>
            </div>

            <!-- BÀN THƯỜNG -->
            <div class="card">
                <h2>🎯 Bàn Thường <span class="badge" id="phien_100">#---</span></h2>
                <div class="dice" id="dice_100">
                    <div class="dice-box"><div class="number" id="d1_100">-</div><div class="label">Xúc xắc 1</div></div>
                    <div class="dice-box"><div class="number" id="d2_100">-</div><div class="label">Xúc xắc 2</div></div>
                    <div class="dice-box"><div class="number" id="d3_100">-</div><div class="label">Xúc xắc 3</div></div>
                </div>
                <div class="result-row">
                    <span class="label">📊 Tổng điểm</span>
                    <span class="value gold" id="tong_100">0</span>
                </div>
                <div class="result-row">
                    <span class="label">✅ Kết quả</span>
                    <span class="value" id="ketqua_100">Chưa có</span>
                </div>
                <div class="predict-box">
                    <div class="title">🔮 Dự đoán phiên tiếp theo</div>
                    <div class="main" id="dudoan_100">Chưa đủ dữ liệu</div>
                    <div class="sub" id="lydo_100"></div>
                    <div style="margin-top: 4px;">
                        <span class="strategy-badge" id="chienluoc_100">Chờ dữ liệu</span>
                    </div>
                    <div class="confidence">
                        <span style="font-size:13px;color:#9ca3af;">Độ tin cậy</span>
                        <div class="bar"><div class="fill" id="do_tin_cay_100" style="width:0%"></div></div>
                        <span class="text" id="do_tin_cay_text_100">0%</span>
                    </div>
                </div>
                <button class="refresh-btn" onclick="fetchData()">🔄 Cập nhật</button>
            </div>

            <!-- BÀN MD5 -->
            <div class="card">
                <h2>🔐 Bàn MD5 <span class="badge" id="phien_101">#---</span></h2>
                <div class="dice" id="dice_101">
                    <div class="dice-box"><div class="number" id="d1_101">-</div><div class="label">Xúc xắc 1</div></div>
                    <div class="dice-box"><div class="number" id="d2_101">-</div><div class="label">Xúc xắc 2</div></div>
                    <div class="dice-box"><div class="number" id="d3_101">-</div><div class="label">Xúc xắc 3</div></div>
                </div>
                <div class="result-row">
                    <span class="label">📊 Tổng điểm</span>
                    <span class="value gold" id="tong_101">0</span>
                </div>
                <div class="result-row">
                    <span class="label">✅ Kết quả</span>
                    <span class="value" id="ketqua_101">Chưa có</span>
                </div>
                <div class="predict-box">
                    <div class="title">🔮 Dự đoán phiên tiếp theo</div>
                    <div class="main" id="dudoan_101">Chưa đủ dữ liệu</div>
                    <div class="sub" id="lydo_101"></div>
                    <div style="margin-top: 4px;">
                        <span class="strategy-badge" id="chienluoc_101">Chờ dữ liệu</span>
                    </div>
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
                🚀 HIT API v2.0 | Duy Bảo Admin
            </div>
        </div>

        <script>
            // ========== FETCH DATA ==========
            async function fetchData() {
                try {
                    // Fetch bàn thường
                    const res100 = await fetch('/api/taixiu');
                    const data100 = await res100.json();
                    updateUI(data100, '100');

                    // Fetch bàn MD5
                    const res101 = await fetch('/api/taixiumd5');
                    const data101 = await res101.json();
                    updateUI(data101, '101');

                    document.getElementById('status').textContent = '🟢 Đã cập nhật';
                    document.getElementById('status').style.color = '#66dd88';
                } catch (e) {
                    document.getElementById('status').textContent = '🔴 Lỗi kết nối';
                    document.getElementById('status').style.color = '#ff6b6b';
                    console.error('Fetch error:', e);
                }
            }

            // ========== UPDATE UI ==========
            function updateUI(data, suffix) {
                // Phiên
                document.getElementById('phien_' + suffix).textContent = '#' + (data.Phien || '---');
                
                // Xúc xắc
                document.getElementById('d1_' + suffix).textContent = data.Xuc_xac_1 || '-';
                document.getElementById('d2_' + suffix).textContent = data.Xuc_xac_2 || '-';
                document.getElementById('d3_' + suffix).textContent = data.Xuc_xac_3 || '-';
                
                // Tổng
                document.getElementById('tong_' + suffix).textContent = data.Tong || 0;
                
                // Kết quả
                const ketqua = data.Ket_qua || 'Chưa có';
                const ketquaEl = document.getElementById('ketqua_' + suffix);
                ketquaEl.textContent = ketqua;
                ketquaEl.className = 'value ' + (ketqua === 'Tài' ? 'tai' : ketqua === 'Xỉu' ? 'xiu' : '');
                
                // Dự đoán
                const dudoan = data.Du_doan || 'Chưa đủ dữ liệu';
                const dudoanEl = document.getElementById('dudoan_' + suffix);
                dudoanEl.textContent = dudoan;
                dudoanEl.className = 'main ' + (dudoan === 'Tài' ? 'tai' : dudoan === 'Xỉu' ? 'xiu' : '');
                
                // Lý do
                document.getElementById('lydo_' + suffix).textContent = data.Ly_do || '';
                
                // Chiến lược
                document.getElementById('chienluoc_' + suffix).textContent = data.Chien_luoc || 'Đang phân tích';
                
                // Độ tin cậy
                const doTinCay = data.Do_tin_cay || 0;
                document.getElementById('do_tin_cay_' + suffix).style.width = doTinCay + '%';
                document.getElementById('do_tin_cay_text_' + suffix).textContent = doTinCay + '%';
            }

            // ========== AUTO REFRESH ==========
            fetchData();
            setInterval(fetchData, 10000);
        </script>
    </body>
    </html>
    """

# ============== MAIN ==============

if __name__ == "__main__":
    # Thêm import random cho dự đoán ngẫu nhiên
    import random
    logger.info("Khởi động hệ thống API Tài Xỉu với AI dự đoán thông minh...")
    thread_100 = threading.Thread(target=poll_api, args=("vgmn_100", lock_100, latest_result_100, history_100, False), daemon=True)
    thread_101 = threading.Thread(target=poll_api, args=("vgmn_101", lock_101, latest_result_101, history_101, True), daemon=True)
    thread_100.start()
    thread_101.start()
    logger.info("Đã bắt đầu polling dữ liệu.")
    port = int(os.environ.get("PORT", 8000))
    app.run(host=HOST, port=port)
