import sys
sys.path.append("src")

import cv2  # chỉ để tạo ảnh giả
import numpy as np
from src.mqtt_client import build_client
from src.publisher import publish_event
import src.config as cf

CAM_ID = "4f0cc528-d215-4b3c-9727-1b68bacadacd"
CAM_CODE = "TTS_CAM_01"

client = build_client()
client.connect(cf.MQTT_HOST, cf.MQTT_PORT, keepalive=30)  # cần import config
client.loop_start()

jpg = cv2.imencode(
    ".jpg",
    np.full((480, 640, 3), (0, 255, 0), dtype=np.uint8)
)[1].tobytes()
publish_event(client, CAM_ID, CAM_CODE, level_cm=45.0, confidence=0.9,
              zone_name="Test", jpg=jpg)

client.loop_stop()
client.disconnect()