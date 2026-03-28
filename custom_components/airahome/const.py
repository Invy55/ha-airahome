"""Constants for the Aira Heat Pump integration."""
DOMAIN = "airahome"

# Configuration
CONF_MAC_ADDRESS = "mac_address"
CONF_CLOUD_EMAIL = "cloud_email"
CONF_CLOUD_PASSWORD = "cloud_password"
CONF_CERTIFICATE = "certificate"
CONF_DEVICE_UUID = "device_uuid"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENTRY_ID = "entry_id"
CONF_DURATION_HOURS = "duration_hours"
CONF_END_DATETIME = "end_datetime"
CONF_INTERVAL_WEEKS = "interval_weeks"
CONF_OFFSET = "offset"
CONF_PLAN_NAME = "plan_name"
CONF_START_DATETIME = "start_datetime"
CONF_STRATEGY = "strategy"
CONF_TEMPERATURE = "temperature"
CONF_WEEKDAYS = "weekdays"

# Default values
DEFAULT_SHORT_NAME = "Aira HP"
DEFAULT_NAME = "Aira Heat Pump"
DEFAULT_SCAN_INTERVAL = 30  # seconds - coordinator waits for completion before next cycle
STALE_DATA_THRESHOLD = 600  # seconds (10 minutes) - keep old data if fresher than this

# BLE connection timeouts (increased for poor connectivity scenarios)
BLE_CONNECT_TIMEOUT = 30  # seconds - timeout for establishing BLE connection
BLE_DISCOVERY_TIMEOUT = 20  # seconds - timeout for BLE device discovery

# Attributes
ATTR_MAC_ADDRESS = "mac_address"
ATTR_DEVICE_UUID = "device_uuid"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_MODEL = "model"
ATTR_CONNECTION_TYPE = "connection_type"

# Services
SERVICE_ACTIVATE_HOT_WATER_BOOST = "activate_hot_water_boost"
SERVICE_DEACTIVATE_HOT_WATER_BOOST = "deactivate_hot_water_boost"
SERVICE_ADD_HOT_WATER_TIME_PLAN = "add_hot_water_time_plan"
SERVICE_REMOVE_HOT_WATER_TIME_PLAN = "remove_hot_water_time_plan"
SERVICE_SET_ROOM_OFFSET = "set_room_offset"

STRATEGY_ZONE_SETPOINTS = "zone_setpoints"
STRATEGY_ROOM_TEMP_DELTA = "room_temp_delta"
