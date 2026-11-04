# Govee Cloud Integration for Home Assistant

This custom integration allows you to connect your Govee devices through the Govee Cloud API to Home Assistant.

## Supported Devices

Currently supported devices:
- H5179 (Temperature and Humidity Sensor)

Other Govee thermo-hygrometers that report temperature and humidity to the Govee cloud
in the same format are added automatically, but have not been tested.

Each device gets these entities:

| Entity | Notes |
| --- | --- |
| Temperature | °C, converted to °F if your Home Assistant uses imperial units |
| Humidity | % |
| Battery | % |
| Upload Rate | Diagnostic: how often the device uploads readings, in minutes |
| Online | Diagnostic binary sensor, disabled by default: Govee's own connectivity flag |

Temperature, humidity and battery become `unavailable` when Govee reports the
device as offline, or when its last readings are older than its upload interval
plus 20% (at least 5 minutes). A sensor that keeps going offline often needs new
batteries.

## Installation

Note: Compatible with Home Assistant 2025.1 and newer.

1. Install using HACS (recommended):
   - Add this repository to HACS as a custom repository
   - Install "Govee Cloud Integration"
   - Restart Home Assistant

2. Manual installation:
   - Copy the `custom_components/govee_cloud` folder to your Home Assistant's `custom_components` directory
   - Restart Home Assistant

## Configuration

1. Go to Home Assistant Settings -> Devices & Services
2. Click "Add Integration"
3. Search for "Govee Cloud"
4. Enter your Govee account email and password

The integration will automatically discover and add your supported Govee devices.

If Govee later rejects your password, Home Assistant asks you to re-enter it.
If Govee rejects the app version the integration identifies itself with, a repair
issue appears under Settings -> Repairs; update the integration when that happens.

## Features

- Automatic device discovery
- Temperature, humidity and battery data, with long-term statistics
- Cloud-based API integration
- No additional hardware required

## Development

```bash
# Unit and integration tests (Python 3.14)
pip install -r requirements_test.txt
pytest

# Run the integration in a real Home Assistant container against your Govee account
GOVEE_EMAIL=you@example.com GOVEE_PASSWORD=... python scripts/smoke_test.py --ha-version 2026.11.0
```

`docker compose up` starts a development Home Assistant on http://localhost:8124 with the
integration mounted from this repository.

## Changelog

### 0.2.0
- Sensors without current readings (device offline, or readings older than the upload interval plus 20%) are now `unavailable` instead of `unknown`
- The staleness margin has a 5-minute minimum, so devices with short upload intervals no longer flap
- Retry setup automatically when Govee or the network is down at startup
- Ask for the password again when Govee rejects it, instead of failing silently
- Show a repair issue when Govee rejects the integration's app version
- The same Govee account can no longer be added twice
- Temperature, humidity and battery have device and state classes: long-term statistics and °F conversion
- Upload Rate is now a diagnostic entity
- **Breaking:** the Online sensor (`sensor.*_online`, `True`/`False`) is replaced by a connectivity binary sensor (`binary_sensor.*_online`, `on`/`off`), still disabled by default
- Devices are registered as physical devices instead of services
- One malformed device on the account no longer breaks updates for all devices
- Unsupported devices are logged once instead of on every update
- Shared HTTP session with a 30 s timeout
- Remove the reference to a hub device that never existed (`via_device`), which Home Assistant reports as deprecated
- Tests, CI (hassfest, HACS validation, pytest) and a Docker smoke test

### 0.1.7
- Fix login: Govee rejected the old app version ("The app version is too low")

### 0.1.6
- Add Upload Rate Sensor to Govee devices

### 0.1.5
- Enable battery sensor by default

### 0.1.4
- Added battery level sensor
- Added online status sensor
- Improved data freshness validation based on device upload rate

### 0.1.3
- Fixed device registration and grouping
- Improved token refresh handling
- Added better error logging

### 0.1.2
- Migrated to config_flow for improved setup experience
- Removed configuration.yaml setup method
- Fixed compatibility with Home Assistant 2025.1

### 0.1.1
- Initial public release
- Support for temperature and humidity sensors
- Cloud-based API integration
- Automatic device discovery

## Support

For bugs and feature requests, please open an issue on GitHub.

## License

This project is licensed under the MIT License.

