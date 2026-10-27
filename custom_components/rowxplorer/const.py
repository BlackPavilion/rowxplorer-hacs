"""Constants for the Rowenta X-Plorer integration."""

from __future__ import annotations

from typing import Final

from homeassistant.components.vacuum import VacuumActivity

DOMAIN: Final = "rowxplorer"

DEFAULT_NAME: Final = "Rowxplorer"
DEFAULT_MQTT_ENDPOINT: Final = "prod-new.iot.mqtt.groupe-seb.com"
DEFAULT_PRODUCT_ID: Final = "VAC001"
DEFAULT_SCAN_INTERVAL: Final = 60
MIN_SCAN_INTERVAL: Final = 15
MAX_SCAN_INTERVAL: Final = 600

CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_ROBOT_ID: Final = "robot_id"
CONF_PRODUCT_ID: Final = "product_id"
CONF_MQTT_ENDPOINT: Final = "mqtt_endpoint"
CONF_NAME: Final = "name"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_DEVICE: Final = "device"

# Suction power values used by the SEB cloud.
FAN_SPEED_SILENT: Final = "silent"
FAN_SPEED_NORMAL: Final = "normal"
FAN_SPEED_STRONG: Final = "strong"
FAN_SPEEDS: Final = [FAN_SPEED_SILENT, FAN_SPEED_NORMAL, FAN_SPEED_STRONG]

# Cleaning methods reported by the robot (``SebCleaningMethod`` in the app).
CLEANING_METHODS: Final = [
    "auto_cleaning",
    "back_to_dock",
    "charge_go",
    "left_bow",
    "left_spiral",
    "mop",
    "partial_bow",
    "pause",
    "random",
    "right_bow",
    "right_spiral",
    "schedule_clean",
    "sleep",
    "small_room_clean",
    "smart",
    "spiral",
    "wall_follow",
]

# Error codes reported by the robot (``SebErrorCode`` in the app).
ERROR_CODES: Final = [
    "normal",
    "left_side_brush_error",
    "right_side_brush_error",
    "main_brush_error",
    "left_wheel_error",
    "right_wheel_error",
    "fan_motor_error",
    "cliff_sensor_error",
    "off_ground_error",
    "bumper_error",
    "charging_error",
    "wall_sensor_error",
    "dustbin_error",
    "front_wheel_error",
    "no_battery_error",
    "low_battery_error",
]

# Accessories reported in the status payload, mapped to a stable sensor key.
ACCESSORIES: Final = {
    "SIDE-BRUSH": "side_brush",
    "MAIN-BRUSH": "main_brush",
    "FILTER": "filter",
}

PRODUCT_MODELS: Final = {
    "VAC001": "X-Plorer 45",
}

# Robot ``status`` -> Home Assistant vacuum activity.
STATUS_TO_ACTIVITY: Final = {
    "CLEANING": VacuumActivity.CLEANING,
    "CHARGING": VacuumActivity.DOCKED,
    "DOCKING": VacuumActivity.RETURNING,
    "STANDBY": VacuumActivity.IDLE,
    "STOP": VacuumActivity.PAUSED,
    "UPGRADING": VacuumActivity.IDLE,
    "ERROR": VacuumActivity.ERROR,
}
