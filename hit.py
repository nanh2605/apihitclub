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

# ============== LẤY LỊCH SỬ TỪ API ==============

def fetch_history_from_api_tx():
    """Lấy lịch sử từ API TX: 103.238.235.159:5000/hitclub/his/tx"""
    history_data = []
    predict_data = []
    
    try:
        url = "http://103.238.235.159:5000/hitclub/his/tx"
        req = Request(url, headers={'User-Agent': 'Python-Proxy/1.0'})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        # Kiểm tra cấu trúc dữ liệu
        if isinstance(data, list):
            for item in data:
                # Lấy các trường từ API
                sid = item.get("phien") or item.get("Phien") or item.get("id") or item.get("sid")
                d1 = item.get("xuc_xac_1") or item.get("Xuc_xac_1") or item.get("d1", 0)
                d2 = item.get("xuc_xac_2") or item.get("Xuc_xac_2") or item.get("d2", 0)
                d3 = item.get("xuc_xac_3") or item.get("Xuc_xac_3") or item.get("d3", 0)
                total = item.get("tong") or item.get("Tong") or item.get("total", 0)
                ket_qua = item.get("ket_qua") or item.get("Ket_qua") or item.get("result", "")
                
                # Nếu có đủ dữ liệu
                if sid and total > 0:
                    if not ket_qua:
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
        
        logger.info(f"✅ Đã lấy {len(history_data)} bản ghi từ API TX")
        return history_data, predict_data
        
    except Exception as e:
        logger.error(f"Lỗi lấy lịch sử TX: {e}")
    
    return [], []

def fetch_history_from_api_md5():
    """Lấy lịch sử từ API MD5: 103.238.235.159:5000/hitclub/his/md5"""
    history_data = []
    predict_data = []
    
    try:
        url = "http://103.238.235.159:5000/hitclub/his/md5"
        req = Request(url, headers={'User-Agent': 'Python-Proxy/1.0'})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        # Kiểm tra cấu trúc dữ liệu
        if isinstance(data, list):
            for item in data:
                sid = item.get("phien") or item.get("Phien") or item.get("id") or item.get("sid")
                d1 = item.get("xuc_xac_1") or item.get("Xuc_xac_1") or item.get("d1", 0)
                d2 = item.get("xuc_xac_2") or item.get("Xuc_xac_2") or item.get("d2", 0)
                d3 = item.get("xuc_xac_3") or item.get("Xuc_xac_3") or item.get("d3", 0)
                total = item.get("tong") or item.get("Tong") or item.get("total", 0)
                ket_qua = item.get("ket_qua") or item.get("Ket_qua") or item.get("result", "")
                
                if sid and total > 0:
                    if not ket_qua:
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
        
        logger.info(f"✅ Đã lấy {len(history_data)} bản ghi từ API MD5")
        return history_data, predict_data
        
    except Exception as e:
        logger.error(f"Lỗi lấy lịch sử MD5: {e}")
    
    return [], []

def load_full_history():
    """Load FULL lịch sử từ 2 API"""
    global history_100, history_101, predict_history_100, predict_history_101
    global latest_result_100, latest_result_101
    
    logger.info("=" * 60)
    logger.info("🔄 ĐANG LẤY LỊCH SỬ TỪ API...")
    
    # Lấy lịch sử TX
    hist_100, pred_100 = fetch_history_from_api_tx()
    if hist_100:
        history_100 = hist_100
        predict_history_100 = pred_100
        save_history(HISTORY_FILE_100, history_100)
        save_history(PREDICT_FILE_100, predict_history_100)
        
        if history_100:
            latest_result_100.update(history_100[0])
            save_data(DATA_FILE_100, latest_result_100)
        
        logger.info(f"✅ TX: {len(history_100)} phiên")
    else:
        # Nếu không lấy được, dùng dữ liệu cũ
        logger.warning("⚠️ Không lấy được lịch sử TX, dùng dữ liệu cũ")
    
    # Lấy lịch sử MD5
    hist_101, pred_101 = fetch_history_from_api_md5()
    if hist_101:
        history_101 = hist_101
        predict_history_101 = pred_101
        save_history(HISTORY_FILE_101, history_101)
        save_history(PREDICT_FILE_101, predict_history_101)
        
        if history_101:
            latest_result_101.update(history_101[0])
            save_data(DATA_FILE_101, latest_result_101)
        
        logger.info(f"✅ MD5: {len(history_101)} phiên")
    else:
        logger.warning("⚠️ Không lấy được lịch sử MD5, dùng dữ liệu cũ")
    
    # Cập nhật dự đoán VIP
    update_predictions_vip()
    
    logger.info("✅ HOÀN TẤT LẤY LỊCH SỬ!")
    logger.info("=" * 60)

# ============== THUẬT TOÁN DỰ ĐOÁN VIP NÂNG CẤP ==============

def phan_tich_cau_1_chuoi_pattern(predict_history):
    """Cầu 1: Phân tích chuỗi và pattern"""
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
    
    # Pattern 2-1-2
    pattern_212 = False
    if len(results) >= 3:
        if results[0] == results[2] and results[0] != results[1]:
            pattern_212 = True
    
    tong_tb = sum(tong_list) / len(tong_list) if tong_list else 10.5
    
    return {
        "max_chain": max_chain,
        "current_result": current_result,
        "is_alternating": is_alternating,
        "pattern_212": pattern_212,
        "tong_tb": tong_tb,
        "total_analyzed": len(results)
    }

def phan_tich_cau_2_tan_suat(predict_history):
    """Cầu 2: Phân tích tần suất và tỷ lệ"""
    if len(predict_history) < 5:
        return None
    
    results = [r["ket_qua"] for r in predict_history[:50]]
    tong_list = [r.get("tong", 0) for r in predict_history[:50] if r.get("tong", 0) > 0]
    
    tai_count = results.count("Tài")
    xiu_count = results.count("Xỉu")
    total = len(results)
    
    tai_ratio = tai_count / total * 100 if total > 0 else 0
    xiu_ratio = xiu_count / total * 100 if total > 0 else 0
    
    # Phân phối tổng
    tong_phan_phoi = {}
    for t in tong_list:
        if t not in tong_phan_phoi:
            tong_phan_phoi[t] = 0
        tong_phan_phoi[t] += 1
    
    tong_xuat_hien_nhieu = max(tong_phan_phoi.items(), key=lambda x: x[1])[0] if tong_phan_phoi else 0
    
    # 10 phiên gần nhất
    recent_10 = results[:10]
    tai_10 = recent_10.count("Tài")
    xiu_10 = recent_10.count("Xỉu")
    
    return {
        "tai_ratio": tai_ratio,
        "xiu_ratio": xiu_ratio,
        "total": total,
        "tong_xuat_hien_nhieu": tong_xuat_hien_nhieu,
        "tong_tb": sum(tong_list) / len(tong_list) if tong_list else 10.5,
        "tai_10": tai_10,
        "xiu_10": xiu_10
    }

def phan_tich_cau_3_markov(predict_history):
    """Cầu 3: Markov Chain và xác suất"""
    if len(predict_history) < 10:
        return None
    
    results = [r["ket_qua"] for r in predict_history]
    
    # Ma trận chuyển tiếp Markov bậc 1
    transitions = {"Tài": {"Tài": 0, "Xỉu": 0}, "Xỉu": {"Tài": 0, "Xỉu": 0}}
    
    for i in range(len(results) - 1):
        current = results[i]
        next_result = results[i + 1]
        transitions[current][next_result] += 1
    
    # Bậc 2
    transitions_2 = {}
    for i in range(len(results) - 2):
        key = results[i] + "-" + results[i+1]
        next_result = results[i+2]
        if key not in transitions_2:
            transitions_2[key] = {"Tài": 0, "Xỉu": 0}
        transitions_2[key][next_result] += 1
    
    # Xác suất bậc 1
    last_result = results[0] if results else "Tài"
    total_trans = transitions[last_result]["Tài"] + transitions[last_result]["Xỉu"]
    
    if total_trans > 0:
        prob_tai = transitions[last_result]["Tài"] / total_trans * 100
        prob_xiu = transitions[last_result]["Xỉu"] / total_trans * 100
    else:
        prob_tai = 50
        prob_xiu = 50
    
    # Xác suất bậc 2
    prob_tai_2 = 50
    prob_xiu_2 = 50
    if len(results) >= 2:
        key_2 = results[0] + "-" + results[1]
        if key_2 in transitions_2:
            total_2 = transitions_2[key_2]["Tài"] + transitions_2[key_2]["Xỉu"]
            if total_2 > 0:
                prob_tai_2 = transitions_2[key_2]["Tài"] / total_2 * 100
                prob_xiu_2 = transitions_2[key_2]["Xỉu"] / total_2 * 100
    
    return {
        "last_result": last_result,
        "prob_tai": prob_tai,
        "prob_xiu": prob_xiu,
        "prob_tai_2": prob_tai_2,
        "prob_xiu_2": prob_xiu_2
    }

def phan_tich_cau_4_song_fibonacci(predict_history):
    """Cầu 4: Phân tích sóng Fibonacci"""
    if len(predict_history) < 8:
        return None
    
    results = [r["ket_qua"] for r in predict_history[:20]]
    tong_list = [r.get("tong", 0) for r in predict_history[:20] if r.get("tong", 0) > 0]
    
    # Tìm sóng
    waves = []
    current_wave = [results[0]]
    for i in range(1, len(results)):
        if results[i] == results[i-1]:
            current_wave.append(results[i])
        else:
            waves.append(current_wave)
            current_wave = [results[i]]
    waves.append(current_wave)
    
    wave_lengths = [len(w) for w in waves]
    avg_wave = sum(wave_lengths) / len(wave_lengths) if wave_lengths else 0
    last_wave_length = len(waves[-1]) if waves else 0
    
    fibonacci_numbers = [1, 2, 3, 5, 8, 13]
    is_fibonacci = last_wave_length in fibonacci_numbers
    
    tong_tb = sum(tong_list) / len(tong_list) if tong_list else 10.5
    fib_ratio = tong_tb / 18 * 100
    
    return {
        "waves": len(waves),
        "avg_wave": avg_wave,
        "last_wave_length": last_wave_length,
        "is_fibonacci": is_fibonacci,
        "fib_ratio": fib_ratio,
        "is_long_wave": last_wave_length >= 5
    }

def phan_tich_cau_5_bollinger(predict_history):
    """Cầu 5: Bollinger Bands"""
    if len(predict_history) < 10:
        return None
    
    tong_list = [r.get("tong", 0) for r in predict_history[:20] if r.get("tong", 0) > 0]
    
    if len(tong_list) < 5:
        return None
    
    avg = sum(tong_list) / len(tong_list)
    variance = sum((x - avg) ** 2 for x in tong_list) / len(tong_list)
    std_dev = variance ** 0.5
    
    upper_band = avg + 2 * std_dev
    lower_band = avg - 2 * std_dev
    
    current_tong = tong_list[0] if tong_list else 0
    
    if current_tong > upper_band:
        signal = "Xỉu"
    elif current_tong < lower_band:
        signal = "Tài"
    else:
        if len(tong_list) >= 3:
            trend = tong_list[0] - tong_list[2]
            signal = "Tài" if trend > 0 else "Xỉu"
        else:
            signal = None
    
    return {
        "avg": avg,
        "std_dev": std_dev,
        "upper_band": upper_band,
        "lower_band": lower_band,
        "current_tong": current_tong,
        "signal": signal,
        "volatility": std_dev / avg if avg > 0 else 0
    }

def phan_tich_cau_6_heuristic(predict_history):
    """Cầu 6: Heuristic - Kinh nghiệm thực tế"""
    if len(predict_history) < 10:
        return None
    
    results = [r["ket_qua"] for r in predict_history[:20]]
    
    last_3 = results[:3] if len(results) >= 3 else []
    tai_count = results.count("Tài")
    xiu_count = results.count("Xỉu")
    total = len(results)
    
    tai_ratio = tai_count / total * 100 if total > 0 else 50
    
    # Bệt 3 phiên
    if len(last_3) == 3 and last_3[0] == last_3[1] == last_3[2]:
        if last_3[0] == "Tài" and tai_ratio > 55:
            return {"Du_doan": "Xỉu", "heuristic": "Bệt 3 Tài, tỷ lệ Tài cao", "weight": 80}
        elif last_3[0] == "Xỉu" and tai_ratio < 45:
            return {"Du_doan": "Tài", "heuristic": "Bệt 3 Xỉu, tỷ lệ Xỉu cao", "weight": 80}
    
    # 2 phiên gần nhất khác nhau
    if len(results) >= 2 and results[0] != results[1]:
        if tai_ratio > 50:
            return {"Du_doan": "Tài", "heuristic": "Xu hướng Tài", "weight": 60}
        else:
            return {"Du_doan": "Xỉu", "heuristic": "Xu hướng Xỉu", "weight": 60}
    
    # Pattern 2-1
    if len(results) >= 3 and results[0] == results[2] and results[0] != results[1]:
        return {"Du_doan": results[0], "heuristic": "Pattern 2-1", "weight": 70}
    
    return None

def du_doan_vip_nang_cao(predict_history):
    """DỰ ĐOÁN VIP NÂNG CẤP - Tổng hợp 6 cầu phân tích"""
    if len(predict_history) < 3:
        return {
            "Du_doan": "Chưa đủ dữ liệu",
            "Do_tin_cay": 0,
            "Ly_do": f"Cần ít nhất 3 phiên, hiện có {len(predict_history)} phiên",
            "Chien_luoc": "Chờ dữ liệu",
            "Cac_cau_da_phan_tich": []
        }
    
    # Phân tích từ các cầu
    cau1 = phan_tich_cau_1_chuoi_pattern(predict_history)
    cau2 = phan_tich_cau_2_tan_suat(predict_history)
    cau3 = phan_tich_cau_3_markov(predict_history)
    cau4 = phan_tich_cau_4_song_fibonacci(predict_history)
    cau5 = phan_tich_cau_5_bollinger(predict_history)
    cau6 = phan_tich_cau_6_heuristic(predict_history)
    
    diem_tai = 0
    diem_xiu = 0
    ly_do = []
    chien_luoc = []
    cac_cau = []
    
    # CẦU 1: CHUỖI VÀ PATTERN
    if cau1:
        cac_cau.append("Cầu 1: Chuỗi & Pattern")
        if cau1["max_chain"] >= 4:
            if cau1["current_result"] == "Tài":
                diem_xiu += 30
                ly_do.append(f"🔴 Chuỗi {cau1['max_chain']} Tài, đảo Xỉu")
            else:
                diem_tai += 30
                ly_do.append(f"🔴 Chuỗi {cau1['max_chain']} Xỉu, đảo Tài")
            chien_luoc.append("Bắt bệt đảo")
        
        if cau1["is_alternating"]:
            if cau1["current_result"] == "Tài":
                diem_xiu += 20
                ly_do.append("🔄 Pattern xen kẽ, dự đoán Xỉu")
            else:
                diem_tai += 20
                ly_do.append("🔄 Pattern xen kẽ, dự đoán Tài")
            chien_luoc.append("Pattern xen kẽ")
        
        if cau1["pattern_212"]:
            if cau1["current_result"] == "Tài":
                diem_tai += 15
                ly_do.append("📐 Pattern 2-1-2, theo Tài")
            else:
                diem_xiu += 15
                ly_do.append("📐 Pattern 2-1-2, theo Xỉu")
            chien_luoc.append("Pattern 2-1-2")
        
        if cau1["tong_tb"] > 12.5:
            diem_tai += 15
            ly_do.append(f"📊 Tổng TB {round(cau1['tong_tb'], 1)} > 12.5")
        elif cau1["tong_tb"] < 8.5:
            diem_xiu += 15
            ly_do.append(f"📊 Tổng TB {round(cau1['tong_tb'], 1)} < 8.5")
    
    # CẦU 2: TẦN SUẤT
    if cau2:
        cac_cau.append("Cầu 2: Tần suất & Tỷ lệ")
        if cau2["tai_ratio"] >= 58:
            diem_tai += 20
            ly_do.append(f"📈 Tài {round(cau2['tai_ratio'], 1)}% trong {cau2['total']} phiên")
        elif cau2["xiu_ratio"] >= 58:
            diem_xiu += 20
            ly_do.append(f"📉 Xỉu {round(cau2['xiu_ratio'], 1)}% trong {cau2['total']} phiên")
        
        if cau2["tai_10"] >= 7:
            diem_tai += 15
            ly_do.append(f"🔥 Tài {cau2['tai_10']}/10 phiên gần nhất")
        elif cau2["xiu_10"] >= 7:
            diem_xiu += 15
            ly_do.append(f"🔥 Xỉu {cau2['xiu_10']}/10 phiên gần nhất")
        
        if not chien_luoc:
            chien_luoc.append("Phân tích tần suất")
    
    # CẦU 3: MARKOV
    if cau3:
        cac_cau.append("Cầu 3: Markov Chain")
        if cau3["prob_tai"] > cau3["prob_xiu"] + 15:
            diem_tai += 20
            ly_do.append(f"🎯 Markov: Tài {round(cau3['prob_tai'], 1)}%")
        elif cau3["prob_xiu"] > cau3["prob_tai"] + 15:
            diem_xiu += 20
            ly_do.append(f"🎯 Markov: Xỉu {round(cau3['prob_xiu'], 1)}%")
        
        if cau3["prob_tai_2"] > cau3["prob_xiu_2"] + 15:
            diem_tai += 15
            ly_do.append(f"🎯 Markov b2: Tài {round(cau3['prob_tai_2'], 1)}%")
        elif cau3["prob_xiu_2"] > cau3["prob_tai_2"] + 15:
            diem_xiu += 15
            ly_do.append(f"🎯 Markov b2: Xỉu {round(cau3['prob_xiu_2'], 1)}%")
        
        if not chien_luoc:
            chien_luoc.append("Markov Chain")
    
    # CẦU 4: FIBONACCI
    if cau4:
        cac_cau.append("Cầu 4: Fibonacci Wave")
        if cau4["is_long_wave"] or cau4["is_fibonacci"]:
            if cau4["last_wave_length"] >= 5:
                last_result = predict_history[0]["ket_qua"]
                if last_result == "Tài":
                    diem_xiu += 20
                    ly_do.append(f"🌊 Sóng dài {cau4['last_wave_length']}, đảo Xỉu")
                else:
                    diem_tai += 20
                    ly_do.append(f"🌊 Sóng dài {cau4['last_wave_length']}, đảo Tài")
                chien_luoc.append("Fibonacci Wave")
    
    # CẦU 5: BOLLINGER
    if cau5:
        cac_cau.append("Cầu 5: Bollinger Bands")
        if cau5["signal"] == "Tài":
            diem_tai += 20
            ly_do.append(f"📊 Bollinger: Tài")
        elif cau5["signal"] == "Xỉu":
            diem_xiu += 20
            ly_do.append(f"📊 Bollinger: Xỉu")
    
    # CẦU 6: HEURISTIC
    if cau6:
        cac_cau.append("Cầu 6: Heuristic")
        if cau6["Du_doan"] == "Tài":
            diem_tai += cau6["weight"]
            ly_do.append(f"🧠 {cau6['heuristic']}")
        else:
            diem_xiu += cau6["weight"]
            ly_do.append(f"🧠 {cau6['heuristic']}")
        chien_luoc.append("Heuristic")
    
    # TỔNG HỢP
    tong_diem = diem_tai + diem_xiu
    
    if tong_diem == 0:
        last_result = predict_history[0]["ket_qua"]
        du_doan = "Xỉu" if last_result == "Tài" else "Tài"
        do_tin_cay = 50
        ly_do_text = "Không có tín hiệu rõ ràng, theo nguyên lý đảo chiều"
        chien_luoc_text = "Đảo chiều an toàn"
    else:
        chech_lech = abs(diem_tai - diem_xiu)
        tong_diem_max = tong_diem
        do_tin_cay = min(95, 50 + (chech_lech / tong_diem_max) * 50) if tong_diem_max > 0 else 50
        
        if diem_tai > diem_xiu:
            du_doan = "Tài"
        elif diem_xiu > diem_tai:
            du_doan = "Xỉu"
        else:
            du_doan = predict_history[0]["ket_qua"]
            do_tin_cay = 52
        
        if ly_do:
            ly_do_text = " | ".join(ly_do[:4])
        else:
            ly_do_text = "Phân tích tổng hợp từ 6 cầu"
        
        if chien_luoc:
            chien_luoc_text = " + ".join(list(dict.fromkeys(chien_luoc))[:3])
        else:
            chien_luoc_text = "Tổng hợp 6 cầu"
    
    return {
        "Du_doan": du_doan,
        "Do_tin_cay": round(do_tin_cay, 1),
        "Ly_do": ly_do_text,
        "Chien_luoc": chien_luoc_text,
        "Diem_Tai": round(diem_tai, 1),
        "Diem_Xiu": round(diem_xiu, 1),
        "So_phien_phan_tich": len(predict_history),
        "Cac_cau_da_phan_tich": cac_cau if cac_cau else ["Chưa có đủ dữ liệu"]
    }

def update_predictions_vip():
    """Cập nhật dự đoán VIP cho cả 2 bàn"""
    with lock_100:
        if predict_history_100:
            du_doan = du_doan_vip_nang_cao(predict_history_100)
            latest_result_100["Du_doan"] = du_doan.get("Du_doan", "Chưa đủ dữ liệu")
            latest_result_100["Do_tin_cay"] = du_doan.get("Do_tin_cay", 0)
            latest_result_100["Ly_do"] = du_doan.get("Ly_do", "")
            latest_result_100["Chien_luoc"] = du_doan.get("Chien_luoc", "")
            latest_result_100["Diem_Tai"] = du_doan.get("Diem_Tai", 0)
            latest_result_100["Diem_Xiu"] = du_doan.get("Diem_Xiu", 0)
            latest_result_100["So_phien_phan_tich"] = len(predict_history_100)
            latest_result_100["Cac_cau_da_phan_tich"] = du_doan.get("Cac_cau_da_phan_tich", [])
            save_data(DATA_FILE_100, latest_result_100)
            logger.info(f"📊 TX: {latest_result_100['Du_doan']} (độ tin cậy {latest_result_100['Do_tin_cay']}%)")
        else:
            latest_result_100["Du_doan"] = "Chưa có dữ liệu lịch sử"
            latest_result_100["Do_tin_cay"] = 0
            latest_result_100["Ly_do"] = "Hãy tải lại lịch sử"
            latest_result_100["Chien_luoc"] = "Không có dữ liệu"
            latest_result_100["Cac_cau_da_phan_tich"] = []
            save_data(DATA_FILE_100, latest_result_100)
    
    with lock_101:
        if predict_history_101:
            du_doan = du_doan_vip_nang_cao(predict_history_101)
            latest_result_101["Du_doan"] = du_doan.get("Du_doan", "Chưa đủ dữ liệu")
            latest_result_101["Do_tin_cay"] = du_doan.get("Do_tin_cay", 0)
            latest_result_101["Ly_do"] = du_doan.get("Ly_do", "")
            latest_result_101["Chien_luoc"] = du_doan.get("Chien_luoc", "")
            latest_result_101["Diem_Tai"] = du_doan.get("Diem_Tai", 0)
            latest_result_101["Diem_Xiu"] = du_doan.get("Diem_Xiu", 0)
            latest_result_101["So_phien_phan_tich"] = len(predict_history_101)
            latest_result_101["Cac_cau_da_phan_tich"] = du_doan.get("Cac_cau_da_phan_tich", [])
            save_data(DATA_FILE_101, latest_result_101)
            logger.info(f"📊 MD5: {latest_result_101['Du_doan']} (độ tin cậy {latest_result_101['Do_tin_cay']}%)")
        else:
            latest_result_101["Du_doan"] = "Chưa có dữ liệu lịch sử"
            latest_result_101["Do_tin_cay"] = 0
            latest_result_101["Ly_do"] = "Hãy tải lại lịch sử"
            latest_result_101["Chien_luoc"] = "Không có dữ liệu"
            latest_result_101["Cac_cau_da_phan_tich"] = []
            save_data(DATA_FILE_101, latest_result_101)

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
    "Ly_do": "",
    "Chien_luoc": "",
    "Diem_Tai": 0,
    "Diem_Xiu": 0,
    "So_phien_phan_tich": 0,
    "Cac_cau_da_phan_tich": [],
    "admin": "Duy Bảo"
}

# Khởi tạo dữ liệu từ file
latest_result_100 = load_data(DATA_FILE_100, default_result)
latest_result_101 = load_data(DATA_FILE_101, default_result)

latest_result_100["admin"] = "Duy Bảo"
latest_result_101["admin"] = "Duy Bảo"

# Load lịch sử từ file
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

# ============== HÀM POLL API ==============

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
        du_doan = du_doan_vip_nang_cao(predict_history)
        store["Du_doan"] = du_doan.get("Du_doan", "Chưa đủ dữ liệu")
        store["Do_tin_cay"] = du_doan.get("Do_tin_cay", 0)
        store["Ly_do"] = du_doan.get("Ly_do", "")
        store["Chien_luoc"] = du_doan.get("Chien_luoc", "")
        store["Diem_Tai"] = du_doan.get("Diem_Tai", 0)
        store["Diem_Xiu"] = du_doan.get("Diem_Xiu", 0)
        store["So_phien_phan_tich"] = len(predict_history)
        store["Cac_cau_da_phan_tich"] = du_doan.get("Cac_cau_da_phan_tich", [])
        
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
    """API lịch sử - tự động lưu và không bị mất"""
    limit = request.args.get('limit', 50, type=int)
    
    # Load lịch sử từ file
    hist_100 = load_history(HISTORY_FILE_100)
    hist_101 = load_history(HISTORY_FILE_101)
    
    # Nếu chưa có dữ liệu, thử lấy từ API
    if not hist_100:
        logger.info("Chưa có lịch sử TX, đang lấy từ API...")
        hist_100, pred_100 = fetch_history_from_api_tx()
        if hist_100:
            save_history(HISTORY_FILE_100, hist_100)
            save_history(PREDICT_FILE_100, pred_100)
            logger.info(f"Đã lưu {len(hist_100)} bản ghi TX")
    
    if not hist_101:
        logger.info("Chưa có lịch sử MD5, đang lấy từ API...")
        hist_101, pred_101 = fetch_history_from_api_md5()
        if hist_101:
            save_history(HISTORY_FILE_101, hist_101)
            save_history(PREDICT_FILE_101, pred_101)
            logger.info(f"Đã lưu {len(hist_101)} bản ghi MD5")
    
    with lock_100, lock_101:
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
    """Tải lại lịch sử từ API"""
    # Lấy lịch sử TX
    hist_100, pred_100 = fetch_history_from_api_tx()
    if hist_100:
        history_100 = hist_100
        predict_history_100 = pred_100
        save_history(HISTORY_FILE_100, history_100)
        save_history(PREDICT_FILE_100, predict_history_100)
        if history_100:
            latest_result_100.update(history_100[0])
            save_data(DATA_FILE_100, latest_result_100)
    
    # Lấy lịch sử MD5
    hist_101, pred_101 = fetch_history_from_api_md5()
    if hist_101:
        history_101 = hist_101
        predict_history_101 = pred_101
        save_history(HISTORY_FILE_101, history_101)
        save_history(PREDICT_FILE_101, predict_history_101)
        if history_101:
            latest_result_101.update(history_101[0])
            save_data(DATA_FILE_101, latest_result_101)
    
    # Cập nhật dự đoán
    update_predictions_vip()
    
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
        <title>🎲 HIT VIP - Tài Xỉu</title>
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
                flex-wrap: wrap;
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
            .predict-box .cau-info {
                font-size: 11px;
                color: #4a6a8f;
                margin-top: 4px;
                display: flex;
                flex-wrap: wrap;
                gap: 4px;
            }
            .predict-box .cau-info .tag {
                background: #1a2a3a;
                padding: 2px 8px;
                border-radius: 10px;
                border: 1px solid #2a3a5e;
                font-size: 10px;
                color: #88ccff;
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
                <h1>🎲 HIT VIP Tài Xỉu</h1>
                <div class="admin">👤 Admin: Duy Bảo</div>
                <div class="status" id="status">🟢 Đang kết nối...</div>
                <div class="auto-update">⚡ Tự động cập nhật | 6 cầu phân tích VIP</div>
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
                    <div class="title">🔮 Dự đoán VIP phiên tiếp theo</div>
                    <div class="main" id="dudoan_100">Chưa đủ dữ liệu</div>
                    <div class="sub" id="lydo_100"></div>
                    <div>
                        <span class="strategy" id="chienluoc_100">Chờ dữ liệu</span>
                    </div>
                    <div class="confidence">
                        <span style="font-size:13px;color:#9ca3af;">Độ tin cậy</span>
                        <div class="bar"><div class="fill" id="do_tin_cay_100" style="width:0%"></div></div>
                        <span class="text" id="do_tin_cay_text_100">0%</span>
                    </div>
                    <div class="analyze-count" id="count_100">📊 Đã phân tích: 0 phiên</div>
                    <div class="cau-info" id="cau_info_100"></div>
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
                    <div class="title">🔮 Dự đoán VIP phiên tiếp theo</div>
                    <div class="main" id="dudoan_101">Chưa đủ dữ liệu</div>
                    <div class="sub" id="lydo_101"></div>
                    <div>
                        <span class="strategy" id="chienluoc_101">Chờ dữ liệu</span>
                    </div>
                    <div class="confidence">
                        <span style="font-size:13px;color:#9ca3af;">Độ tin cậy</span>
                        <div class="bar"><div class="fill" id="do_tin_cay_101" style="width:0%"></div></div>
                        <span class="text" id="do_tin_cay_text_101">0%</span>
                    </div>
                    <div class="analyze-count" id="count_101">📊 Đã phân tích: 0 phiên</div>
                    <div class="cau-info" id="cau_info_101"></div>
                </div>
            </div>

            <!-- ENDPOINTS -->
            <div class="card">
                <h2>📡 API Endpoints</h2>
                <div class="endpoints">
                    <div class="item">
                        <span class="method">GET</span>
                        <code>/api/taixiu</code>
                        <span class="desc">Bàn thường + dự đoán VIP</span>
                    </div>
                    <div class="item">
                        <span class="method">GET</span>
                        <code>/api/taixiumd5</code>
                        <span class="desc">Bàn MD5 + dự đoán VIP</span>
                    </div>
                    <div class="item">
                        <span class="method">GET</span>
                        <code>/api/history</code>
                        <span class="desc">Lịch sử (tự động lưu)</span>
                    </div>
                    <div class="item">
                        <span class="method">GET</span>
                        <code>/api/reload_history</code>
                        <span class="desc">Tải lại lịch sử</span>
                    </div>
                </div>
            </div>

            <div class="footer">
                🚀 HIT VIP v5.0 | 6 Cầu phân tích | Duy Bảo Admin
            </div>
        </div>

        <script>
            let currentSession100 = 0;
            let currentSession101 = 0;
            let data100 = {};
            let data101 = {};
            let isUpdating = false;

            async function fetchData() {
                if (isUpdating) return;
                isUpdating = true;

                try {
                    const res100 = await fetch('/api/taixiu');
                    const newData100 = await res100.json();
                    
                    const res101 = await fetch('/api/taixiumd5');
                    const newData101 = await res101.json();

                    const oldPhien100 = data100.Phien || 0;
                    const oldPhien101 = data101.Phien || 0;
                    
                    const hasUpdate100 = newData100.Phien > oldPhien100 && newData100.Phien > 0;
                    const hasUpdate101 = newData101.Phien > oldPhien101 && newData101.Phien > 0;

                    data100 = newData100;
                    data101 = newData101;

                    updateUI(data100, '100', hasUpdate100);
                    updateUI(data101, '101', hasUpdate101);

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

            function updateUI(data, suffix, hasUpdate) {
                const card = document.getElementById('card_' + suffix);
                if (hasUpdate) {
                    card.classList.add('new-update');
                    document.getElementById('indicator_' + suffix).classList.add('show');
                } else {
                    card.classList.remove('new-update');
                    document.getElementById('indicator_' + suffix).classList.remove('show');
                }
                
                const phien = data.Phien || 0;
                document.getElementById('phien_' + suffix).textContent = '#' + (phien || '---');
                
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
                    
                    const box1 = document.getElementById('box1_' + suffix);
                    const box2 = document.getElementById('box2_' + suffix);
                    const box3 = document.getElementById('box3_' + suffix);
                    
                    box1.classList.remove('pop');
                    box2.classList.remove('pop');
                    box3.classList.remove('pop');
                    d1El.classList.remove('pop-number');
                    d2El.classList.remove('pop-number');
                    d3El.classList.remove('pop-number');
                    
                    void box1.offsetWidth;
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
                
                const tong = data.Tong || 0;
                const tongEl = document.getElementById('tong_' + suffix);
                tongEl.textContent = tong;
                if (hasUpdate) {
                    tongEl.classList.remove('pulse');
                    void tongEl.offsetWidth;
                    tongEl.classList.add('pulse');
                }
                
                const ketqua = data.Ket_qua || 'Chưa có';
                const ketquaEl = document.getElementById('ketqua_' + suffix);
                ketquaEl.textContent = ketqua;
                ketquaEl.className = 'value ' + (ketqua === 'Tài' ? 'tai' : ketqua === 'Xỉu' ? 'xiu' : '');
                if (hasUpdate && ketqua !== 'Chưa có') {
                    ketquaEl.classList.remove('pulse');
                    void ketquaEl.offsetWidth;
                    ketquaEl.classList.add('pulse');
                }
                
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
                
                document.getElementById('lydo_' + suffix).textContent = data.Ly_do || '';
                document.getElementById('chienluoc_' + suffix).textContent = data.Chien_luoc || 'Đang phân tích';
                
                const doTinCay = data.Do_tin_cay || 0;
                document.getElementById('do_tin_cay_' + suffix).style.width = doTinCay + '%';
                document.getElementById('do_tin_cay_text_' + suffix).textContent = doTinCay + '%';
                
                const soPhien = data.So_phien_phan_tich || 0;
                document.getElementById('count_' + suffix).textContent = '📊 Đã phân tích: ' + soPhien + ' phiên';
                
                const cauInfo = document.getElementById('cau_info_' + suffix);
                const cacCau = data.Cac_cau_da_phan_tich || [];
                if (cacCau.length > 0) {
                    cauInfo.innerHTML = cacCau.map(c => '<span class="tag">' + c + '</span>').join(' ');
                } else {
                    cauInfo.innerHTML = '<span class="tag">Chưa có dữ liệu</span>';
                }
            }

            function showToast(message) {
                const toast = document.getElementById('toast');
                toast.textContent = message;
                toast.classList.add('show');
                clearTimeout(toast.timeout);
                toast.timeout = setTimeout(() => {
                    toast.classList.remove('show');
                }, 3000);
            }

            async function checkAutoUpdate() {
                try {
                    const res100 = await fetch('/api/check_update?gid=100&current=' + currentSession100);
                    const check100 = await res100.json();
                    
                    const res101 = await fetch('/api/check_update?gid=101&current=' + currentSession101);
                    const check101 = await res101.json();
                    
                    if (check100.has_update || check101.has_update) {
                        fetchData();
                    }
                } catch (e) {}
            }

            fetchData();
            setInterval(fetchData, 5000);
            setInterval(checkAutoUpdate, 2000);
        </script>
    </body>
    </html>
    """

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
    app.run(host=HOST, port=port, debug=False)
