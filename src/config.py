# đọc .env (ngưỡng, cooldown, margin...)
import os

from dotenv import load_dotenv

load_dotenv()

MODULE = "WATER_LEVEL_DETECTION"
ZONE_ID = 51
ORG_ID = 103

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.getenv("MQTT_PORT", "433"))
MQTT_PATH = os.getenv("MQTT_PATH", "/mqtt")
MQTT_USER = os.environ["MQTT_USER"]
MQTT_PASS = os.environ["MQTT_PASS"]
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "tts_quan_01")

STORAGE_URL = os.getenv("STORAGE_URL", "https://aioc-stg.atin.vn/storage/upload/file")

MARGIN_CM = float(os.getenv("MARGIN_CM", "5"))
COOLDOWN_S = float(os.getenv("COOLDOWN_S", "300"))

WEIGHT_WATER_MODEL_SEGMENT_PATH=os.getenv("WEIGHT_WATER_MODEL_SEGMENT_PATH")
WATER_MODEL_SEGMENT_CONFIDENCE=os.getenv("WATER_MODEL_SEGMENT_CONFIDENCE")