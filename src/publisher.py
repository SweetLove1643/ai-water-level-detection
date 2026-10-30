# Bước 6: upload ảnh, publish event + bbox
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import requests
import src.config as cf

log = logging.getLogger("publisher")
TZ = timezone(timedelta(hours=7))

def upload_snapshot(jpg: bytes, camera_id: str) -> str | None:
    try:
        r = requests.post(
            cf.STORAGE_URL,
            files={
                "file": ("snap.jpg", jpg, "image/jpeg")
            },
            data={
                "camera_id": camera_id,
                "category": "anomaly" 
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("object_key")
    except Exception:
        log.exception("upload ảnh lỗi camera=%s", camera_id)
        return None

def publish_event(client, 
                  cam_id: str, 
                  cam_code: str, 
                  level_cm: float,
                  confidence: float | None = None,
                  zone_name: str | None = None, 
                  jpg: bytes | None = None) -> bool:
    object_key = upload_snapshot(jpg, cam_id) if jpg else None
    event = {
        "ai_modules": cf.MODULE,
        "submodule_code": cf.MODULE,
        "camera_id": cam_id,
        "camera_code": cam_code,
        "event_time": datetime.now(TZ).isoformat(timespec="seconds"),
        "entity_type": "WATER_LEVEL",
        "severity": "MEDIUM",
        "payload": {
            "type": "WATER_LEVEL_ALERT",
            "water_level": round(level_cm, 1),
            "unit": "cm",
        },
    }
    if confidence is not None:
        event["confidence"] = round(confidence, 3)
    if zone_name:
        event["payload"]["zone_name"] = zone_name
    if object_key:
        event["snapshot_url"] = object_key

    topic = f"smart_vms/ai_events/{cf.MODULE}"

    try:
        info = client.publish(topic, json.dumps(event), qos=1)

        if info.rc != 0:
            log.error(
                "MQTT publish failed camera=%s topic=%s rc=%s",
                cam_code,
                topic,
                info.rc,
            )
            return False

        info.wait_for_publish(timeout=5)

        if not info.is_published():
            log.error("MQTT publish timeout camera=%s topic=%s", cam_code, topic)
            return False

        log.info(
            "MQTT event sent camera=%s topic=%s object_key=%s",
            cam_code,
            topic,
            object_key,
        )
        return True

    except Exception:
        log.exception("MQTT publish exception camera=%s topic=%s", cam_code, topic)
        return False

def publish_bbox(client, cam_id: str, cam_code: str,
                 detections: list[dict], hud_text: str) -> None:
    """QoS 0, toạ độ bbox chuẩn hoá 0..1, gửi liên tục theo frame."""
    topic = f"smart_vms/ai/bbox/{cam_code}"
    msg = {
        "camera_code": cam_code,
        "camera_id": cam_id,
        "ai_modules": cf.MODULE,
        "timestamp": time.time(),
        "detections": detections,
        "hud": {
            "text": hud_text,
            "display_ms": 1000,
            "color": "#22c55e",
        },
    }
    
    try:
        info = client.publish(topic, json.dumps(msg), qos=0)
        if info.rc != 0:
            log.warning(
                "BBox publish rejected camera=%s topic=%s rc=%s",
                cam_code,
                topic,
                info.rc,
            )
            return False
        return True
    except Exception:
        log.exception("BBox publish exception camera=%s topic=%s", cam_code, topic)
        return False

