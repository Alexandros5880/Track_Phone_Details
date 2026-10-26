import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner
from main import main, analyze_number, map_server, show_map


class PhoneTests(unittest.TestCase):
    def test_greek_number_only(self):
        result = analyze_number("6975954890")
        self.assertEqual(result["number"], "+306975954890")
        self.assertEqual(result["region"], "GR")

    def test_international_overrides_region(self):
        self.assertEqual(analyze_number("00442083661177")["region"], "GB")

    def test_invalid_and_missing_input(self):
        for arguments in [[], ["--number", "123"], ["--number", "hello"],
                          ["--number", "6975954890", "--region", "XX"]]:
            self.assertEqual(CliRunner().invoke(main, arguments).exit_code, 2)

    def test_default_does_not_call_services(self):
        with patch("main.enrich_twilio") as twilio, patch("main.create_map") as mapper:
            result = CliRunner().invoke(main, ["--number", "6975954890", "--json"])
            self.assertEqual(result.exit_code, 0, result.output)
            twilio.assert_not_called()
            mapper.assert_not_called()

    def test_map_network_failure_preserves_results(self):
        from requests.exceptions import ConnectionError
        with patch.dict(os.environ, {"OPENCAGE_API_KEY": "test"}):
            with patch("opencage.geocoder.OpenCageGeocode.geocode", side_effect=ConnectionError()):
                result = CliRunner().invoke(main, ["--number", "6975954890", "--map", "unused.html"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn("could not connect to OpenCage", result.output)

    def test_rejected_services(self):
        from opencage.geocoder import NotAuthorizedError
        from twilio.base.exceptions import TwilioRestException
        with patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "test", "TWILIO_AUTH_TOKEN": "test", "OPENCAGE_API_KEY": "test"}):
            with patch("twilio.rest.Client") as client, patch("opencage.geocoder.OpenCageGeocode.geocode", side_effect=NotAuthorizedError()):
                client.return_value.lookups.v2.phone_numbers.return_value.fetch.side_effect = TwilioRestException(401, "test", code=20003)
                result = CliRunner().invoke(main, ["--number", "6975954890", "--twilio", "--map", "unused.html"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn("20003", result.output)
                self.assertIn("OpenCage rejected the API key (unauthorized)", result.output)

    def test_empty_and_successful_map(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"OPENCAGE_API_KEY": "test"}):
            output = Path(folder) / "map.html"
            with patch("opencage.geocoder.OpenCageGeocode.geocode", return_value=[]):
                result = CliRunner().invoke(main, ["--number", "6975954890", "--map", str(output)])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertFalse(output.exists())
            with patch("opencage.geocoder.OpenCageGeocode.geocode", return_value=[{"geometry": {"lat": 39, "lng": 22}}]):
                result = CliRunner().invoke(main, ["--number", "6975954890", "--map", str(output)])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn("not the device location", output.read_text(encoding="utf-8"))


class MapServerTests(unittest.TestCase):
    def test_serves_only_map_and_stops(self):
        from urllib.request import urlopen
        from urllib.error import HTTPError, URLError
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "map with spaces.html"
            path.write_text("<html>Map</html>", encoding="utf-8")
            with map_server(path, preferred_port=0) as (url, owned):
                self.assertTrue(owned)
                with urlopen(url, timeout=2) as response:
                    self.assertEqual(response.read(), path.read_bytes())
                with self.assertRaises(HTTPError):
                    urlopen(url.rsplit("/", 1)[0] + "/main.py", timeout=2)
            with self.assertRaises(URLError):
                urlopen(url, timeout=2)

    def test_reuses_matching_server_and_keeps_it_running(self):
        from urllib.request import urlopen
        from urllib.parse import urlsplit
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "map.html"
            path.write_text("map", encoding="utf-8")
            with map_server(path, preferred_port=0) as (url, _):
                port = urlsplit(url).port
                with map_server(path, preferred_port=port) as (second, owned):
                    self.assertEqual(second, url)
                    self.assertFalse(owned)
                with urlopen(url, timeout=2) as response:
                    self.assertEqual(response.read(), b"map")
                other = Path(folder) / "other.html"
                other.write_text("other", encoding="utf-8")
                with map_server(other, preferred_port=port) as (second, owned):
                    self.assertTrue(owned)
                    self.assertNotEqual(urlsplit(second).port, port)

    def test_ctrl_c_closes_owned_server(self):
        from urllib.request import urlopen
        from urllib.error import URLError
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "map.html"
            path.write_text("map", encoding="utf-8")
            with patch("main.open_browser_url", return_value=True) as browser:
                with patch("main.map_server") as server:
                    server.return_value.__enter__.return_value = ("http://127.0.0.1:8000/map.html", True)
                    with patch("main.threading.Event") as event:
                        event.return_value.wait.side_effect = KeyboardInterrupt
                        show_map(path)
                    server.return_value.__exit__.assert_called_once()
                    browser.assert_called_once_with("http://127.0.0.1:8000/map.html")


if __name__ == "__main__":
    unittest.main()
