import unittest

from nexora.agents.meteorology import (MeteorologyAgent, OpenMeteoProvider, SimulatedWeatherProvider,
                                       WeatherProviderError)


def fake_fetch(calls):
    def fetch(url, params):
        calls.append((url, params))
        if "geocoding" in url:
            if params["name"] == "Atlantis":
                return {}
            return {"results": [{"name": "Madrid", "admin1": "Comunidad de Madrid", "country": "EspaÃ±a",
                                 "latitude": 40.4, "longitude": -3.7}]}
        return {"current": {"time": "2026-11-11T12:00", "temperature_2m": 14.2, "relative_humidity_2m": 71,
                            "weather_code": 61, "wind_speed_10m": 9.5}}
    return fetch


class MeteorologyTests(unittest.TestCase):
    def test_default_is_offline_and_explicitly_simulated(self):
        obs = MeteorologyAgent().get_weather_observation("Madrid")
        self.assertTrue(obs["simulated"])
        self.assertEqual(obs["source"], "simulated")
        self.assertIn("simulados", obs["attribution"])

    def test_open_meteo_provider_parses_and_attributes(self):
        calls = []
        agent = MeteorologyAgent(provider=OpenMeteoProvider(fetch_json=fake_fetch(calls)))
        obs = agent.get_weather_observation("  Madrid ")
        self.assertFalse(obs["simulated"])
        self.assertEqual(obs["location"], "Madrid")
        self.assertEqual(obs["resolved_location"], "Madrid, Comunidad de Madrid, EspaÃ±a")
        self.assertEqual(obs["temp_c"], 14.2)
        self.assertEqual(obs["condition"], "Lluvia ligera")
        self.assertIn("Open-Meteo", obs["attribution"])
        self.assertEqual(calls[1][1]["latitude"], 40.4)
        self.assertIn("weather_code", calls[1][1]["current"])

    def test_unknown_location_and_missing_data(self):
        prov = OpenMeteoProvider(fetch_json=fake_fetch([]))
        with self.assertRaises(WeatherProviderError):
            prov.observe("Atlantis")
        broken = OpenMeteoProvider(fetch_json=lambda u, p: {"results": [{"latitude": 1, "longitude": 2}]} if "geocoding" in u else {})
        with self.assertRaises(WeatherProviderError):
            broken.observe("X")

    def test_unknown_wmo_code_is_reported_not_invented(self):
        def fetch(url, params):
            if "geocoding" in url:
                return {"results": [{"name": "X", "latitude": 0, "longitude": 0}]}
            return {"current": {"temperature_2m": 1, "weather_code": 1234}}
        self.assertEqual(OpenMeteoProvider(fetch_json=fetch).observe("X")["condition"], "CÃ³digo WMO 1234")

    def test_empty_location(self):
        with self.assertRaises(ValueError):
            MeteorologyAgent().get_weather_observation("  ")

    def test_observation_stays_in_meteorology_memory(self):
        agent = MeteorologyAgent(provider=SimulatedWeatherProvider())
        agent.get_weather_observation("Madrid")
        self.assertEqual(agent.memory_keys(), ("last_query_Madrid",))
        self.assertEqual(agent.describe()["provider"], "simulated")


if __name__ == "__main__":
    unittest.main()
