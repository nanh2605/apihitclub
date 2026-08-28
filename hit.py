import json
import threading
import time
import os
import logging
from urllib.request import urlopen, Request
from flask import Flask, jsonify
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HOST = '0.0.0.0'
POLL_INTERVAL = 5
RETRY_DELAY = 5
MAX_HISTORY = 50

lock_100 = threading.Lock()
lock_101 = threading.Lock()

# ============== SỬA: djtuancon → Duy Bảo, id → admin ==============
latest_result_100 = {
    "Phien": 0, 
    "Xuc_xac_1": 0, 
    "Xuc_xac_2": 0, 
    "Xuc_xac_3": 0,
    "Tong": 0, 
    "Ket_qua": "Chưa có", 
    "admin": "Duy Bảo"
}

latest_result_101 = {
    "Phien": 0, 
    "Xuc_xac_1": 0, 
    "Xuc_xac_2": 0, 
    "Xuc_xac_3": 0,
    "Tong": 0, 
    "Ket_qua": "Chưa có", 
    "admin": "Duy Bảo"
}

history_100 = []
history_101 = []

last_sid_100 = None
last_sid_101 = None
sid_for_tx = None

# ============== LƯU LỊCH SỬ CHO DỰ ĐOÁN ==============
predict_history = []
MAX_PREDICT_HISTORY = 100

# ============== HÀM CHÍNH ==============

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

# ============== HÀM DỰ ĐOÁN ==============

def du_doan():
    """Dự đoán kết quả tiếp theo với độ tin cậy"""
    
    if len(predict_history) < 3:
        return {
            "du_doan": "Chưa đủ dữ liệu",
            "do_tin_cay": 0,
            "ly_do": f"Cần ít nhất 3 phiên, hiện có {len(predict_history)} phiên"
        }
    
    # Lấy kết quả gần nhất
    recent = [r["ket_qua"] for r in predict_history[:10]]
    tai_count = recent.count("Tài")
    xiu_count = recent.count("Xỉu")
    total = len(recent)
    
    # ========== LOGIC DỰ ĐOÁN ==========
    
    # 1. Kiểm tra chuỗi 3 phiên liên tiếp
    last_3 = predict_history[:3]
    last_3_result = [r["ket_qua"] for r in last_3]
    
    # Nếu 3 phiên liên tiếp giống nhau → khả năng đảo chiều
    if last_3_result == ["Tài", "Tài", "Tài"]:
        return {
            "du_doan": "Xỉu",
            "do_tin_cay": 72,
            "ly_do": "3 phiên Tài liên tiếp, khả năng đảo chiều sang Xỉu"
        }
    
    if last_3_result == ["Xỉu", "Xỉu", "Xỉu"]:
        return {
            "du_doan": "Tài",
            "do_tin_cay": 72,
            "ly_do": "3 phiên Xỉu liên tiếp, khả năng đảo chiều sang Tài"
        }
    
    # 2. Kiểm tra pattern xen kẽ
    if len(last_3_result) >= 3:
        if last_3_result[0] == "Tài" and last_3_result[1] == "Xỉu" and last_3_result[2] == "Tài":
            return {
                "du_doan": "Xỉu",
                "do_tin_cay": 65,
                "ly_do": "Pattern Tài-Xỉu-Tài, dự đoán Xỉu tiếp theo"
            }
        if last_3_result[0] == "Xỉu" and last_3_result[1] == "Tài" and last_3_result[2] == "Xỉu":
            return {
                "du_doan": "Tài",
                "do_tin_cay": 65,
                "ly_do": "Pattern Xỉu-Tài-Xỉu, dự đoán Tài tiếp theo"
            }
    
    # 3. Dựa vào tỷ lệ
    tai_ratio = tai_count / total * 100
    xiu_ratio = xiu_count / total * 100
    
    if tai_ratio >= 65:
        return {
            "du_doan": "Tài",
            "do_tin_cay": round(tai_ratio, 1),
            "ly_do": f"Tài chiếm {round(tai_ratio, 1)}% trong {total} phiên gần nhất"
        }
    
    if xiu_ratio >= 65:
        return {
            "du_doan": "Xỉu",
            "do_tin_cay": round(xiu_ratio, 1),
            "ly_do": f"Xỉu chiếm {round(xiu_ratio, 1)}% trong {total} phiên gần nhất"
        }
    
    # 4. Nếu tỷ lệ cân bằng, dựa vào tổng điểm
    tong_trung_binh = sum([r.get("tong", 0) for r in predict_history[:5]]) / 5
    
    if tong_trung_binh > 11:
        return {
            "du_doan": "Tài",
            "do_tin_cay": 55,
            "ly_do": f"Tổng trung bình {round(tong_trung_binh, 1)} > 11, nghiêng về Tài"
        }
    
    if tong_trung_binh < 10:
        return {
            "du_doan": "Xỉu",
            "do_tin_cay": 55,
            "ly_do": f"Tổng trung bình {round(tong_trung_binh, 1)} < 10, nghiêng về Xỉu"
        }
    
    # 5. Mặc định - dựa vào xu hướng gần nhất
    if tai_count > xiu_count:
        return {
            "du_doan": "Tài",
            "do_tin_cay": 52,
            "ly_do": f"Tài có xu hướng nhỉnh hơn ({tai_count}/{total} phiên)"
        }
    else:
        return {
            "du_doan": "Xỉu",
            "do_tin_cay": 52,
            "ly_do": f"Xỉu có xu hướng nhỉnh hơn ({xiu_count}/{total} phiên)"
        }

# ============== POLL API ==============

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
                            result = {
                                "Phien": sid,
                                "Xuc_xac_1": d1,
                                "Xuc_xac_2": d2,
                                "Xuc_xac_3": d3,
                                "Tong": total,
                                "Ket_qua": ket_qua,
                                "admin": "Duy Bảo"  # SỬA
                            }
                            update_result(result_store, history, lock, result)
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
                                "admin": "Duy Bảo"  # SỬA
                            }
                            update_result(result_store, history, lock, result)
                            logger.info(f"[TX] Phiên {sid} - Tổng: {total}, Kết quả: {ket_qua}")
                            sid_for_tx = None
        except Exception as e:
            logger.error(f"Lỗi khi lấy dữ liệu API {gid}: {e}")
            time.sleep(RETRY_DELAY)
        time.sleep(POLL_INTERVAL)

# ============== FLASK APP ==============

app = Flask(__name__)

# ============== API CŨ (GIỮ NGUYÊN) ==============

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

# ============== API DỰ ĐOÁN MỚI ==============

@app.route("/api/predict", methods=["GET"])
def predict():
    """API dự đoán kết quả tiếp theo"""
    
    # Lấy kết quả hiện tại
    with lock_100:
        current = latest_result_100.copy()
    
    # Dự đoán
    result = du_doan()
    
    return jsonify({
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "current": {
            "phien": current.get("Phien"),
            "ket_qua": current.get("Ket_qua"),
            "tong": current.get("Tong")
        },
        "predict": {
            "du_doan": result.get("du_doan"),
            "do_tin_cay": result.get("do_tin_cay"),
            "ly_do": result.get("ly_do")
        },
        "admin": "Duy Bảo"
    })

# ============== TRANG CHỦ ==============

@app.route("/")
def index():
    return """
    <h1>🎲 HIT API - Tài Xỉu</h1>
    <p>Admin: Duy Bảo</p>
    <h3>Endpoints:</h3>
    <ul>
        <li><code>GET /api/taixiu</code> - Kết quả bàn thường</li>
        <li><code>GET /api/taixiumd5</code> - Kết quả bàn MD5</li>
        <li><code>GET /api/history</code> - Lịch sử</li>
        <li><code>GET /api/predict</code> - Dự đoán kết quả tiếp theo</li>
    </ul>
    """

# ============== MAIN ==============

if __name__ == "__main__":
    logger.info("Khởi động hệ thống API Tài Xỉu...")
    thread_100 = threading.Thread(target=poll_api, args=("vgmn_100", lock_100, latest_result_100, history_100, False), daemon=True)
    thread_101 = threading.Thread(target=poll_api, args=("vgmn_101", lock_101, latest_result_101, history_101, True), daemon=True)
    thread_100.start()
    thread_101.start()
    logger.info("Đã bắt đầu polling dữ liệu.")
    port = int(os.environ.get("PORT", 8000))
    app.run(host=HOST, port=port)
