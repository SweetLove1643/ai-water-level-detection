# Bước 1: kết nối, reconnect, subscribe
import json
import logging
import ssl
import threading

import paho.mqtt.client as mqtt

from src.publisher import publish_event

from src import config
from src.config_manager import ConfigManager, CameraConfig
from src.worker import CameraWorker

log = logging.getLogger("mqtt_client")

TOPIC_CAMERAS = f"smart_vms/cameras/zone/{config.ZONE_ID}"
TOPIC_ZONES = f"smart_vms/cameras/+/ai_zones/{config.MODULE}"
TOPIC_GETDEVICE = "smart_vms/cameras/getdevice"

workers: dict[str, CameraWorker] = {}
workers_lock = threading.Lock()

mqtt_client: mqtt.Client | None = None

def on_start(
    camera: CameraConfig,
    zones: list[dict[str, object]],
) -> None:
    with workers_lock:
        existing = workers.get(camera.code)

        if existing is not None:
            log.warning("Worker camera=%s đã tồn tại; cập nhật vùng", camera.code)
            existing.update_zones(zones)
            return

        client = mqtt_client
        if client is None:
            raise RuntimeError("MQTT client chưa được khởi tạo")

        def send_alert(level_cm: float, jpg: bytes) -> bool:
            return publish_event(
                client=client,
                cam_id=camera.id,
                cam_code=camera.code,
                level_cm=level_cm,
                jpg=jpg,
            )

        worker = CameraWorker(
            camera=camera,
            zones=zones,
            publish_alert=send_alert,
        )
        workers[camera.code] = worker

        try:
            worker.start()
        except Exception:
            workers.pop(camera.code, None)
            raise

    log.info("START camera=%s zones=%d", camera.code, len(zones))


def on_stop(code: str) -> None:
    with workers_lock:
        worker = workers.pop(code, None)

    if worker is None:
        log.warning("Không tìm thấy worker camera=%s để dừng", code)
        return

    worker.stop()
    log.info("STOP camera=%s", code)


def on_update(
    code: str,
    zones: list[dict[str, object]],
) -> None:
    with workers_lock:
        worker = workers.get(code)

    if worker is None:
        log.warning("Không tìm thấy worker camera=%s để cập nhật vùng", code)
        return

    worker.update_zones(zones)
    log.info("UPDATE camera=%s zones=%d", code, len(zones))

cfg = ConfigManager(on_start, on_stop, on_update)

def build_client() -> mqtt.Client:
    global mqtt_client

    c = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=config.MQTT_CLIENT_ID,
        transport="websockets",
    )
    c.ws_set_options(path=config.MQTT_PATH)
    c.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    c.username_pw_set(config.MQTT_USER, config.MQTT_PASS)
    c.reconnect_delay_set(min_delay=1, max_delay=30)

    def on_connect(client, userdata, flags, reason_code, properties=None):
        log.info("Connected: %s", reason_code)
        if reason_code != 0:
            log.error("Kết nối thất bại (%s)", reason_code)
            client.disconnect()
            return

        rc, mid = client.subscribe([(TOPIC_CAMERAS, 1), (TOPIC_ZONES, 1)], qos=1)
        if rc == 0:
            log.info("Send Subscribe sucessfull!, mid=%s, topics=%s", mid, [TOPIC_CAMERAS, TOPIC_ZONES])
        client.publish(
            TOPIC_GETDEVICE,
            json.dumps({
                "zone_id": config.ZONE_ID,
                "organization_id": config.ORG_ID,
                
            }),
            qos=1
        )

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        log.warning("Disconnected: %s (paho sẽ tự reconnect)", reason_code)

    def on_message(client, userdata, msg):
        try:
            log.info(
                "MQTT RX topic=%s qos=%s retained=%s bytes=%d",
                msg.topic,
                msg.qos,
                msg.retain,
                len(msg.payload),
            )
            print("Debug payload =%s", type(msg))

            if msg.topic == TOPIC_CAMERAS:
                cfg.handle_cameras(msg.payload)
            elif msg.topic.endswith(f"/ai_zones/{config.MODULE}"):
                cfg.handle_zones(msg.topic.split("/")[2], msg.payload)
        except Exception:
            log.exception("lỗi xử lý %s", msg.topic)

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        log.info("Subscribe sucessfull!. mid=%s", mid)

    c.on_subscribe = on_subscribe
    c.on_connect = on_connect
    c.on_disconnect = on_disconnect
    c.on_message = on_message

    mqtt_client = c
    return c