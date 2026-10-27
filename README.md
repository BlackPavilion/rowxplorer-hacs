<p align="center">
  <img src="assets/logo.png" alt="rowxplorer" width="440">
</p>

Custom [Home Assistant](https://www.home-assistant.io/) integration for
**Rowenta X-Plorer 45** robot vacuums (and other Groupe SEB robots on the same
SEB cloud platform). It talks to the SEB IoT cloud (OAuth + Cognito + MQTT over
WSS) — the same verified path used by
[`rowxplorer-lib`](https://github.com/BlackPavilion/rowxplorer-lib), which is
vendored inside the integration.

> **Disclaimer** — This is an unofficial integration, not affiliated with or
> endorsed by Groupe SEB / Rowenta. Use it at your own risk with your own robot
> and account.

## Features

- **Vacuum entity** with start, pause, stop, return to dock, spot clean,
  locate (beep) and suction power.
- **Sensors** for battery, cleaning area, cleaning time, total cleaning time,
  cleaning method, suction power, error and accessory wear (side brush, main
  brush, filter).
- **UI configuration**: sign in with your Rowenta email and password (or paste
  a refresh token), plus reauthentication and options flows.
- **Robot auto-discovery**: the integration lists the robots linked to your SEB
  account and pre-fills the robot ID and product ID.
- **Push updates**: the robot publishes its status over MQTT, so changes show
  up in Home Assistant within seconds. A 60 s poll (configurable) stays as a
  fallback.
- Diagnostics support with the refresh token redacted.

## Requirements

- Home Assistant **2025.2** or newer.
- A Rowenta X-Plorer 45 (or compatible Groupe SEB robot) already paired in the
  official **Rowenta Robots** app.
- The **email and password** of the Rowenta account that owns the robot (or a
  refresh token — see [Authentication](#authentication)). The robot is
  discovered automatically from the account (see
  [Robot discovery](#robot-discovery)).

## Installation

### HACS (recommended)

1. In HACS, open the menu → **Custom repositories**.
2. Add `https://github.com/BlackPavilion/rowxplorer-hacs` with category
   **Integration**.
3. Install **Rowxplorer** and restart Home Assistant.

### Manual

Copy the `custom_components/rowxplorer` directory into your Home Assistant
`config/custom_components/` directory and restart Home Assistant.

## Authentication

During setup the integration signs in to the SEB account with your Rowenta
**email and password**, obtains a long-lived refresh token and stores only that
token. Your password is never saved, and the refresh token is exchanged for
short-lived tokens automatically (it is not rotated, so it stays valid until
the password is changed or the session is revoked).

If your account uses **two-step verification** (or the login endpoints change),
choose **Refresh token** in the first step and paste a token generated with the
`rowxplorer-lib` CLI:

```bash
pip install rowxplorer-lib
rowxplorer-lib login --user you@example.com --password SECRET
```

## Robot discovery

The integration lists the robots linked to your SEB account and **adds them
all automatically** — one config entry per robot, with the robot ID, product
ID and name taken from the account. If the list comes back empty (for example,
your account lives in a different SEB perimeter), the flow falls back to
manual entry. The robot UUID is the `ROBOT_ID` value used by `rowxplorer-lib`
and looks like:

```
01234567-89ab-cdef-0123-456789abcdef
```

## Configuration

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **Rowxplorer**.
3. Choose **Rowenta account (email and password)** and sign in, or choose
   **Refresh token** to paste one manually.
4. Done: every robot linked to the account is added automatically (one entry
   per robot). If no robot is found you enter the details manually instead:
   the **robot ID** (UUID), a name, and (optionally) the product ID, the MQTT
   endpoint and the fallback update interval. The defaults work for the
   X-Plorer 45:
   - Product ID: `VAC001`
   - MQTT endpoint: `prod-new.iot.mqtt.groupe-seb.com`
   - Update interval: 60 s (between 15 and 600 s)

Automatically added robots are not probed during setup: if a robot is offline
(or not reachable over MQTT) its entry simply stays "not ready" until it
answers, and the entities show as unavailable.

Status changes arrive over MQTT as soon as the robot publishes them. The
integration also polls every 60 s as a fallback; the interval is set during
setup and can be changed later from the integration → **Configure**.

## Entities

| Entity | Description |
| --- | --- |
| `vacuum.<name>` | Robot state and commands |
| `sensor.<name>_battery` | Battery level (%) |
| `sensor.<name>_cleaning_area` | Area cleaned in the current/last job (m²) |
| `sensor.<name>_cleaning_time` | Duration of the current/last job |
| `sensor.<name>_total_cleaning_time` | Accumulated cleaning time |
| `sensor.<name>_method` | Last cleaning method |
| `sensor.<name>_power` | Suction power |
| `sensor.<name>_error` | Current error code |
| `sensor.<name>_side_brush` | Remaining side brush life (%) |
| `sensor.<name>_main_brush` | Remaining main brush life (%) |
| `sensor.<name>_filter` | Remaining filter life (%) |

The vacuum supports `start`, `pause`, `stop`, `return_to_base`, `locate`,
`clean_spot` and `set_fan_speed`.

## Troubleshooting

- **`invalid_auth`** — the email/password is wrong or the account uses two-step
  verification (use the **Refresh token** option). If the stored token was
  revoked, Home Assistant asks you to reauthenticate.
- **`cannot_connect`** — check the robot ID, the MQTT endpoint and that the
  robot is online. The integration opens a WebSocket to the SEB cloud; a
  firewall blocking outbound 443 will prevent it from working.
- **Commands seem delayed** — commands are fire-and-forget; the state is
  refreshed right after sending and then on every poll.
- **Enable debug logging**:

  ```yaml
  logger:
    default: warning
    logs:
      custom_components.rowxplorer: debug
  ```

## Development

The `rowxplorer_lib/` package inside the integration is a vendored copy of
[`rowxplorer-lib`](https://github.com/BlackPavilion/rowxplorer-lib). To update
it from a sibling checkout:

```bash
scripts/sync_lib.sh ../rowxplorer-lib
```

The integration itself has no third-party Python requirements: `requests` and
`paho-mqtt` are already provided by Home Assistant.

## License

MIT — see [LICENSE](LICENSE).
