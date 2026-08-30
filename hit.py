import json
import threading
import time
import os
import logging
from urllib.request import urlopen, Request
from flask import Flask, jsonify, request
from datetime import datetime
import random
from collections import Counter

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
HISTORY_FILE_100 = 'history_100.json'
HISTORY_FILE_101 = 'history_101.json'
PREDICT_FILE_100 = 'predict_history_100.json'
PREDICT_FILE_101 = 'predict_history_101.json'

def save_data(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Lỗi lưu file {file_path}: {e}")
        return False

def load_data(file_path, default_data):
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
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Lỗi đọc history {file_path}: {e}")
    return []

def save_history(file_path, history):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Lỗi lưu history {file_path}: {e}")
        return False

# ============== LẤY LỊCH SỬ TỪ API HISTORY ==============

def fetch_history_from_api(gid, is_md5):
    """Lấy lịch sử từ API /api/history"""
    history_data = []
    predict_data = []
    
    try:
        # Gọi API history để lấy lịch sử
        url = f"https://jakpotgwab.geightdors.net/glms/v1/notify/taixiu?platform_id=g8&gid={gid}"
        req = Request(url, headers={'User-Agent': 'Python-Proxy/1.0'})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        if data.get('status') == 'OK' and isinstance(data.get('data'), list):
            for game in data['data']:
                cmd = game.get("cmd")
                
                # Lấy kết quả
                if is_md5 and cmd == 2006:
                    sid = game.get("sid")
                    d1, d2, d3 = game.get("d1"), game.get("d2"), game.get("d3")
                    if sid and None not in (d1, d2, d3):
                        total = d1 + d2 + d3
                        ket_qua = "Xỉu" if total <= 10 else "Tài"
                        
                        history_data.append({
                            "Phien": sid,
                            "Xuc_xac_1": d1,
                            "Xuc_xac_2": d2,
                            "Xuc_xac_3": d3,
                            "Tong": total,
                            "Ket_qua": ket_qua,
                            "admin": "Duy Bảo"
                        })
                        
                        predict_data.append({
                            "phien": sid,
                            "ket_qua": ket_qua,
                            "tong": total,
                            "xuc_xac": [d1, d2, d3]
                        })
                
                elif not is_md5 and cmd == 1003:
                    sid = game.get("sid")
                    d1, d2, d3 = game.get("d1"), game.get("d2"), game.get("d3")
                    if sid and None not in (d1, d2, d3):
                        total = d1 + d2 + d3
                        ket_qua = "Xỉu" if total <= 10 else "Tài"
                        
                        history_data.append({
                            "Phien": sid,
                            "Xuc_xac_1": d1,
                            "Xuc_xac_2": d2,
                            "Xuc_xac_3": d3,
                            "Tong": total,
                            "Ket_qua": ket_qua,
                            "admin": "Duy Bảo"
                        })
                        
                        predict_data.append({
                            "phien": sid,
                            "ket_qua": ket_qua,
                            "tong": total,
                            "xuc_xac": [d1, d2, d3]
                        })
        
        # Sắp xếp theo phiên giảm dần (mới nhất đầu)
        history_data.sort(key=lambda x: x.get("Phien", 0), reverse=True)
        predict_data.sort(key=lambda x: x.get("phien", 0), reverse=True)
        
        logger.info(f"✅ Đã lấy {len(history_data)} bản ghi từ API history cho {gid}")
        return history_data, predict_data
        
    except Exception as e:
        logger.error(f"Lỗi lấy lịch sử từ API {gid}: {e}")
    
    return [], []

def load_full_history():
    """Load toàn bộ lịch sử và cập nhật dự đoán ngay lập tức"""
    global history_100, history_101, predict_history_100, predict_history_101
    global latest_result_100, latest_result_101
    
    logger.info("=" * 50)
    logger.info("🔄 ĐANG LẤY LỊCH SỬ TỪ API HISTORY...")
    
    # Lấy lịch sử bàn thường
    hist_100, pred_100 = fetch_history_from_api("vgmn_100", False)
    if hist_100:
        history_100 = hist_100
        predict_history_100 = pred_100
        save_history(HISTORY_FILE_100, history_100)
        save_history(PREDICT_FILE_100, predict_history_100)
        
        if history_100:
            latest_result_100.update(history_100[0])
            save_data(DATA_FILE_100, latest_result_100)
        
        logger.info(f"✅ Bàn thường: Đã lấy {len(history_100)} phiên")
    else:
        logger.warning("⚠️ Không lấy được lịch sử bàn thường, dùng dữ liệu cũ")
    
    # Lấy lịch sử bàn MD5
    hist_101, pred_101 = fetch_history_from_api("vgmn_101", True)
    if hist_101:
        history_101 = hist_101
        predict_history_101 = pred_101
        save_history(HISTORY_FILE_101, history_101)
        save_history(PREDICT_FILE_101, predict_history_101)
        
        if history_101:
            latest_result_101.update(history_101[0])
            save_data(DATA_FILE_101, latest_result_101)
        
        logger.info(f"✅ Bàn MD5: Đã lấy {len(history_101)} phiên")
    else:
        logger.warning("⚠️ Không lấy được lịch sử bàn MD5, dùng dữ liệu cũ")
    
    # Cập nhật dự đoán ngay lập tức
    update_predictions()
    
    logger.info("✅ HOÀN TẤT LẤY LỊCH SỬ!")
    logger.info("=" * 50)

def update_predictions():
    """Cập nhật dự đoán từ lịch sử đã có"""
    
    with lock_100:
        if predict_history_100:
            du_doan = du_doan_ai_thong_minh(predict_history_100)
            latest_result_100["Du_doan"] = du_doan.get("Du_doan", "Chưa đủ dữ liệu")
            latest_result_100["Do_tin_cay"] = du_doan.get("Do_tin_cay", 0)
            latest_result_100["Ly_do"] = du_doan.get("Ly_do", "")
            latest_result_100["Chien_luoc"] = du_doan.get("Chien_luoc", "")
            latest_result_100["So_phien_phan_tich"] = len(predict_history_100)
            save_data(DATA_FILE_100, latest_result_100)
            logger.info(f"📊 Dự đoán bàn thường: {latest_result_100['Du_doan']} (độ tin cậy {latest_result_100['Do_tin_cay']}%) - {latest_result_100['Chien_luoc']}")
        else:
            latest_result_100["Du_doan"] = "Chưa có dữ liệu lịch sử"
            latest_result_100["Do_tin_cay"] = 0
            latest_result_100["Ly_do"] = "Hãy đợi phiên mới hoặc tải lại lịch sử"
            latest_result_100["Chien_luoc"] = "Không có dữ liệu"
            latest_result_100["So_phien_phan_tich"] = 0
            save_data(DATA_FILE_100, latest_result_100)
    
    with lock_101:
        if predict_history_101:
            du_doan = du_doan_ai_thong_minh(predict_history_101)
            latest_result_101["Du_doan"] = du_doan.get("Du_doan", "Chưa đủ dữ liệu")
            latest_result_101["Do_tin_cay"] = du_doan.get("Do_tin_cay", 0)
            latest_result_101["Ly_do"] = du_doan.get("Ly_do", "")
            latest_result_101["Chien_luoc"] = du_doan.get("Chien_luoc", "")
            latest_result_101["So_phien_phan_tich"] = len(predict_history_101)
            save_data(DATA_FILE_101, latest_result_101)
            logger.info(f"📊 Dự đoán bàn MD5: {latest_result_101['Du_doan']} (độ tin cậy {latest_result_101['Do_tin_cay']}%) - {latest_result_101['Chien_luoc']}")
        else:
            latest_result_101["Du_doan"] = "Chưa có dữ liệu lịch sử"
            latest_result_101["Do_tin_cay"] = 0
            latest_result_101["Ly_do"] = "Hãy đợi phiên mới hoặc tải lại lịch sử"
            latest_result_101["Chien_luoc"] = "Không có dữ liệu"
            latest_result_101["So_phien_phan_tich"] = 0
            save_data(DATA_FILE_101, latest_result_101)

# ============== THUẬT TOÁN DỰ ĐOÁN AI THÔNG MINH ==============

def du_doan_ai_thong_minh(predict_history):
    """
    Dự đoán kết quả tiếp theo với AI thông minh
    """
    
    if len(predict_history) < 3:
        return {
            "Du_doan": "Chưa đủ dữ liệu",
            "Do_tin_cay": 0,
            "Ly_do": f"Cần ít nhất 3 phiên, hiện có {len(predict_history)} phiên",
            "Chien_luoc": "Chờ dữ liệu"
        }
    
    # Lấy kết quả và tổng điểm
    results = [r["ket_qua"] for r in predict_history[:20]]
    tong_list = [r.get("tong", 0) for r in predict_history[:20] if r.get("tong", 0) > 0]
    
    tai_count = results.count("Tài")
    xiu_count = results.count("Xỉu")
    total = len(results)
    
    # ===== PHÂN TÍCH CHUỖI (CHAIN ANALYSIS) =====
    chains = []
    current_chain = 1
    for i in range(1, len(results)):
        if results[i] == results[i-1]:
            current_chain += 1
        else:
            chains.append((results[i-1], current_chain))
            current_chain = 1
    chains.append((results[-1], current_chain))
    
    # Tìm chuỗi dài nhất
    max_chain = max([c[1] for c in chains]) if chains else 0
    current_result = results[0] if results else ""
    
    # ===== PHÂN TÍCH TẦN SUẤT (FREQUENCY ANALYSIS) =====
    tai_ratio = tai_count / total * 100
    xiu_ratio = xiu_count / total * 100
    
    # ===== PHÂN TÍCH TỔNG ĐIỂM =====
    if tong_list:
        tong_trung_binh = sum(tong_list) / len(tong_list)
        tong_max = max(tong_list)
        tong_min = min(tong_list)
    else:
        tong_trung_binh = 10.5
        tong_max = 0
        tong_min = 0
    
    # ===== CHIẾN LƯỢC DỰ ĐOÁN =====
    
    # 1. BẮT BỆT - Khi có chuỗi dài
    if max_chain >= 4:
        if current_result == "Tài":
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": min(85, 60 + max_chain * 5),
                "Ly_do": f"Chuỗi {max_chain} phiên Tài liên tiếp, xác suất đảo chiều cao",
                "Chien_luoc": "Bắt bệt đảo"
            }
        elif current_result == "Xỉu":
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": min(85, 60 + max_chain * 5),
                "Ly_do": f"Chuỗi {max_chain} phiên Xỉu liên tiếp, xác suất đảo chiều cao",
                "Chien_luoc": "Bắt bệt đảo"
            }
    
    # 2. PATTERN XEN KẼ (Alternating Pattern)
    if len(results) >= 5:
        last_5 = results[:5]
        # Kiểm tra pattern T-X-T-X-T
        if last_5[0] == "Tài" and last_5[1] == "Xỉu" and last_5[2] == "Tài" and last_5[3] == "Xỉu" and last_5[4] == "Tài":
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": 75,
                "Ly_do": "Pattern T-X-T-X-T, dự đoán Xỉu tiếp theo",
                "Chien_luoc": "Pattern xen kẽ"
            }
        if last_5[0] == "Xỉu" and last_5[1] == "Tài" and last_5[2] == "Xỉu" and last_5[3] == "Tài" and last_5[4] == "Xỉu":
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": 75,
                "Ly_do": "Pattern X-T-X-T-X, dự đoán Tài tiếp theo",
                "Chien_luoc": "Pattern xen kẽ"
            }
    
    # 3. THEO XU HƯỚNG (Trend Following)
    if len(results) >= 10:
        # Lấy 10 phiên gần nhất
        recent_10 = results[:10]
        tai_10 = recent_10.count("Tài")
        xiu_10 = recent_10.count("Xỉu")
        
        # Nếu 1 bên chiếm > 60% trong 10 phiên
        if tai_10 >= 7:
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": 70,
                "Ly_do": f"Tài chiếm {tai_10}/10 phiên gần nhất, xu hướng mạnh",
                "Chien_luoc": "Theo xu hướng Tài"
            }
        if xiu_10 >= 7:
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": 70,
                "Ly_do": f"Xỉu chiếm {xiu_10}/10 phiên gần nhất, xu hướng mạnh",
                "Chien_luoc": "Theo xu hướng Xỉu"
            }
    
    # 4. PHÂN TÍCH TỔNG ĐIỂM (Total Analysis)
    if tong_list and len(tong_list) >= 5:
        # Nếu tổng TB > 12 -> nghiêng Tài
        if tong_trung_binh > 12.5:
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": 62,
                "Ly_do": f"Tổng TB {round(tong_trung_binh, 1)} > 12.5, nghiêng về Tài",
                "Chien_luoc": "Phân tích tổng điểm"
            }
        # Nếu tổng TB < 8.5 -> nghiêng Xỉu
        if tong_trung_binh < 8.5:
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": 62,
                "Ly_do": f"Tổng TB {round(tong_trung_binh, 1)} < 8.5, nghiêng về Xỉu",
                "Chien_luoc": "Phân tích tổng điểm"
            }
    
    # 5. TỶ LỆ TỔNG THỂ (Overall Ratio)
    if total >= 10:
        if tai_ratio >= 58:
            return {
                "Du_doan": "Tài",
                "Do_tin_cay": round(tai_ratio, 1),
                "Ly_do": f"Tài chiếm {round(tai_ratio, 1)}% trong {total} phiên",
                "Chien_luoc": "Tỷ lệ tổng thể"
            }
        if xiu_ratio >= 58:
            return {
                "Du_doan": "Xỉu",
                "Do_tin_cay": round(xiu_ratio, 1),
                "Ly_do": f"Xỉu chiếm {round(xiu_ratio, 1)}% trong {total} phiên",
                "Chien_luoc": "Tỷ lệ tổng thể"
            }
    
    # 6. MẶC ĐỊNH - Dựa vào kết quả gần nhất
    if results:
        # Nếu 2 phiên gần nhất khác nhau -> theo phiên cuối
        if len(results) >= 2 and results[0] != results[1]:
            return {
                "Du_doan": results[0],
                "Do_tin_cay": 55,
                "Ly_do": f"Theo kết quả gần nhất ({results[0]})",
                "Chien_luoc": "Theo xu hướng cuối"
            }
        
        # Nếu tỷ lệ Tài/Xỉu cân bằng -> dự đoán ngẫu nhiên có kiểm soát
        if abs(tai_ratio - xiu_ratio) < 10:
            # Ưu tiên dự đoán theo phiên gần nhất
            return {
                "Du_doan": results[0],
                "Do_tin_cay": 50,
                "Ly_do": f"Dữ liệu cân bằng ({round(tai_ratio, 1)}% - {round(xiu_ratio, 1)}%), theo phiên gần nhất",
                "Chien_luoc": "Cân bằng"
            }
    
    # 7. DỰ ĐOÁN CUỐI CÙNG
    return {
        "Du_doan": random.choice(["Tài", "Xỉu"]),
        "Do_tin_cay": 50,
        "Ly_do": "Không có mẫu hình rõ ràng, dự đoán ngẫu nhiên",
        "Chien_luoc": "Ngẫu nhiên"
    }

# ============== HÀM CHÍNH ==============

default_result = {
    "Phien": 0,
    "Xuc_xac_1": 0,
    "Xuc_xac_2": 0,
    "Xuc_xac_3": 0,
    "Tong": 0,
    "Ket_qua": "Chưa có",
    "Du_doan": "Chưa đủ dữ liệu",
    "Do_tin_cay": 0,
    "Ly_do": "",
    "Chien_luoc": "",
    "So_phien_phan_tich": 0,
    "admin": "Duy Bảo"
}

# Khởi tạo dữ liệu từ file hoặc tạo mới
latest_result_100 = load_data(DATA_FILE_100, default_result)
latest_result_101 = load_data(DATA_FILE_101, default_result)

latest_result_100["admin"] = "Duy Bảo"
latest_result_101["admin"] = "Duy Bảo"

# Load lịch sử từ file
history_100 = load_history(HISTORY_FILE_100)
history_101 = load_history(HISTORY_FILE_101)
predict_history_100 = load_history(PREDICT_FILE_100)
predict_history_101 = load_history(PREDICT_FILE_101)

MAX_PREDICT_HISTORY = 100

last_sid_100 = None
last_sid_101 = None
sid_for_tx = None

current_session_100 = latest_result_100.get("Phien", 0)
current_session_101 = latest_result_101.get("Phien", 0)

def get_tai_xiu(d1, d2, d3):
    total = d1 + d2 + d3
    return "Xỉu" if total <= 10 else "Tài"

def update_result(store, history, lock, result, predict_history, is_md5, data_file, hist_file, pred_file):
    global current_session_100, current_session_101
    
    with lock:
        old_phien = store.get("Phien", 0)
        
        store.clear()
        store.update(result)
        history.insert(0, result.copy())
        if len(history) > MAX_HISTORY:
            history.pop()
        
        if result.get("Ket_qua") and result.get("Ket_qua") != "Chưa có":
            predict_history.insert(0, {
                "phien": result.get("Phien"),
                "ket_qua": result.get("Ket_qua"),
                "tong": result.get("Tong"),
                "xuc_xac": [result.get("Xuc_xac_1"), result.get("Xuc_xac_2"), result.get("Xuc_xac_3")]
            })
            if len(predict_history) > MAX_PREDICT_HISTORY:
                predict_history.pop()
        
        # Cập nhật dự đoán với AI
        du_doan_result = du_doan_ai_thong_minh(predict_history)
        store["Du_doan"] = du_doan_result.get("Du_doan", "Chưa đủ dữ liệu")
        store["Do_tin_cay"] = du_doan_result.get("Do_tin_cay", 0)
        store["Ly_do"] = du_doan_result.get("Ly_do", "")
        store["Chien_luoc"] = du_doan_result.get("Chien_luoc", "")
        store["So_phien_phan_tich"] = len(predict_history)
        
        save_data(data_file, store)
        save_history(hist_file, history)
        save_history(pred_file, predict_history)
        
        new_phien = store.get("Phien", 0)
        if new_phien != old_phien and new_phien > 0:
            if is_md5:
                current_session_101 = new_phien
                logger.info(f"[MD5] 🔄 PHIÊN MỚI: {new_phien}")
            else:
                current_session_100 = new_phien
                logger.info(f"[TX] 🔄 PHIÊN MỚI: {new_phien}")

def poll_api(gid, lock, result_store, history, is_md5):
    global last_sid_100, last_sid_101, sid_for_tx
    url = f"https://jakpotgwab.geightdors.net/glms/v1/notify/taixiu?platform_id=g8&gid={gid}"
    
    if is_md5:
        predict_history = predict_history_101
        data_file = DATA_FILE_101
        hist_file = HISTORY_FILE_101
        pred_file = PREDICT_FILE_101
    else:
        predict_history = predict_history_100
        data_file = DATA_FILE_100
        hist_file = HISTORY_FILE_100
        pred_file = PREDICT_FILE_100
    
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
        hist_100 = load_history(HISTORY_FILE_100)
        hist_101 = load_history(HISTORY_FILE_101)
        response = jsonify({
            "taixiu": hist_100[:limit],
            "taixiumd5": hist_101[:limit],
            "taixiu_total": len(hist_100),
            "taixiumd5_total": len(hist_101),
            "admin": "Duy Bảo"
        })
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

@app.route("/api/reload_history", methods=["GET"])
def reload_history():
    load_full_history()
    return jsonify({
        "status": "success",
        "message": "Đã tải lại lịch sử",
        "taixiu_count": len(history_100),
        "taixiumd5_count": len(history_101),
        "admin": "Duy Bảo"
    })

@app.route("/api/check_update", methods=["GET"])
def check_update():
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
            * { margin: 0; padding: 0; box-sizing: border-box; }
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
            .container { max-width: 800px; width: 100%; margin: 0 auto; }
            .header {
                background: linear-gradient(135deg, #1a1a2e, #16213e);
                border-radius: 16px;
                padding: 20px;
                margin-bottom: 20px;
                text-align: center;
                border: 1px solid #2a3a5e;
            }
            .header h1 { font-size: 24px; color: #ffd700; margin-bottom: 4px; }
            .header .admin { font-size: 14px; color: #88ccff; opacity: 0.8; }
            .header .status { font-size: 13px; color: #66dd88; margin-top: 6px; }
            .header .info { font-size: 12px; color: #6b7a8f; margin-top: 4px; }
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
            .dice-box .number { font-size: 32px; font-weight: 700; }
            .dice-box .label { font-size: 11px; color: #6b7a8f; margin-top: 2px; }
            .result-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 0;
                border-bottom: 1px solid #1f2937;
                flex-wrap: wrap;
                gap: 8px;
            }
            .result-row:last-child { border-bottom: none; }
            .result-row .label { font-size: 14px; color: #9ca3af; }
            .result-row .value { font-size: 16px; font-weight: 600; }
            .value.tai { color: #ff6b6b; }
            .value.xiu { color: #4ecdc4; }
            .value.gold { color: #ffd700; }
            .predict-box {
                background: #0f1a2e;
                border-radius: 10px;
                padding: 14px;
                margin-top: 10px;
                border: 1px solid #1f3a5e;
            }
            .predict-box .title { font-size: 13px; color: #9ca3af; margin-bottom: 6px; }
            .predict-box .main { font-size: 22px; font-weight: 700; }
            .predict-box .main.tai { color: #ff6b6b; }
            .predict-box .main.xiu { color: #4ecdc4; }
            .predict-box .sub { font-size: 13px; color: #9ca3af; margin-top: 4px; }
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
                transition: width 0.5s ease;
            }
            .predict-box .confidence .text {
                font-size: 13px;
                font-weight: 600;
                min-width: 40px;
                text-align: right;
            }
            .predict-box .analyze-count {
                font-size: 11px;
                color: #6b7a8f;
                margin-top: 6px;
            }
            .endpoints { margin-top: 16px; }
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
            .endpoints .item .desc { font-size: 13px; color: #9ca3af; }
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
            .refresh-btn:hover { background: #2a3a5e; }
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
                <div class="info" id="info">📊 Đang tải dữ liệu...</div>
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
                    <div class="title">🔮 Dự đoán phiên tiếp theo (AI)</div>
                    <div class="main" id="dudoan_100">Chưa đủ dữ liệu</div>
                    <div class="sub" id="lydo_100"></div>
                    <div>
                        <span class="strategy-badge" id="chienluoc_100">Chờ dữ liệu</span>
                    </div>
                    <div class="confidence">
                        <span style="font-size:13px;color:#9ca3af;">Độ tin cậy</span>
                        <div class="bar"><div class="fill" id="do_tin_cay_100" style="width:0%"></div></div>
                        <span class="text" id="do_tin_cay_text_100">0%</span>
                    </div>
                    <div class="analyze-count" id="count_100">📊 Đã phân tích: 0 phiên</div>
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
                    <div class="title">🔮 Dự đoán phiên tiếp theo (AI)</div>
                    <div class="main" id="dudoan_101">Chưa đủ dữ liệu</div>
                    <div class="sub" id="lydo_101"></div>
                    <div>
                        <span class="strategy-badge" id="chienluoc_101">Chờ dữ liệu</span>
                    </div>
                    <div class="confidence">
                        <span style="font-size:13px;color:#9ca3af;">Độ tin cậy</span>
                        <div class="bar"><div class="fill" id="do_tin_cay_101" style="width:0%"></div></div>
                        <span class="text" id="do_tin_cay_text_101">0%</span>
                    </div>
                    <div class="analyze-count" id="count_101">📊 Đã phân tích: 0 phiên</div>
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
                    <div class="item">
                        <span class="method">GET</span>
                        <code>/api/reload_history</code>
                        <span class="desc">Tải lại lịch sử</span>
                    </div>
                </div>
            </div>

            <div class="footer">
                🚀 HIT API v3.0 | AI Dự đoán thông minh | Duy Bảo Admin
            </div>
        </div>

        <script>
            async function fetchData() {
                try {
                    const res100 = await fetch('/api/taixiu');
                    const data100 = await res100.json();
                    updateUI(data100, '100');

                    const res101 = await fetch('/api/taixiumd5');
                    const data101 = await res101.json();
                    updateUI(data101, '101');

                    const resHist = await fetch('/api/history?limit=1');
                    const histData = await resHist.json();
                    document.getElementById('info').textContent = 
                        `📊 Bàn thường: ${histData.taixiu_total || 0} phiên | Bàn MD5: ${histData.taixiumd5_total || 0} phiên`;

                    document.getElementById('status').textContent = '🟢 Đã cập nhật - ' + new Date().toLocaleTimeString();
                    document.getElementById('status').style.color = '#66dd88';
                } catch (e) {
                    document.getElementById('status').textContent = '🔴 Lỗi kết nối';
                    document.getElementById('status').style.color = '#ff6b6b';
                    console.error('Fetch error:', e);
                }
            }

            function updateUI(data, suffix) {
                document.getElementById('phien_' + suffix).textContent = '#' + (data.Phien || '---');
                document.getElementById('d1_' + suffix).textContent = data.Xuc_xac_1 || '-';
                document.getElementById('d2_' + suffix).textContent = data.Xuc_xac_2 || '-';
                document.getElementById('d3_' + suffix).textContent = data.Xuc_xac_3 || '-';
                document.getElementById('tong_' + suffix).textContent = data.Tong || 0;
                
                const ketqua = data.Ket_qua || 'Chưa có';
                const ketquaEl = document.getElementById('ketqua_' + suffix);
                ketquaEl.textContent = ketqua;
                ketquaEl.className = 'value ' + (ketqua === 'Tài' ? 'tai' : ketqua === 'Xỉu' ? 'xiu' : '');
                
                const dudoan = data.Du_doan || 'Chưa đủ dữ liệu';
                const dudoanEl = document.getElementById('dudoan_' + suffix);
                dudoanEl.textContent = dudoan;
                dudoanEl.className = 'main ' + (dudoan === 'Tài' ? 'tai' : dudoan === 'Xỉu' ? 'xiu' : '');
                
                document.getElementById('lydo_' + suffix).textContent = data.Ly_do || '';
                document.getElementById('chienluoc_' + suffix).textContent = data.Chien_luoc || 'Đang phân tích';
                
                const doTinCay = data.Do_tin_cay || 0;
                document.getElementById('do_tin_cay_' + suffix).style.width = doTinCay + '%';
                document.getElementById('do_tin_cay_text_' + suffix).textContent = doTinCay + '%';
                
                const soPhien = data.So_phien_phan_tich || 0;
                document.getElementById('count_' + suffix).textContent = `📊 Đã phân tích: ${soPhien} phiên`;
            }

            fetchData();
            setInterval(fetchData, 5000);
        </script>
    </body>
    </html>
    """

# ============== MAIN ==============

if __name__ == "__main__":
    logger.info("🚀 Khởi động hệ thống API Tài Xỉu với AI thông minh...")
    logger.info("=" * 50)
    
    # Load full lịch sử ngay khi khởi động
    load_full_history()
    
    logger.info("=" * 50)
    logger.info("🔄 Bắt đầu polling dữ liệu mới...")
    
    thread_100 = threading.Thread(target=poll_api, args=("vgmn_100", lock_100, latest_result_100, history_100, False), daemon=True)
    thread_101 = threading.Thread(target=poll_api, args=("vgmn_101", lock_101, latest_result_101, history_101, True), daemon=True)
    thread_100.start()
    thread_101.start()
    
    logger.info("✅ Đã bắt đầu polling dữ liệu.")
    port = int(os.environ.get("PORT", 8000))
    app.run(host=HOST, port=port)
