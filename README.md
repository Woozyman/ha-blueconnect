# Blue Connect for Home Assistant

Home Assistant custom integration for Blue Connect pool monitors.

## Features

- UI-based setup flow with secure config entry storage
- Automatic sensors for temperature, pH, ORP, salinity, last measurement, and overall status
- Automatic binary sensors for pH, ORP, and temperature health checks
- Device registry support
- Diagnostics support with credential redaction
- Reauthentication support when credentials expire
- HACS-ready repository metadata

## Installation

### HACS

1. Add this repository as a custom repository in HACS:
   - `https://github.com/Woozyman/ha-blueconnect`
   - Category: `Integration`
2. Install the integration and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for **Blue Connect**.
5. Enter your:
   - Blue Connect email
   - Blue Connect password
   - Blue Connect Blue Key

## Entities

### Sensors

- `sensor.blue_connect_temperature`
- `sensor.blue_connect_ph`
- `sensor.blue_connect_orp`
- `sensor.blue_connect_salinity`
- `sensor.blue_connect_last_measurement`
- `sensor.blue_connect_status`

### Binary Sensors

- `binary_sensor.blue_connect_ph_ok`
- `binary_sensor.blue_connect_orp_ok`
- `binary_sensor.blue_connect_temperature_ok`

The status sensor exposes the raw Blue Connect status array as an attribute and reports the first non-OK status, or `OK` when all statuses are healthy.

## Example Lovelace cards

### Entities card

```yaml
type: entities
title: Pool Status
entities:
  - sensor.blue_connect_temperature
  - sensor.blue_connect_ph
  - sensor.blue_connect_orp
  - sensor.blue_connect_salinity
  - sensor.blue_connect_last_measurement
  - sensor.blue_connect_status
```

### Glance card

```yaml
type: glance
title: Blue Connect
entities:
  - entity: sensor.blue_connect_temperature
  - entity: sensor.blue_connect_ph
  - entity: sensor.blue_connect_orp
  - entity: sensor.blue_connect_salinity
```

## Publishing through HACS

To be discoverable in HACS search without adding a custom repository:

1. Publish the repository on GitHub.
2. Keep `hacs.json` in the repository root.
3. Add repository topics such as `home-assistant`, `home-assistant-integration`, `hacs`, `blueconnect`, and `pool-monitor`.
4. Submit the repository to the HACS default list after it is ready.

## This plugins reference is to RiiotLabs own API docs, find repo here:
Uses `https://github.com/RiiotLabs/Blue-backend-automation`