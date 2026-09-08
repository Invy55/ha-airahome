"""Constants for the Aira Heat Pump integration."""
DOMAIN = "airahome"

# Configuration
CONF_MAC_ADDRESS = "mac_address"
CONF_CLOUD_EMAIL = "cloud_email"
CONF_CLOUD_PASSWORD = "cloud_password"
CONF_NUM_ZONES = "num_zones"
CONF_NUM_PHASES = "num_phases"
CONF_CERTIFICATE = "certificate"
CONF_INSTALLATION = "installation"
CONF_DEVICE_UUID = "device_uuid"
CONF_DEVICE_NAME = "device_name"
CONF_SCAN_INTERVAL = "scan_interval"

# Default values
DEFAULT_SHORT_NAME = "Aira HP"
DEFAULT_NAME = "Aira Heat Pump"
DEFAULT_SCAN_INTERVAL = 30  # seconds - coordinator waits for completion before next cycle
DEFAULT_NUM_ZONES = 1
DEFAULT_NUM_PHASES = 3
STALE_DATA_THRESHOLD = 600  # seconds (10 minutes) - keep old data if fresher than this to outlast the full reconnect backoff cycle

# BLE connection timeouts (increased for poor connectivity scenarios)
BLE_CONNECT_TIMEOUT = 30  # seconds - timeout for establishing BLE connection
BLE_DISCOVERY_TIMEOUT = 20  # seconds - timeout for BLE device discovery
BLE_COMMAND_SLEEP = 1.5  # seconds - delay between BLE commands to avoid overwhelming the device
BLE_RECONNECT_BACKOFF = (30, 60, 120, 240)  # seconds to wait after each reconnect attempt before the next

# BLE errors that can indicate a stale GATT cache
CACHE_ERROR_PATTERNS: tuple[str, ...] = (
    "not permitted",
    "write not permitted",
    "read not permitted",
    "invalid handle",
    "attribute not found",
    "status=3",
    "status 3",
    "status=1",
    "status 1",
    "status=0x03",
    "status=0x01",
    "write_not_permitted",
    "invalid_handle",
    "failed to get services",
    "characteristic not found",
    "descriptor not found",
)

# Error code prefixes by protocol source
ERROR_SOURCE_PREFIXES: dict[str, str] = {
    "ccv": "CCV_ERROR_CODE_",
    "aira": "AIRA_ERROR_CODE_",
    "power": "POWER_ERROR_CODE_",
}

# Attributes
ATTR_MAC_ADDRESS = "mac_address"
ATTR_DEVICE_UUID = "device_uuid"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_MODEL = "model"
ATTR_CONNECTION_TYPE = "connection_type"

# Supported device types
SUPPORTED_DEVICE_TYPES = ["heat_pump"]

# Default data structure
DEFAULT_DATA = {
    "state": {},
    "system_check_state": {},
    "connected": False,
    "rssi": None,
}
