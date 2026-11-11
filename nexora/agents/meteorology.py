"""Agente meteorolÃ³gico.

Proveedores:
  - ``SimulatedWeatherProvider`` (por defecto): datos de demostraciÃ³n, sin red.
    Marcados siempre con ``simulated: True``.
  - ``OpenMeteoProvider``: observaciones reales de Open-Meteo (sin API key).
    Solo se usa si el usuario lo activa (``--live`` o config), porque envÃ­a el
    nombre de la ubicaciÃ³n a un servicio externo.

AtribuciÃ³n: Open-Meteo exige citar la fuente (CC BY 4.0).
AEMET OpenData NO estÃ¡ implementado (requiere API key; irÃ­a en el vault).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional

from nexora.agents.base import BaseAgent

# CÃ³digos WMO de "weather_code" (los que usa Open-Meteo).
WMO_CODES_ES = {
    0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Niebla", 48: "Niebla con escarcha",
    51: "Llovizna ligera", 53: "Llovizna moderada", 55: "Llovizna intensa",
    56: "Llovizna helada ligera", 57: "Llovizna helada intensa",
    61: "Lluvia ligera", 63: "Lluvia moderada", 65: "Lluvia intensa",
    66: "Lluvia helada ligera", 67: "Lluvia helada intensa",
    71: "Nevada ligera", 73: "Nevada moderada", 75: "Nevada intensa", 77: "Granos de nieve",
    80: "Chubascos ligeros", 81: "Chubascos moderados", 82: "Chubascos violentos",
    85: "Chubascos de nieve ligeros", 86: "Chubascos de nieve intensos",
    95: "Tormenta", 96: "Tormenta con granizo ligero", 99: "Tormenta con granizo fuerte",
}


class WeatherProviderError(RuntimeError):
    pass


class SimulatedWeatherProvider:
    name = "simulated"

    def observe(self, location: str) -> Dict[str, Any]:
        return {
            "location": location,
            "resolved_location": location,
            "temp_c": 18.5,
            "humidity_pct": 62,
            "wind_kmh": 11.0,
            "condition": "Parcialmente nublado",
            "observed_at": None,
            "source": "simulated",
            "simulated": True,
            "attribution": "Datos simulados de demostraciÃ³n; no son observaciones reales.",
        }


def _fetch_json(url: str, params: dict, timeout: float) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": "NEXORA-OS/0.2"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise WeatherProviderError(f"Fallo de red o respuesta invÃ¡lida: {exc}") from exc


class OpenMeteoProvider:
    name = "open-meteo"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
    CURRENT_VARS = "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"

    def __init__(self, fetch_json: Optional[Callable[[str, dict], dict]] = None, timeout: float = 10.0):
        self._fetch = fetch_json or (lambda url, params: _fetch_json(url, params, timeout))

    def observe(self, location: str) -> Dict[str, Any]:
        geo = self._fetch(self.GEOCODING_URL, {"name": location, "count": 1, "language": "es", "format": "json"})
        results = geo.get("results") or []
        if not results:
            raise WeatherProviderError(f"UbicaciÃ³n no encontrada: {location}")
        place = results[0]

        data = self._fetch(
            self.FORECAST_URL,
            {"latitude": place["latitude"], "longitude": place["longitude"], "current": self.CURRENT_VARS},
        )
        cur = data.get("current")
        if not cur or "temperature_2m" not in cur:
            raise WeatherProviderError("Open-Meteo no devolviÃ³ condiciones actuales")

        resolved = ", ".join(p for p in (place.get("name"), place.get("admin1"), place.get("country")) if p)
        code = cur.get("weather_code")
        return {
            "location": location,
            "resolved_location": resolved or location,
            "temp_c": cur["temperature_2m"],
            "humidity_pct": cur.get("relative_humidity_2m"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "condition": WMO_CODES_ES.get(code, f"CÃ³digo WMO {code}"),
            "observed_at": cur.get("time"),
            "source": "Open-Meteo",
            "simulated": False,
            "attribution": self.ATTRIBUTION,
        }


class MeteorologyAgent(BaseAgent):
    status = "basic"

    def __init__(self, engine=None, provider=None):
        super().__init__(
            name="MeteorologyAgent",
            mode="meteorology",
            engine=engine,
            system_context="Modo MeteorologÃ­a Aislado",
        )
        self.provider = provider or SimulatedWeatherProvider()

    def get_weather_observation(self, location: str) -> Dict[str, Any]:
        """ObservaciÃ³n con fuente y atribuciÃ³n explÃ­citas; se guarda solo en la memoria de este modo."""
        if not isinstance(location, str) or not location.strip():
            raise ValueError("La ubicaciÃ³n no puede estar vacÃ­a")
        location = location.strip()
        obs = self.provider.observe(location)
        self.remember(f"last_query_{location}", obs)
        return obs

    def describe(self) -> dict:
        info = super().describe()
        info["provider"] = self.provider.name
        return info
