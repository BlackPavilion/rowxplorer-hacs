"""Config flow for the Rowenta X-Plorer integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_MQTT_ENDPOINT,
    CONF_NAME,
    CONF_PRODUCT_ID,
    CONF_REFRESH_TOKEN,
    CONF_ROBOT_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_MQTT_ENDPOINT,
    DEFAULT_NAME,
    DEFAULT_PRODUCT_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .rowxplorer_lib import (
    AuthenticationError,
    Device,
    RobotStatus,
    RowxplorerClient,
    SebAuth,
    SebAuthConfig,
    SebMqttConfig,
)
from .rowxplorer_lib.exceptions import (
    ConnectionError as RowxplorerConnectionError,
)

_LOGGER = logging.getLogger(__name__)

# Config flow source for the flows spawned to auto-add the account's robots.
SOURCE_AUTO_ADD = "auto_add"

STEP_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REFRESH_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="username",
            )
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


def _login(username: str, password: str) -> str:
    """Log in to the SEB account and return a long-lived refresh token."""
    tokens = SebAuth(
        SebAuthConfig(user=username, password=password)
    ).login()
    if not tokens.refresh_token:
        raise AuthenticationError(
            "the SEB login did not return a refresh token"
        )
    return tokens.refresh_token


def _validate_token(refresh_token: str) -> None:
    """Check that the refresh token can be exchanged for fresh tokens."""
    SebAuth(SebAuthConfig(refresh_token=refresh_token)).refresh()


def _list_devices(refresh_token: str) -> list[Device]:
    """List the robots paired with the SEB account (device discovery)."""
    auth = SebAuth(SebAuthConfig(refresh_token=refresh_token))
    return RowxplorerClient.seb(auth=auth).list_devices()


def _probe_robot(
    refresh_token: str,
    robot_id: str,
    product_id: str,
    mqtt_endpoint: str,
) -> RobotStatus:
    """Connect to the robot and fetch its status."""
    client = RowxplorerClient.seb(
        auth_config=SebAuthConfig(refresh_token=refresh_token),
        mqtt_config=SebMqttConfig(
            mqtt_endpoint=mqtt_endpoint,
            product_id=product_id,
            robot_id=robot_id,
            client_id="#homeassistant-setup",
            timeout=20.0,
            connect_timeout=20.0,
        ),
    )
    try:
        return client.status()
    finally:
        client.transport.disconnect()


class RowxplorerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup of a Rowenta X-Plorer robot."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._refresh_token: str = ""
        self._username: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose how to authenticate."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["credentials", "token"],
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in with the Rowenta account email and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            try:
                refresh_token = await self.hass.async_add_executor_job(
                    _login, username, password
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except RowxplorerConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - config flow boundary
                _LOGGER.exception("Unexpected error logging in to SEB")
                errors["base"] = "unknown"
            else:
                self._refresh_token = refresh_token
                self._username = username
                return await self.async_step_discover()

        return self.async_show_form(
            step_id="credentials",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            errors=errors,
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an existing SEB refresh token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            refresh_token = user_input[CONF_REFRESH_TOKEN].strip()
            try:
                await self.hass.async_add_executor_job(
                    _validate_token, refresh_token
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except RowxplorerConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - config flow boundary
                _LOGGER.exception("Unexpected error validating the SEB token")
                errors["base"] = "unknown"
            else:
                self._refresh_token = refresh_token
                return await self.async_step_discover()

        return self.async_show_form(
            step_id="token",
            data_schema=STEP_TOKEN_SCHEMA,
            errors=errors,
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add every robot linked to the account, automatically.

        One config entry is created per robot: this flow creates the first
        one and spawns an ``auto_add`` flow for each of the rest. When the
        account has no robots (e.g. a different SEB perimeter) the user
        enters the robot details manually.
        """
        try:
            devices = await self.hass.async_add_executor_job(
                _list_devices, self._refresh_token
            )
        except AuthenticationError:
            # The token was just validated; fall back to manual entry.
            _LOGGER.warning("Device discovery failed; using manual entry")
            return await self.async_step_robot()
        except Exception:  # noqa: BLE001 - config flow boundary
            _LOGGER.exception("Unexpected error listing the account's robots")
            return await self.async_step_robot()

        if not devices:
            # No robots found (e.g. different SEB perimeter): manual entry.
            return await self.async_step_robot()

        first, *rest = devices
        # Spawn one auto-add flow per remaining robot.
        for device in rest:
            try:
                await self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    data=self._device_flow_data(device),
                    context={"source": SOURCE_AUTO_ADD},
                )
            except Exception:  # noqa: BLE001 - config flow boundary
                _LOGGER.exception(
                    "Could not spawn the auto-add flow for %s", device.uuid
                )
        return await self._create_robot_entry(first)

    async def async_step_auto_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a robot discovered in the account (spawned by the main flow)."""
        await self.async_set_unique_id(user_input[CONF_ROBOT_ID])
        self._abort_if_unique_id_configured()
        data = {
            CONF_REFRESH_TOKEN: user_input[CONF_REFRESH_TOKEN],
            CONF_ROBOT_ID: user_input[CONF_ROBOT_ID],
            CONF_PRODUCT_ID: user_input[CONF_PRODUCT_ID],
            CONF_MQTT_ENDPOINT: DEFAULT_MQTT_ENDPOINT,
        }
        if user_input.get(CONF_USERNAME):
            data[CONF_USERNAME] = user_input[CONF_USERNAME]
        return self.async_create_entry(
            title=user_input.get(CONF_NAME) or DEFAULT_NAME,
            data=data,
            options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
        )

    def _device_flow_data(self, device: Device) -> dict[str, Any]:
        """Flow data for a discovered robot (shared by the spawned flows)."""
        return {
            CONF_REFRESH_TOKEN: self._refresh_token,
            CONF_USERNAME: self._username,
            CONF_ROBOT_ID: device.uuid,
            CONF_PRODUCT_ID: device.thing_type or DEFAULT_PRODUCT_ID,
            CONF_NAME: device.name or DEFAULT_NAME,
        }

    async def _create_robot_entry(self, device: Device) -> ConfigFlowResult:
        """Create a config entry for a discovered robot."""
        await self.async_set_unique_id(device.uuid)
        self._abort_if_unique_id_configured()
        data = self._device_flow_data(device)
        data[CONF_MQTT_ENDPOINT] = DEFAULT_MQTT_ENDPOINT
        if not self._username:
            data.pop(CONF_USERNAME, None)
        return self.async_create_entry(
            title=device.name or DEFAULT_NAME,
            data=data,
            options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
        )

    async def async_step_robot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the robot details and verify connectivity."""
        errors: dict[str, str] = {}
        if user_input is not None:
            robot_id = user_input[CONF_ROBOT_ID].strip().lower()
            product_id = user_input[CONF_PRODUCT_ID].strip().upper()
            mqtt_endpoint = (
                user_input[CONF_MQTT_ENDPOINT].strip()
                .removeprefix("https://")
                .removeprefix("wss://")
                .rstrip("/")
            )
            name = user_input[CONF_NAME].strip() or DEFAULT_NAME
            scan_interval = int(user_input[CONF_SCAN_INTERVAL])

            try:
                await self.hass.async_add_executor_job(
                    _probe_robot,
                    self._refresh_token,
                    robot_id,
                    product_id,
                    mqtt_endpoint,
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except RowxplorerConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - config flow boundary
                _LOGGER.exception("Unexpected error connecting to the robot")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(robot_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_REFRESH_TOKEN: self._refresh_token,
                        CONF_ROBOT_ID: robot_id,
                        CONF_PRODUCT_ID: product_id,
                        CONF_MQTT_ENDPOINT: mqtt_endpoint,
                        **(
                            {CONF_USERNAME: self._username}
                            if self._username
                            else {}
                        ),
                    },
                    options={CONF_SCAN_INTERVAL: scan_interval},
                )

        schema: dict[str, Any] = {
            vol.Required(CONF_ROBOT_ID): str,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Optional(CONF_PRODUCT_ID, default=DEFAULT_PRODUCT_ID): str,
            vol.Optional(CONF_MQTT_ENDPOINT, default=DEFAULT_MQTT_ENDPOINT): str,
            vol.Required(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=5,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
        return self.async_show_form(
            step_id="robot",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start the reauthentication flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the Rowenta account credentials again."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            try:
                refresh_token = await self.hass.async_add_executor_job(
                    _login, username, password
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except RowxplorerConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - config flow boundary
                _LOGGER.exception("Unexpected error logging in to SEB")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_USERNAME: username,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_CREDENTIALS_SCHEMA,
                {CONF_USERNAME: entry.data.get(CONF_USERNAME, "")},
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithReload:
        """Return the options flow."""
        return RowxplorerOptionsFlow()


class RowxplorerOptionsFlow(OptionsFlowWithReload):
    """Options for the Rowenta X-Plorer integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the polling interval."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=5,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
