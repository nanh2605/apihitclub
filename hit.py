import json
import threading
import time
import os
import logging
from urllib.request import urlopen, Request
from flask import Flask, jsonify, request
from datetime import datetime
import random
from collections import Counter, deque

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HOST = '0.0.0.0'
POLL_INTERVAL = 5
RETRY_DELAY = 5
MAX_HISTORY = 200

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

# ============== LẤY FULL LỊCH SỬ TỪ API ==============

def fetch_full_history_from_api(gid, is_md5):
    """Lấy FULL lịch sử từ API"""
    history_data = []
    predict_data = []
    
    try:
        url = f"https://jakpotgwab.geightdors.net/glms/v1/notify/taixiu?platform_id=g8&gid={gid}"
        req = Request(url, headers={'User-Agent': 'Python-Proxy/1.0'})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        if data.get('status') == 'OK' and isinstance(data.get('data'), list):
            for game in data['data']:
                cmd = game.get("cmd")
                
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
        
        # Sắp xếp mới nhất đầu
        history_data.sort(key=lambda x: x.get("Phien", 0), reverse=True)
        predict_data.sort(key=lambda x: x.get("phien", 0), reverse=True)
        
        logger.info(f"✅ Đã lấy {len(history_data)} bản ghi từ API cho {gid}")
        return history_data, predict_data
        
    except Exception as e:
        logger.error(f"Lỗi lấy lịch sử {gid}: {e}")
    
    return [], []

def load_full_history():
    """Load FULL lịch sử khi khởi động"""
    global history_100, history_101, predict_history_100, predict_history_101
    global latest_result_100, latest_result_101
    
    logger.info("=" * 60)
    logger.info("🔄 ĐANG LẤY FULL LỊCH SỬ TỪ API...")
    
    # Lấy lịch sử bàn thường
    hist_100, pred_100 = fetch_full_history_from_api("vgmn_100", False)
    if hist_100:
        history_100 = hist_100
        predict_history_100 = pred_100
        save_history(HISTORY_FILE_100, history_100)
        save_history(PREDICT_FILE_100, predict_history_100)
        
        if history_100:
            latest_result_100.update(history_100[0])
            save_data(DATA_FILE_100, latest_result_100)
        
        logger.info(f"✅ Bàn thường: {len(history_100)} phiên")
    else:
        logger.warning("⚠️ Không lấy được lịch sử bàn thường")
    
    # Lấy lịch sử bàn MD5
    hist_101, pred_101 = fetch_full_history_from_api("vgmn_101", True)
    if hist_101:
        history_101 = hist_101
        predict_history_101 = pred_101
        save_history(HISTORY_FILE_101, history_101)
        save_history(PREDICT_FILE_101, predict_history_101)
        
        if history_101:
            latest_result_101.update(history_101[0])
            save_data(DATA_FILE_101, latest_result_101)
        
        logger.info(f"✅ Bàn MD5: {len(history_101)} phiên")
    else:
        logger.warning("⚠️ Không lấy được lịch sử bàn MD5")
    
    # Cập nhật dự đoán VIP
    update_predictions_vip()
    
    logger.info("✅ HOÀN TẤT LẤY FULL LỊCH SỬ!")
    logger.info("=" * 60)

# ============== THUẬT TOÁN DỰ ĐOÁN VIP ==============

def phan_tich_cau_1(predict_history):
    """Phân tích cầu 1: Chuỗi và Pattern"""
    if len(predict_history) < 3:
        return None
    
    results = [r["ket_qua"] for r in predict_history[:20]]
    tong_list = [r.get("tong", 0) for r in predict_history[:20] if r.get("tong", 0) > 0]
    
    # Phân tích chuỗi
    chains = []
    current_chain = 1
    for i in range(1, len(results)):
        if results[i] == results[i-1]:
            current_chain += 1
        else:
            chains.append((results[i-1], current_chain))
            current_chain = 1
    chains.append((results[-1], current_chain))
    
    max_chain = max([c[1] for c in chains]) if chains else 0
    current_result = results[0] if results else ""
    
    # Pattern xen kẽ
    is_alternating = False
    if len(results) >= 5:
        last_5 = results[:5]
        if len(set(last_5)) == 2 and all(last_5[i] != last_5[i+1] for i in range(4)):
            is_alternating = True
    
    # Tổng điểm TB
    tong_tb = sum(tong_list) / len(tong_list) if tong_list else 10.5
    
    return {
        "max_chain": max_chain,
        "current_result": current_result,
        "is_alternating": is_alternating,
        "tong_tb": tong_tb,
        "total_analyzed": len(results)
    }

def phan_tich_cau_2(predict_history):
    """Phân tích cầu 2: Tần suất và Tỷ lệ"""
    if len(predict_history) < 5:
        return None
    
    results = [r["ket_qua"] for r in predict_history[:30]]
    tong_list = [r.get("tong", 0) for r in predict_history[:30] if r.get("tong", 0) > 0]
    
    tai_count = results.count("Tài")
    xiu_count = results.count("Xỉu")
    total = len(results)
    
    # Tỷ lệ
    tai_ratio = tai_count / total * 100 if total > 0 else 0
    xiu_ratio = xiu_count / total * 100 if total > 0 else 0
    
    # Phân phối tổng
    tong_phan_phoi = {}
    for t in tong_list:
        if t not in tong_phan_phoi:
            tong_phan_phoi[t] = 0
        tong_phan_phoi[t] += 1
    
    tong_xuat_hien_nhieu = max(tong_phan_phoi.items(), key=lambda x: x[1])[0] if tong_phan_phoi else 0
    
    return {
        "tai_ratio": tai_ratio,
        "xiu_ratio": xiu_ratio,
        "total": total,
        "tong_xuat_hien_nhieu": tong_xuat_hien_nhieu,
        "tong_tb": sum(tong_list) / len(tong_list) if tong_list else 10.5
    }

def phan_tich_cau_3(predict_history):
    """Phân tích cầu 3: Markov và Xác suất"""
    if len(predict_history) < 10:
        return None
    
    results = [r["ket_qua"] for r in predict_history]
    
    # Ma trận chuyển tiếp Markov
    transitions = {"Tài": {"Tài": 0, "Xỉu": 0}, "Xỉu": {"Tài": 0, "Xỉu": 0}}
    
    for i in range(len(results) - 1):
        current = results[i]
        next_result = results[i + 1]
        transitions[current][next_result] += 1
    
    # Xác suất chuyển tiếp
    last_result = results[0] if results else "Tài"
    total_trans = transitions[last_result]["Tài"] + transitions[last_result]["Xỉu"]
    
    if total_trans > 0:
        prob_tai = transitions[last_result]["Tài"] / total_trans * 100
        prob_xiu = transitions[last_result]["Xỉu"] / total_trans * 100
    else:
        prob_tai = 50
        prob_xiu = 50
    
    return {
        "last_result": last_result,
        "prob_tai": prob_tai,
        "prob_xiu": prob_xiu,
        "transitions": transitions
    }

def phan_tich_cau_4(predict_history):
    """Phân tích cầu 4: Fibonacci và Sóng"""
    if len(predict_history) < 8:
        return None
    
    results = [r["ket_qua"] for r in predict_history[:15]]
    
    # Tìm sóng (wave)
    waves = []
    current_wave = [results[0]]
    for i in range(1, len(results)):
        if results[i] == results[i-1]:
            current_wave.append(results[i])
        else:
            waves.append(current_wave)
            current_wave = [results[i]]
    waves.append(current_wave)
    
    # Phân tích sóng
    wave_lengths = [len(w) for w in waves]
    avg_wave = sum(wave_lengths) / len(wave_lengths) if wave_lengths else 0
    
    # Fibonacci: Nếu sóng dài >= 5 thì khả năng đảo
    last_wave_length = len(waves[-1]) if waves else 0
    
    return {
        "waves": len(waves),
        "avg_wave": avg_wave,
        "last_wave_length": last_wave_length,
        "is_long_wave": last_wave_length >= 5
    }

def du_doan_vip(predict_history):
    """
    DỰ ĐOÁN VIP - Tổng hợp nhiều thuật toán
    """
    if len(predict_history) < 3:
        return {
            "Du_doan": "Chưa đủ dữ liệu",
            "Do_tin_cay": 0,
            "Ly_do": f"Cần ít nhất 3 phiên, hiện có {len(predict_history)} phiên",
            "Chien_luoc": "Chờ dữ liệu"
        }
    
    # Phân tích từ các cầu
    cau1 = phan_tich_cau_1(predict_history)
    cau2 = phan_tich_cau_2(predict_history)
    cau3 = phan_tich_cau_3(predict_history)
    cau4 = phan_tich_cau_4(predict_history)
    
    # Điểm số cho Tài và Xỉu
    diem_tai = 0
    diem_xiu = 0
    ly_do = []
    chien_luoc = ""
    do_tin_cay = 0
    
    # === CẦU 1: CHUỖI VÀ PATTERN ===
    if cau1:
        # Chuỗi dài >= 4 -> đảo chiều
        if cau1["max_chain"] >= 4:
            if cau1["current_result"] == "Tài":
                diem_xiu += 25
                ly_do.append(f"Chuỗi {cau1['max_chain']} Tài, đảo Xỉu")
            else:
                diem_tai += 25
                ly_do.append(f"Chuỗi {cau1['max_chain']} Xỉu, đảo Tài")
            chien_luoc = "Bắt bệt đảo"
            do_tin_cay = min(85, 60 + cau1["max_chain"] * 5)
        
        # Pattern xen kẽ
        if cau1["is_alternating"]:
            last_result = cau1["current_result"]
            if last_result == "Tài":
                diem_xiu += 15
                ly_do.append("Pattern xen kẽ, dự đoán Xỉu")
            else:
                diem_tai += 15
                ly_do.append("Pattern xen kẽ, dự đoán Tài")
            if not chien_luoc:
                chien_luoc = "Pattern xen kẽ"
        
        # Tổng điểm trung bình
        if cau1["tong_tb"] > 12:
            diem_tai += 10
            ly_do.append(f"Tổng TB {round(cau1['tong_tb'], 1)} > 12")
        elif cau1["tong_tb"] < 9:
            diem_xiu += 10
            ly_do.append(f"Tổng TB {round(cau1['tong_tb'], 1)} < 9")
    
    # === CẦU 2: TẦN SUẤT VÀ TỶ LỆ ===
    if cau2:
        if cau2["tai_ratio"] >= 60:
            diem_tai += 20
            ly_do.append(f"Tài {round(cau2['tai_ratio'], 1)}%")
        elif cau2["xiu_ratio"] >= 60:
            diem_xiu += 20
            ly_do.append(f"Xỉu {round(cau2['xiu_ratio'], 1)}%")
        
        # Tổng xuất hiện nhiều
        if cau2["tong_xuat_hien_nhieu"] > 10:
            diem_tai += 5
        elif cau2["tong_xuat_hien_nhieu"] < 8:
            diem_xiu += 5
    
    # === CẦU 3: MARKOV ===
    if cau3:
        if cau3["prob_tai"] > cau3["prob_xiu"] + 15:
            diem_tai += 20
            ly_do.append(f"Markov: Tài {round(cau3['prob_tai'], 1)}%")
        elif cau3["prob_xiu"] > cau3["prob_tai"] + 15:
            diem_xiu += 20
            ly_do.append(f"Markov: Xỉu {round(cau3['prob_xiu'], 1)}%")
        
        if not chien_luoc:
            chien_luoc = "Markov Chain"
    
    # === CẦU 4: SÓNG FIBONACCI ===
    if cau4:
        if cau4["is_long_wave"]:
            last_result = predict_history[0]["ket_qua"]
            if last_result == "Tài":
                diem_xiu += 15
                ly_do.append(f"Sóng dài {cau4['last_wave_length']}, đảo Xỉu")
            else:
                diem_tai += 15
                ly_do.append(f"Sóng dài {cau4['last_wave_length']}, đảo Tài")
            if not chien_luoc:
                chien_luoc = "Fibonacci Wave"
    
    # === TỔNG HỢP ===
    tong_diem = diem_tai + diem_xiu
    
    if tong_diem == 0:
        # Không có dữ liệu phân tích
        last_result = predict_history[0]["ket_qua"]
        du_doan = "Xỉu" if last_result == "Tài" else "Tài"
        do_tin_cay = 50
        ly_do_text = "Dữ liệu cân bằng, dự đoán ngẫu nhiên"
        chien_luoc = "Ngẫu nhiên có kiểm soát"
    else:
        # Tính độ tin cậy dựa trên chênh lệch điểm
        chech_lech = abs(diem_tai - diem_xiu)
        tong_diem_max = tong_diem
        do_tin_cay = min(95, 50 + (chech_lech / tong_diem_max) * 50) if tong_diem_max > 0 else 50
        
        if diem_tai > diem_xiu:
            du_doan = "Tài"
        elif diem_xiu > diem_tai:
            du_doan = "Xỉu"
        else:
            du_doan = random.choice(["Tài", "Xỉu"])
        
        # Lấy lý do có điểm cao nhất
        if ly_do:
            ly_do_text = " | ".join(ly_do[:3])
        else:
            ly_do_text = "Phân tích tổng hợp"
    
    return {
        "Du_doan": du_doan,
        "Do_tin_cay": round(do_tin_cay, 1),
        "Ly_do": ly_do_text,
        "Chien_luoc": chien_luoc if chien_luoc else "Tổng hợp",
        "Diem_Tai": round(diem_tai, 1),
        "Diem_Xiu": round(diem_xiu, 1),
        "So_phien_phan_tich": len(predict_history)
    }

def update_predictions_vip():
    """Cập nhật dự đoán VIP cho cả 2 bàn"""
    
    with lock_100:
        if predict_history_100:
            du_doan = du_doan_vip(predict_history_100)
            latest_result_100["Du_doan"] = du_doan.get("Du_doan", "Chưa đủ dữ liệu")
            latest_result_100["Do_tin_cay"] = du_doan.get("Do_tin_cay", 0)
            latest_result_100["Ly_do"] = du_doan.get("Ly_do", "")
            latest_result_100["Chien_luoc"] = du_doan.get("Chien_luoc", "")
            latest_result_100["Diem_Tai"] = du_doan.get("Diem_Tai", 0)
            latest_result_100["Diem_Xiu"] = du_doan.get("Diem_Xiu", 0)
            latest_result_100["So_phien_phan_tich"] = len(predict_history_100)
            save_data(DATA_FILE_100, latest_result_100)
            
            logger.info(f"📊 Bàn thường: {latest_result_100['Du_doan']} (độ tin cậy {latest_result_100['Do_tin_cay']}%) - {latest_result_100['Chien_luoc']}")
        else:
            latest_result_100["Du_doan"] = "Chưa có dữ liệu lịch sử"
            latest_result_100["Do_tin_cay"] = 0
            latest_result_100["Ly_do"] = "Hãy tải lại lịch sử hoặc đợi phiên mới"
            latest_result_100["Chien_luoc"] = "Không có dữ liệu"
            latest_result_100["Diem_Tai"] = 0
            latest_result_100["Diem_Xiu"] = 0
            latest_result_100["So_phien_phan_tich"] = 0
            save_data(DATA_FILE_100, latest_result_100)
    
    with lock_101:
        if predict_history_101:
            du_doan = du_doan_vip(predict_history_101)
            latest_result_101["Du_doan"] = du_doan.get("Du_doan", "Chưa đủ dữ liệu")
            latest_result_101["Do_tin_cay"] = du_doan.get("Do_tin_cay", 0)
            latest_result_101["Ly_do"] = du_doan.get("Ly_do", "")
            latest_result_101["Chien_luoc"] = du_doan.get("Chien_luoc", "")
            latest_result_101["Diem_Tai"] = du_doan.get("Diem_Tai", 0)
            latest_result_101["Diem_Xiu"] = du_doan.get("Diem_Xiu", 0)
            latest_result_101["So_phien_phan_tich"] = len(predict_history_101)
            save_data(DATA_FILE_101, latest_result_101)
            
            logger.info(f"📊 Bàn MD5: {latest_result_101['Du_doan']} (độ tin cậy {latest_result_101['Do_tin_cay']}%) - {latest_result_101['Chien_luoc']}")
        else:
            latest_result_101["Du_doan"] = "Chưa có dữ liệu lịch sử"
            latest_result_101["Do_tin_cay"] = 0
            latest_result_101["Ly_do"] = "Hãy tải lại lịch sử hoặc đợi phiên mới"
            latest_result_101["Chien_luoc"] = "Không có dữ liệu"
            latest_result_101["Diem_Tai"] = 0
            latest_result_101["Diem_Xiu"] = 0
            latest_result_101["So_phien_phan_tich"] = 0
            save_data(DATA_FILE_101, latest_result_101)

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
    "Diem_Tai": 0,
    "Diem_Xiu": 0,
    "So_phien_phan_tich": 0,
    "admin": "Duy Bảo"
}

# Khởi tạo dữ liệu
latest_result_100 = load_data(DATA_FILE_100, default_result)
latest_result_101 = load_data(DATA_FILE_101, default_result)

latest_result_100["admin"] = "Duy Bảo"
latest_result_101["admin"] = "Duy Bảo"

# Load lịch sử
history_100 = load_history(HISTORY_FILE_100)
history_101 = load_history(HISTORY_FILE_101)
predict_history_100 = load_history(PREDICT_FILE_100)
predict_history_101 = load_history(PREDICT_FILE_101)

MAX_PREDICT_HISTORY = 200

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
        
        # Cập nhật dự đoán VIP
        du_doan = du_doan_vip(predict_history)
        store["Du_doan"] = du_doan.get("Du_doan", "Chưa đủ dữ liệu")
        store["Do_tin_cay"] = du_doan.get("Do_tin_cay", 0)
        store["Ly_do"] = du_doan.get("Ly_do", "")
        store["Chien_luoc"] = du_doan.get("Chien_luoc", "")
        store["Diem_Tai"] = du_doan.get("Diem_Tai", 0)
        store["Diem_Xiu"] = du_doan.get("Diem_Xiu", 0)
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

# ============== MAIN ==============

if __name__ == "__main__":
    logger.info("🚀 KHỞI ĐỘNG HỆ THỐNG DỰ ĐOÁN VIP...")
    logger.info("=" * 60)
    
    # Load FULL lịch sử ngay khi khởi động
    load_full_history()
    
    logger.info("=" * 60)
    logger.info("🔄 BẮT ĐẦU POLLING DỮ LIỆU MỚI...")
    
    thread_100 = threading.Thread(target=poll_api, args=("vgmn_100", lock_100, latest_result_100, history_100, False), daemon=True)
    thread_101 = threading.Thread(target=poll_api, args=("vgmn_101", lock_101, latest_result_101, history_101, True), daemon=True)
    thread_100.start()
    thread_101.start()
    
    logger.info("✅ ĐÃ BẮT ĐẦU POLLING.")
    port = int(os.environ.get("PORT", 8000))
    app.run(host=HOST, port=port)
