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

# Supported device types
SUPPORTED_DEVICE_TYPES = ["heat_pump"]