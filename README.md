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

Add the following to your `configuration.yaml`:

```yaml
sensor:
  - platform: govee_cloud
    email: "your-email@example.com"
    password: "your-password"
```

Replace `your-email@example.com` and `your-password` with your Govee account credentials.

## Features

- Automatic device discovery
- Real-time temperature and humidity data
- Cloud-based API integration
- No additional hardware required

## Changelog

### 0.1.2
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

