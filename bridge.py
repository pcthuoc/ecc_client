"""
Printer Bridge - Core Bridge Module
"""

import paho.mqtt.client as mqtt
import websocket
import json
import time
import threading
import uuid
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import requests
import hashlib
import os

from config import config, load_config, save_config, GCODE_DIR
from protocol import create_sdcp_message, STATUS_MAP

printer_ws = None
printer_status = {"connected": False, "raw_data": {}, "last_update": 0}
mqtt_client_global = None
bridge_running = False


class PrinterBridge:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🖨️ Printer Bridge")
        self.root.geometry("700x550")
        self.detail_win = None
        self.setup_ui()
        load_config()
        self.load_ui()

    def setup_ui(self):
        main = ttk.Frame(self.root, padding="10")
        main.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main, text="🖨️ Printer Bridge", font=("Arial", 14, "bold")).pack(pady=(0,10))
        
        # Config
        cfg = ttk.LabelFrame(main, text="Cấu hình", padding="8")
        cfg.pack(fill=tk.X, pady=(0,8))
        
        r1 = ttk.Frame(cfg); r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="IP:", width=10).pack(side=tk.LEFT)
        self.ip = ttk.Entry(r1, width=15); self.ip.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(r1, text="Port:").pack(side=tk.LEFT)
        self.port = ttk.Entry(r1, width=6); self.port.pack(side=tk.LEFT, padx=(3,8))
        ttk.Button(r1, text="🔍Test", command=self.test, width=7).pack(side=tk.LEFT)
        ttk.Button(r1, text="📡Lấy ID", command=self.get_id, width=9).pack(side=tk.LEFT, padx=3)
        
        r2 = ttk.Frame(cfg); r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text="Mainboard:", width=10).pack(side=tk.LEFT)
        self.mid = ttk.Entry(r2, width=42); self.mid.pack(side=tk.LEFT)
        
        r3 = ttk.Frame(cfg); r3.pack(fill=tk.X, pady=2)
        ttk.Label(r3, text="MQTT:", width=10).pack(side=tk.LEFT)
        self.mqtt = ttk.Entry(r3, width=15); self.mqtt.pack(side=tk.LEFT, padx=(0,5))
        ttk.Label(r3, text="Port:").pack(side=tk.LEFT)
        self.mqttport = ttk.Entry(r3, width=6); self.mqttport.pack(side=tk.LEFT, padx=(3,8))
        ttk.Button(r3, text="💾Lưu", command=self.save_ui, width=7).pack(side=tk.LEFT)
        
        r4 = ttk.Frame(cfg); r4.pack(fill=tk.X, pady=2)
        ttk.Label(r4, text="API Key:", width=10).pack(side=tk.LEFT)
        self.api = ttk.Entry(r4, width=50); self.api.pack(side=tk.LEFT)
        
        # Status
        st = ttk.Frame(main); st.pack(fill=tk.X, pady=5)
        self.ws_st = ttk.Label(st, text="⚪ WS: --"); self.ws_st.pack(side=tk.LEFT, padx=(0,15))
        self.mqtt_st = ttk.Label(st, text="⚪ MQTT: --"); self.mqtt_st.pack(side=tk.LEFT)
        
        # Buttons
        btn = ttk.Frame(main); btn.pack(fill=tk.X, pady=8)
        self.start_btn = ttk.Button(btn, text="▶️ Khởi động", command=self.start, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=(0,8))
        self.detail_btn = ttk.Button(btn, text="📊 Chi tiết", command=self.start_detail, width=10)
        self.detail_btn.pack(side=tk.LEFT, padx=(0,8))
        self.stop_btn = ttk.Button(btn, text="⏹️ Dừng", command=self.stop, width=8, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        
        # Log
        log = ttk.LabelFrame(main, text="Log", padding="5")
        log.pack(fill=tk.BOTH, expand=True)
        self.log = ScrolledText(log, height=12, font=("Consolas", 9))
        self.log.pack(fill=tk.BOTH, expand=True)

    def log_msg(self, msg, icon="ℹ️"):
        self.log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {icon} {msg}\n")
        self.log.see(tk.END)
        if int(self.log.index('end-1c').split('.')[0]) > 150:
            self.log.delete('1.0', '30.0')

    def load_ui(self):
        self.ip.insert(0, config.get("printer_ip", ""))
        self.port.insert(0, str(config.get("printer_port", 3030)))
        self.mid.insert(0, config.get("mainboard_id", ""))
        self.mqtt.insert(0, config.get("mqtt_broker", ""))
        self.mqttport.insert(0, str(config.get("mqtt_port", 1883)))
        self.api.insert(0, config.get("api_key", ""))

    def save_ui(self):
        config.update({
            "printer_ip": self.ip.get(), 
            "printer_port": int(self.port.get() or 3030),
            "mainboard_id": self.mid.get(), 
            "mqtt_broker": self.mqtt.get(),
            "mqtt_port": int(self.mqttport.get() or 1883), 
            "api_key": self.api.get()
        })
        self.log_msg("Đã lưu" if save_config() else "Lỗi lưu!", "✅" if save_config() else "❌")

    def test(self):
        ip, port = self.ip.get(), self.port.get() or "3030"
        if not ip: return self.log_msg("Chưa nhập IP!", "⚠️")
        self.log_msg(f"Test {ip}:{port}...")
        def t():
            try:
                ws = websocket.create_connection(f"ws://{ip}:{port}/websocket", timeout=5)
                ws.close()
                self.root.after(0, lambda: self.log_msg("OK!", "✅"))
            except Exception as e:
                self.root.after(0, lambda: self.log_msg(f"Lỗi: {e}", "❌"))
        threading.Thread(target=t, daemon=True).start()

    def get_id(self):
        ip, port = self.ip.get(), self.port.get() or "3030"
        if not ip: return self.log_msg("Chưa nhập IP!", "⚠️")
        self.log_msg("Gửi CMD 0...")
        def g():
            try:
                ws = websocket.create_connection(f"ws://{ip}:{port}/websocket", timeout=10)
                ws.send(json.dumps({"Id": str(uuid.uuid4()), "Data": {"Cmd": 0, "Data": {}, 
                    "RequestID": str(uuid.uuid4()), "MainboardID": "", "TimeStamp": int(time.time()), "From": 0}, 
                    "Topic": "sdcp/request/"}))
                ws.settimeout(5)
                while True:
                    r = ws.recv()
                    if r.strip() in ['"pong"', 'pong']: continue
                    d = json.loads(r)
                    mid = d.get("Attributes", {}).get("MainboardID") or d.get("Data", {}).get("MainboardID") or d.get("MainboardID")
                    if mid:
                        ws.close()
                        self.root.after(0, lambda m=mid: [self.mid.delete(0, tk.END), self.mid.insert(0, m), self.log_msg(f"ID: {m}", "✅")])
                        return
            except Exception as e:
                self.root.after(0, lambda: self.log_msg(f"Lỗi: {e}", "❌"))
        threading.Thread(target=g, daemon=True).start()

    def start(self):
        if not self.ip.get() or not self.mid.get() or not self.api.get():
            return self.log_msg("Thiếu config!", "⚠️")
        self.save_ui()
        self._start_bridge()

    def start_detail(self):
        if not self.ip.get() or not self.mid.get() or not self.api.get():
            return self.log_msg("Thiếu config!", "⚠️")
        self.save_ui()
        self._start_bridge()
        self._open_detail()

    def _start_bridge(self):
        global bridge_running
        bridge_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.detail_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log_msg("Khởi động...", "🚀")
        threading.Thread(target=self._connect_ws, daemon=True).start()
        self.root.after(1500, self._connect_mqtt)

    def stop(self):
        global bridge_running, printer_ws, mqtt_client_global
        bridge_running = False
        if mqtt_client_global:
            try: mqtt_client_global.loop_stop(); mqtt_client_global.disconnect()
            except: pass
            mqtt_client_global = None
        if printer_ws:
            try: printer_ws.close()
            except: pass
            printer_ws = None
        printer_status["connected"] = False
        self.ws_st.config(text="⚪ WS: --")
        self.mqtt_st.config(text="⚪ MQTT: --")
        self.start_btn.config(state=tk.NORMAL)
        self.detail_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log_msg("Đã dừng", "⏹️")
        if self.detail_win:
            try: self.detail_win.destroy()
            except: pass
            self.detail_win = None

    def _connect_ws(self):
        global printer_ws
        def on_open(ws):
            printer_status["connected"] = True
            self.root.after(0, lambda: [self.ws_st.config(text="🟢 WS: OK"), self.log_msg("WS OK", "✅")])
        def on_msg(ws, m):
            self._on_ws_msg(m)
        def on_close(ws, c, m):
            printer_status["connected"] = False
            self.root.after(0, lambda: self.ws_st.config(text="🔴 WS: --"))
        def on_err(ws, e):
            self.root.after(0, lambda: self.log_msg(f"WS err: {e}", "❌"))
        printer_ws = websocket.WebSocketApp(f"ws://{config['printer_ip']}:{config['printer_port']}/websocket",
            on_open=on_open, on_message=on_msg, on_close=on_close, on_error=on_err)
        printer_ws.run_forever()

    def _connect_mqtt(self):
        global mqtt_client_global
        def on_conn(c, u, f, rc):
            if rc == 0:
                self.root.after(0, lambda: [self.mqtt_st.config(text="🟢 MQTT: OK"), self.log_msg("MQTT OK", "✅")])
                c.subscribe(f"{config['api_key']}/command/send/{config['mainboard_id']}")
        def on_msg(c, u, m):
            self._on_mqtt_msg(m)
        mqtt_client_global = mqtt.Client()
        mqtt_client_global.username_pw_set(config["api_key"], None)
        mqtt_client_global.on_connect = on_conn
        mqtt_client_global.on_message = on_msg
        try:
            mqtt_client_global.connect(config["mqtt_broker"], config["mqtt_port"], 60)
            mqtt_client_global.loop_start()
            threading.Thread(target=self._main_loop, daemon=True).start()
        except Exception as e:
            self.log_msg(f"MQTT err: {e}", "❌")

    def _on_ws_msg(self, msg):
        try:
            if msg.strip() in ['"pong"', 'pong']: return
            d = json.loads(msg)
            if "Data" in d and "Cmd" in d.get("Data", {}):
                cmd, ack = d["Data"]["Cmd"], d["Data"].get("Data", {}).get("Ack", -1)
                names = {128: "PRINT", 129: "PAUSE", 130: "STOP", 131: "RESUME", 258: "FILES", 403: "CTRL"}
                if cmd in [128, 129, 130, 131, 403]:
                    self.root.after(0, lambda: self.log_msg(f"ACK {names.get(cmd)}: {ack}", "🔔"))
                    self._mqtt_resp(cmd, ack, "OK" if ack == 0 else "FAIL")
                    if self.detail_win: self.root.after(0, lambda: self.d_ack.insert(tk.END, f"{names.get(cmd)}: {ack}\n"))
                    return
                if cmd == 258:
                    fl = d["Data"].get("Data", {}).get("FileList", [])
                    self._mqtt_resp(cmd, ack, sorted(fl, key=lambda x: x.get("CreateTime", 0), reverse=True)[:20])
                    self.root.after(0, lambda: self.log_msg(f"Files: {len(fl)}", "📁"))
                    return
            printer_status["raw_data"] = d
            if self.detail_win: self.root.after(0, lambda: [self.d_raw.delete(1.0, tk.END), self.d_raw.insert(tk.END, json.dumps(d, indent=2)[:1500])])
        except: pass

    def _on_mqtt_msg(self, msg):
        try:
            p = json.loads(msg.payload.decode())
            cmd = p.get("Command", list(p.keys())[0] if p else "?")
            self.root.after(0, lambda: self.log_msg(f"CMD: {cmd}", "📩"))
            if self.detail_win: self.root.after(0, lambda: self.d_cmd.insert(tk.END, f"{cmd}: {str(p)[:100]}\n"))
            if "Command" in p:
                c = p["Command"].lower()
                if c == "pause": self._send_cmd(129, {})
                elif c == "resume": self._send_cmd(131, {})
                elif c == "stop": self._send_cmd(130, {})
                elif c == "get_files": self._send_cmd(258, {"Url": "/local/"})
                elif c == "print": self._print(p)
                elif c == "print_cloud": threading.Thread(target=self._cloud_print, args=(p,), daemon=True).start()
            elif "TempTargetNozzle" in p: self._send_cmd(403, {"TempTargetNozzle": int(p["TempTargetNozzle"])})
            elif "TempTargetHotbed" in p: self._send_cmd(403, {"TempTargetHotbed": int(p["TempTargetHotbed"])})
            elif "TargetFanSpeed" in p: self._send_cmd(403, {"TargetFanSpeed": p["TargetFanSpeed"]})
            elif "LightStatus" in p: self._send_cmd(403, {"LightStatus": p["LightStatus"]})
        except Exception as e:
            self.root.after(0, lambda: self.log_msg(f"CMD err: {e}", "❌"))

    def _send_cmd(self, cmd, data):
        global printer_ws
        if printer_ws and printer_status["connected"]:
            printer_ws.send(json.dumps(create_sdcp_message(cmd, data)))

    def _mqtt_resp(self, cmd, ack, content):
        global mqtt_client_global
        if mqtt_client_global:
            mqtt_client_global.publish(f"{config['api_key']}/response/{config['mainboard_id']}",
                json.dumps({"Cmd": cmd, "Ack": ack, "Content": content, "Time": time.strftime('%Y-%m-%d %H:%M:%S')}))

    def _print(self, p):
        fn = p.get("Filename", "")
        ps = p.get("PlateSide", p.get("PrintPlatformType", 0))
        pt = 0 if (isinstance(ps, str) and ps.upper() == "A") else (1 if isinstance(ps, str) else int(ps))
        tl = int(p.get("Tlp_Switch", p.get("Timelapse", 0)))
        cl = int(p.get("Calibration_switch", p.get("BedLeveling", 0)))
        if fn: self._send_cmd(128, {"Filename": fn, "StartLayer": 0, "PrintPlatformType": pt, "Tlp_Switch": tl, "Calibration_switch": cl})

    def _cloud_print(self, p):
        fn, url = p.get("Filename", ""), p.get("FileUrl", "")
        ps = p.get("PlateSide", p.get("PrintPlatformType", 0))
        pt = 0 if (isinstance(ps, str) and ps.upper() == "A") else (1 if isinstance(ps, str) else int(ps))
        tl, cl = int(p.get("Tlp_Switch", p.get("Timelapse", 0))), int(p.get("Calibration_switch", p.get("BedLeveling", 0)))
        
        # Download
        self.root.after(0, lambda: self.log_msg(f"Download: {fn}", "📥"))
        self._mqtt_resp(1001, 0, {"step": "downloading", "filename": fn})
        try:
            tp = os.path.join(GCODE_DIR, fn)
            r = requests.get(url, stream=True, timeout=300); r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(tp, 'wb') as f:
                for c in r.iter_content(8192):
                    if c: 
                        f.write(c)
                        downloaded += len(c)
                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            if pct % 25 == 0:
                                self._mqtt_resp(1001, 0, {"step": "downloading", "progress": pct, "filename": fn})
            self.root.after(0, lambda: self.log_msg(f"Downloaded: {fn}", "✅"))
        except Exception as e:
            self.root.after(0, lambda: self.log_msg(f"Download err: {e}", "❌"))
            self._mqtt_resp(1001, -1, {"step": "download_failed", "error": str(e)}); return
        
        # Upload
        self.root.after(0, lambda: self.log_msg(f"Upload: {fn}", "📤"))
        self._mqtt_resp(1001, 0, {"step": "uploading", "filename": fn})
        try:
            with open(tp, 'rb') as f: fd = f.read()
            md5 = hashlib.md5(fd).hexdigest()
            uid = uuid.uuid4().hex
            upload_url = f"http://{config['printer_ip']}:{config['printer_port']}/uploadFile/upload"
            off = 0
            while off < len(fd):
                ch = fd[off:off+1048576]
                res = requests.post(upload_url, data={"TotalSize": len(fd), "Uuid": uid, "Offset": str(off), "Check": "1", "S-File-MD5": md5},
                    files={"File": (fn, ch, "application/octet-stream")}, timeout=60).json()
                if not res.get('success'): raise Exception(str(res))
                off += 1048576
            # Xóa file sau khi upload
            try:
                os.remove(tp)
                self.root.after(0, lambda: self.log_msg(f"Deleted: {fn}", "🗑️"))
            except: pass
        except Exception as e:
            self.root.after(0, lambda: self.log_msg(f"Upload err: {e}", "❌"))
            self._mqtt_resp(1001, -2, {"step": "upload_failed", "error": str(e)}); return
        
        # Print
        self._mqtt_resp(1001, 0, {"step": "upload_complete", "filename": fn})
        time.sleep(1)
        pfn = f"/local/{fn}"
        self._send_cmd(128, {"Filename": pfn, "StartLayer": 0, "PrintPlatformType": pt, "Tlp_Switch": tl, "Calibration_switch": cl})
        self._mqtt_resp(1001, 0, {"step": "print_started", "filename": pfn})
        self.root.after(0, lambda: self.log_msg(f"Print: {fn}", "🖨️"))

    def _main_loop(self):
        global bridge_running, mqtt_client_global
        first_send = True
        while bridge_running:
            if printer_status["connected"]:
                try: printer_ws.send(json.dumps(create_sdcp_message(0, {})))
                except: pass
                time.sleep(2)
                if printer_status["raw_data"] and "Status" in printer_status["raw_data"] and mqtt_client_global:
                    s = printer_status["raw_data"]["Status"]
                    pi = s.get("PrintInfo", {})
                    n = s.get("TempOfNozzle", 0)
                    nc, nt = (float(n[1]), float(n[0])) if isinstance(n, list) and len(n) >= 2 else (float(n) if n else 0, float(s.get("TempTargetNozzle", 0)))
                    b = s.get("TempOfHotbed", 0)
                    bc, bt = (float(b[1]), float(b[0])) if isinstance(b, list) and len(b) >= 2 else (float(b) if b else 0, float(s.get("TempTargetHotbed", 0)))
                    
                    status_code = pi.get("Status", 0)
                    if first_send or status_code > 0:
                        fan = s.get("CurrentFanSpeed", {})
                        light = s.get("LightStatus", {})
                        pl = {
                            "device_id": config["mainboard_id"],
                            "device_status": STATUS_MAP.get(status_code, "idle"),
                            "timestamp": int(time.time()),
                            "nozzle_temp_current": round(nc, 1),
                            "nozzle_temp_target": nt,
                            "bed_temp_current": round(bc, 1),
                            "bed_temp_target": bt,
                            "chamber_temp_current": round(float(s.get("TempOfBox", 0)), 1),
                            "chamber_temp_target": float(s.get("TempTargetBox", 0)),
                            "filename": pi.get("Filename", ""),
                            "progress": pi.get("Progress", 0),
                            "current_layer": pi.get("CurrentLayer", 0),
                            "total_layer": pi.get("TotalLayer", 0),
                            "model_fan_speed": fan.get("ModelFan", 0) if isinstance(fan, dict) else 0,
                            "auxiliary_fan_speed": fan.get("AuxiliaryFan", 0) if isinstance(fan, dict) else 0,
                            "box_fan_enabled": 1 if (fan.get("BoxFan", 0) if isinstance(fan, dict) else 0) > 0 else 0,
                            "lighting_enabled": light.get("SecondLight", 0) if isinstance(light, dict) else (1 if light else 0),
                            "first_connect": first_send
                        }
                        topic = f"{config['api_key']}/data/stream/{config['mainboard_id']}"
                        if first_send:
                            self.root.after(0, lambda: self.log_msg("Gửi full data lần đầu", "📡"))
                            first_send = False
                    else:
                        pl = {
                            "device_id": config["mainboard_id"],
                            "device_status": STATUS_MAP.get(status_code, "idle"),
                            "timestamp": int(time.time()),
                            "nozzle_temp_current": round(nc, 1),
                            "nozzle_temp_target": nt,
                            "bed_temp_current": round(bc, 1),
                            "bed_temp_target": bt
                        }
                        topic = f"{config['api_key']}/data/periodic/{config['mainboard_id']}"
                    
                    mqtt_client_global.publish(topic, json.dumps(pl))
                    if self.detail_win: self.root.after(0, lambda: [self.d_mqtt.delete(1.0, tk.END), self.d_mqtt.insert(tk.END, json.dumps(pl, indent=2))])
            time.sleep(config.get("read_interval", 5))

    def _open_detail(self):
        if self.detail_win: return
        self.detail_win = tk.Toplevel(self.root)
        self.detail_win.title("📊 Chi tiết")
        self.detail_win.geometry("800x450")
        self.detail_win.protocol("WM_DELETE_WINDOW", lambda: [self.detail_win.destroy(), setattr(self, 'detail_win', None)])
        m = ttk.Frame(self.detail_win); m.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        f1, f2, f3, f4 = ttk.LabelFrame(m, text="📥 RAW"), ttk.LabelFrame(m, text="📤 MQTT"), ttk.LabelFrame(m, text="📩 CMD"), ttk.LabelFrame(m, text="🔔 ACK")
        f1.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        f2.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        f3.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        f4.grid(row=1, column=1, sticky="nsew", padx=2, pady=2)
        m.grid_rowconfigure(0, weight=1); m.grid_rowconfigure(1, weight=1)
        m.grid_columnconfigure(0, weight=1); m.grid_columnconfigure(1, weight=1)
        self.d_raw = ScrolledText(f1, font=("Consolas", 8)); self.d_raw.pack(fill=tk.BOTH, expand=True)
        self.d_mqtt = ScrolledText(f2, font=("Consolas", 8)); self.d_mqtt.pack(fill=tk.BOTH, expand=True)
        self.d_cmd = ScrolledText(f3, font=("Consolas", 8)); self.d_cmd.pack(fill=tk.BOTH, expand=True)
        self.d_ack = ScrolledText(f4, font=("Consolas", 8)); self.d_ack.pack(fill=tk.BOTH, expand=True)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", lambda: [self.stop() if bridge_running else None, self.root.destroy()])
        self.root.mainloop()
