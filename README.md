# Govee Cloud Integration for Home Assistant

This custom integration allows you to connect your Govee devices through the Govee Cloud API to Home Assistant.

## Supported Devices

Currently supported devices:
- H5179 (Temperature and Humidity Sensor)

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

## Features

- Automatic device discovery
- Real-time temperature and humidity data
- Cloud-based API integration
- No additional hardware required

## Changelog

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

