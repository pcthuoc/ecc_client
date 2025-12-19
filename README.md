# Printer Bridge

MQTT-WebSocket Bridge cho máy in Elegoo

## Cấu trúc thư mục

```
printer_bridge/
├── main.py          # Entry point
├── bridge.py        # Core bridge logic
├── config.py        # Configuration management
├── protocol.py      # SDCP protocol definitions
├── README.md
└── data/
    ├── config.json  # Saved configuration
    └── gcode/       # Downloaded gcode files (auto-deleted after upload)
```

## Cách sử dụng

```bash
cd printer_bridge
python main.py
```

## Tính năng

- **▶️ Khởi động** - Chạy bridge, log cơ bản
- **📊 Chi tiết** - Chạy bridge + cửa sổ 4 panel debug
- **⏹️ Dừng** - Dừng bridge

## Commands MQTT

| Command | Mô tả |
|---------|-------|
| `print` | In file local |
| `print_cloud` | Tải file từ URL và in |
| `pause` | Tạm dừng |
| `resume` | Tiếp tục |
| `stop` | Dừng in |
| `get_files` | Lấy danh sách file |

## Data flow

1. Lần đầu kết nối → Gửi full data (stream topic)
2. Đang in → Gửi full data (stream topic)  
3. Idle → Gửi data tối giản (periodic topic)
