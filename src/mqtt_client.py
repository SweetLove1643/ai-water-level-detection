# Bước 1: kết nối, reconnect, subscribe
import json
import logging
import ssl
import threading

import paho.mqtt.client as mqtt

from src.publisher import publish_bbox, publish_event
from src import config
from src.config_manager import ConfigManager, CameraConfig
from src.worker import CameraWorker

log = logging.getLogger("mqtt_client")

TOPIC_CAMERAS = f"smart_vms/cameras/zone/{config.ZONE_ID}"
TOPIC_GETDEVICE = "smart_vms/cameras/getdevice"

workers: dict[str, CameraWorker] = {}
workers_lock = threading.Lock()

mqtt_client: mqtt.Client | None = None

def on_start(
    camera: CameraConfig,
) -> None:
    with workers_lock:
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
        
        def send_bbox(
            detections: list[dict[str, object]],
            hud_text: str,
        ) -> bool:
            publish_bbox(
                client=client,
                cam_id=camera.id,
                cam_code=camera.code,
                detections=detections,
                hud_text=hud_text,
            )

        worker = CameraWorker(
            camera=camera,
            publish_alert=send_alert,
            publish_bbox=send_bbox,
        )
        workers[camera.code] = worker

        try:
            worker.start()
        except Exception:
            workers.pop(camera.code, None)
            raise

    log.info("STARTED: %s", camera.code)


def on_stop(code: str) -> None:
    with workers_lock:
        worker = workers.pop(code, None)

    if worker is None:
        log.warning("Không tìm thấy worker camera=%s để dừng", code)
        return

    worker.stop()
    log.info("STOP camera=%s", code)

cfg = ConfigManager(on_start, on_stop)

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
            log.error("Failed connect: (%s)", reason_code)
            client.disconnect()
            return

        rc, mid = client.subscribe(TOPIC_CAMERAS, qos=1)
        if rc == 0:
            log.info("Send Subscribe sucessfull!, mid=%s, topics=%s", mid, TOPIC_CAMERAS)
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
                "MQTT topic=%s qos=%s retained=%s bytes=%d",
                msg.topic,
                msg.qos,
                msg.retain,
                len(msg.payload),
            )

            if msg.topic == TOPIC_CAMERAS:
                cfg.handle_cameras(msg.payload)
            else:
                log.warning("TOPIC_CAMERAS not found")

        except Exception:
            log.exception("Processing error: %s", msg.topic)

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        log.info("Subscribe sucessfull!. mid=%s", mid)

    c.on_subscribe = on_subscribe
    c.on_connect = on_connect
    c.on_disconnect = on_disconnect
    c.on_message = on_message

    mqtt_client = c
    return c