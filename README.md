# Water Level Detection

Hệ thống AI giám sát mực nước từ camera RTSP. Ứng dụng phân đoạn vùng nước, đo mặt nước theo ROI và các mốc calibration của camera, sau đó gửi cảnh báo lên VMS qua MQTT.

## Tổng quan sản phẩm

### Bài toán

Quan sát mực nước bằng mắt thường hoặc kiểm tra camera định kỳ có thể khiến cảnh báo đến muộn, đặc biệt khi cần theo dõi liên tục. Dự án hướng tới tự động hóa việc nhận biết mực nước tại khu vực đã hiệu chuẩn và chuyển kết quả thành sự kiện để hệ thống VMS tiếp nhận.

### Giá trị hướng tới

- Theo dõi luồng video liên tục thay vì chỉ kiểm tra ảnh chụp rời rạc.
- Xác định mức nước theo ROI và thước mốc được hiệu chuẩn riêng cho góc nhìn camera.
- Hạn chế cảnh báo chập chờn bằng hysteresis và cooldown.
- Kết nối với VMS qua MQTT và có thể đính kèm ảnh snapshot.
- Tách pipeline thành các phần detector, đo mức, quản lý trạng thái và publisher để thuận tiện kiểm thử, debug và mở rộng.

Đây là mục tiêu thiết kế của prototype; hiệu quả vận hành thực tế cần được xác nhận bằng thử nghiệm tại hiện trường.

### Đóng góp kỹ thuật trong dự án

Phần triển khai của project kết hợp các thành phần sau thành một pipeline giám sát:

1. Nhận cấu hình camera và AI zones qua MQTT.
2. Đọc RTSP riêng cho từng camera worker.
3. Dùng YOLO segmentation để tạo water mask.
4. Giới hạn phép đo trong ROI và xác định mặt nước quanh vị trí đo đã cấu hình.
5. Ánh xạ mặt nước với các mốc calibration, áp dụng ngưỡng cảnh báo, hysteresis và cooldown.
6. Gửi event MQTT và upload snapshot khi có ảnh.

Mô hình YOLO, thư viện, dữ liệu và các tài nguyên huấn luyện có nguồn gốc/điều khoản riêng; không mặc định chúng là nội dung do dự án tự tạo. README này không tuyên bố mô hình được huấn luyện từ đầu hoặc có độ chính xác cụ thể.

### Trạng thái và giới hạn

Project hiện ở giai đoạn prototype/thử nghiệm tích hợp. Chưa có benchmark định lượng về độ chính xác, độ trễ, tỷ lệ cảnh báo sai hoặc hiệu năng đa camera; không nên xem các chỉ số này là đã được bảo đảm.

Kết quả phụ thuộc vào góc đặt camera, chất lượng hình ảnh, điều kiện ánh sáng, chất lượng segmentation và việc hiệu chuẩn ROI/mốc đo. Mỗi camera cần calibration phù hợp. Mất tín hiệu đo không nên được diễn giải như mực nước đã giảm. Trước khi triển khai thực tế, cần kiểm tra đầy đủ camera, broker, Storage, cấu hình zone và xử lý sự cố tại môi trường đích.

## Sở hữu trí tuệ và giấy phép

### Tác giả và mục tiêu cấp phép

- Tác giả dự án: [SweetLove1643](https://github.com/SweetLove1643).
- Mục tiêu: công khai mã nguồn và, khi đã xác minh quyền phân phối, dữ liệu cùng model weights để mọi người có thể sử dụng, nghiên cứu, chỉnh sửa và chia sẻ theo các license tương ứng.
- Khi sử dụng hoặc phân phối lại phần do dự án tạo ra, vui lòng giữ lại thông tin ghi công tác giả và các thông báo bản quyền/license hiện hành.
- Ghi công tác giả gốc không đồng nghĩa tác giả phải là người duy nhất được ghi nhận: người đóng góp có thể và nên được ghi nhận cho phần họ tạo ra. Không được nhận phần đóng góp của người khác là của mình.

Weights và phần lớn dữ liệu local hiện không được đưa vào Git. Chúng chưa có liên kết tải công khai trong repository; không nên hiểu mô tả mục tiêu là các tài nguyên đó đã sẵn sàng để tải hoặc được cấp quyền phân phối.

### Thành phần bên thứ ba


| Thành phần | Vai trò | Dự án / license upstream |
|---|---|---|
| Ultralytics | YOLO segmentation và model tooling | [Project](https://github.com/ultralytics/ultralytics) · [Licensing](https://www.ultralytics.com/license) |
| OpenCV | Đọc video, xử lý mask và mã hóa snapshot | [Project](https://github.com/opencv/opencv) · [License](https://github.com/opencv/opencv/blob/4.x/LICENSE) |
| Paho MQTT Python | MQTT client | [Project](https://github.com/eclipse-paho/paho.mqtt.python) · [License](https://github.com/eclipse-paho/paho.mqtt.python/blob/master/LICENSE) |
| NumPy | Xử lý mảng và mask | [Project](https://github.com/numpy/numpy) · [License](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |
| Requests | Gửi ảnh lên Storage API | [Project](https://github.com/psf/requests) · [License](https://github.com/psf/requests/blob/main/LICENSE) |
| python-dotenv | Nạp cấu hình môi trường | [Project](https://github.com/theskumar/python-dotenv) · [License](https://github.com/theskumar/python-dotenv/blob/main/LICENSE) |
| PyTorch | Backend ML được Ultralytics sử dụng | [Project](https://github.com/pytorch/pytorch) · [License](https://github.com/pytorch/pytorch/blob/main/LICENSE) |

Model nền, weights được fine-tune, dataset và tài liệu của bên thứ ba có thể có điều khoản riêng, độc lập với license của source code project. Đặc biệt, hãy đọc điều khoản Ultralytics và xác minh quyền sử dụng/phân phối đối với model trước khi phát hành. Bảng này là danh sách tham khảo, không phải kết luận pháp lý về khả năng tương thích license.

## Luồng xử lý

1. `main.py` nạp cấu hình, khởi tạo MQTT client và kết nối broker.
2. `src/mqtt_client.py` nhận danh sách camera và AI zones từ MQTT, sau đó tạo worker cho camera.
3. `src/worker.py` đọc RTSP, gọi detector, đo mặt nước và kiểm tra trạng thái cảnh báo.
4. `src/state.py` áp dụng hysteresis và cooldown cho cảnh báo.
5. `src/publisher.py` upload ảnh snapshot (nếu có) và gửi event MQTT.

Calibration ROI, vị trí đo, ngưỡng cảnh báo và các mốc đo nằm trong `resources/config/water_marks.json`.

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
