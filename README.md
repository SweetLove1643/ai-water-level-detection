# Water Level Detection

Ứng dụng edge AI đọc camera RTSP, phân đoạn vùng nước bằng YOLO, đo mực nước theo ROI và các mốc calibration, rồi gửi cảnh báo lên VMS qua MQTT.

## Luồng xử lý

1. `main.py` nạp cấu hình, khởi tạo MQTT client và kết nối broker.
2. `src/mqtt_client.py` nhận danh sách camera và AI zones từ MQTT, sau đó tạo worker cho camera.
3. `src/worker.py` đọc RTSP, gọi detector, đo mặt nước và kiểm tra trạng thái cảnh báo.
4. `src/state.py` áp dụng hysteresis và cooldown cho cảnh báo.
5. `src/publisher.py` upload ảnh snapshot (nếu có) và gửi event MQTT.

Calibration ROI và các mốc đo nằm trong `resources/config/water_marks.json`.

## Yêu cầu

- Windows
- Python 3.11 (đã dùng để kiểm thử project)
- Camera RTSP truy cập được
- MQTT broker và thông tin đăng nhập hợp lệ
- Model segmentation 
- File calibration tại `resources/config/water_marks.json`

Model weights, dữ liệu huấn luyện, video local, log và môi trường ảo được nhà phát triển loại khỏi Git. Liên hệ nhà phát triển nếu cần cung cấp thông tin.

## Cài đặt

Mở PowerShell tại thư mục project:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PyTorch là dependency của Ultralytics. Nếu cần GPU/CUDA, cài bản PyTorch phù hợp với máy theo hướng dẫn PyTorch trước khi cài dependencies của project.

Tạo file `.env` tại thư mục gốc. Tối thiểu cần cấu hình:

```dotenv
MQTT_HOST=<broker-host>
MQTT_USER=<mqtt-username>
MQTT_PASS=<mqtt-password>
```

Các biến tùy chọn được đọc trong `src/config.py`:

- `MQTT_PORT` (mặc định `433`)
- `MQTT_PATH` (mặc định `/mqtt`)
- `MQTT_CLIENT_ID`
- `STORAGE_URL`
- `MARGIN_CM`, `COOLDOWN_S`

Lưu ý: ngưỡng cảnh báo được cài đặt từ từ `warn_cm` trong file calibration.

## Chạy ứng dụng

```powershell
.\.venv\Scripts\python.exe main.py
```

Dừng ứng dụng bằng `Ctrl+C`. Log được ghi vào `logs/app.log` và console.

## Cấu trúc chính

```text
main.py                         Điểm khởi chạy
src/config.py                   Cấu hình môi trường
src/config_manager.py           Ánh xạ camera/zones và quản lý worker
src/detector.py                 YOLO water segmentation
src/waterline.py                ROI, calibration và tính mức nước
src/state.py                    Trạng thái cảnh báo, hysteresis, cooldown
src/worker.py                   RTSP camera worker
src/publisher.py                Upload snapshot và publish event
src/mqtt_client.py              MQTT subscriptions và lifecycle
resources/config/water_marks.json
scripts_test/                   Test và công cụ debug
```
