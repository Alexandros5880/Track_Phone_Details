"""Phone number metadata lookup. Does not locate a device or identify its owner."""
import html
import json
import os
import platform
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlsplit
from urllib.request import urlopen
from urllib.error import URLError
from pathlib import Path
import webbrowser

import click
from dotenv import load_dotenv
import phonenumbers
from phonenumbers import carrier, geocoder, timezone

load_dotenv(Path(__file__).resolve().with_name(".env"))


def analyze_number(value, region="GR"):
    region = region.upper()
    if region not in phonenumbers.SUPPORTED_REGIONS:
        raise click.BadParameter("Use a two-letter country code, such as GR or GB.", param_hint="--region")
    value = value.strip()
    if value.startswith("00"):
        value = "+" + value[2:]
    try:
        number = phonenumbers.parse(value, region)
    except phonenumbers.NumberParseException:
        raise click.BadParameter("Cannot parse this phone number.", param_hint="--number") from None
    if not phonenumbers.is_valid_number(number):
        raise click.BadParameter("Invalid phone number for the selected country.", param_hint="--number")
    types = {
        phonenumbers.PhoneNumberType.MOBILE: "mobile",
        phonenumbers.PhoneNumberType.FIXED_LINE: "landline",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "landline or mobile",
        phonenumbers.PhoneNumberType.TOLL_FREE: "toll-free",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "premium rate",
        phonenumbers.PhoneNumberType.VOIP: "VoIP",
    }
    return {
        "number": phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
        "international": phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        "region": phonenumbers.region_code_for_number(number),
        "description": geocoder.description_for_number(number, "en"),
        "type": types.get(phonenumbers.number_type(number), "other or unknown"),
        "prefix_carrier": carrier.name_for_number(number, "en") or None,
        "time_zones": list(timezone.time_zones_for_number(number)),
        "twilio": None,
        "warnings": [],
        "notice": "Metadata only: validity does not prove the number is active. Prefix carrier may differ after number portability. No device location or owner identity is available.",
    }


def enrich_twilio(result):
    # Your Twilio Account SID and Auth Token
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    from requests.exceptions import RequestException
    from twilio.base.exceptions import TwilioRestException
    from twilio.http.http_client import TwilioHttpClient
    from twilio.rest import Client
    try:
        client = Client(sid, token, http_client=TwilioHttpClient(timeout=15))
        info = client.lookups.v2.phone_numbers(result["number"]).fetch(fields="line_type_intelligence")
        data = info.line_type_intelligence or {}
        if data.get("error_code"):
            result["warnings"].append(f"Twilio carrier information unavailable (code {data['error_code']}).")
        elif data:
            result["twilio"] = {"carrier": data.get("carrier_name"), "type": data.get("type")}
        else:
            result["warnings"].append("Twilio returned no carrier information.")
    except TwilioRestException as exc:
        result["warnings"].append(f"Twilio request failed (code {exc.code}, HTTP {exc.status}). Check credentials, permissions and service availability.")
    except RequestException:
        result["warnings"].append("Twilio could not be reached. Check your connection and retry.")


def create_map(result, destination, open_browser=False):
    key = os.environ.get("OPENCAGE_API_KEY", "").strip()
    if not result["description"] or not result["region"]:
        result["warnings"].append("Map skipped: no geographic description is available.")
        return
    from opencage.geocoder import (OpenCageGeocode, OpenCageGeocodeError,
                                  NotAuthorizedError, ForbiddenError, RateLimitExceededError)
    from requests.exceptions import RequestException
    import folium
    try:
        matches = OpenCageGeocode(key).geocode(
            result["description"], countrycode=result["region"].lower(), limit=1, timeout=15
        )
    except NotAuthorizedError:
        result["warnings"].append("Map unavailable: OpenCage rejected the API key (unauthorized). Check or replace OPENCAGE_API_KEY in your OpenCage account.")
        return
    except ForbiddenError:
        result["warnings"].append("Map unavailable: OpenCage denied access. Check your account status and remaining quota.")
        return
    except RateLimitExceededError:
        result["warnings"].append("Map unavailable: OpenCage request rate limit reached. Wait before retrying.")
        return
    except RequestException:
        result["warnings"].append("Map unavailable: could not connect to OpenCage. Check your internet connection and retry.")
        return
    except OpenCageGeocodeError:
        result["warnings"].append("Map unavailable: OpenCage could not process the geocoding request.")
        return
    if not matches:
        result["warnings"].append("Map unavailable: no matching geographic area was found.")
        return
    geometry = matches[0]["geometry"]
    center = [geometry["lat"], geometry["lng"]]
    map_view = folium.Map(location=center, zoom_start=5)
    caption = "Approximate numbering area only — not the device location."
    folium.Marker(center, popup=html.escape(result["description"] + ". " + caption)).add_to(map_view)
    map_view.get_root().html.add_child(folium.Element(
        '<p style="text-align:center">' + html.escape(caption) + '</p>'
    ))
    path = Path(destination).resolve()
    try:
        map_view.save(str(path))
    except OSError as exc:
        raise click.ClickException(f"Cannot save map: {exc.strerror}") from None
    result["map_file"] = str(path)


def open_browser_url(url):
    """Use the Windows browser from WSL, passing the URL as data."""
    try:
        if "microsoft" in platform.release().lower():
            environment = os.environ.copy()
            environment["PHONE_DETAILS_MAP_URL"] = url
            environment["WSLENV"] = ":".join(filter(None, [
                environment.get("WSLENV", ""), "PHONE_DETAILS_MAP_URL"
            ]))
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "Start-Process -FilePath $env:PHONE_DETAILS_MAP_URL"],
                env=environment, capture_output=True, timeout=20,
            )
            return completed.returncode == 0
        return webbrowser.open(url)
    except (OSError, subprocess.SubprocessError):
        return False


@contextmanager
def map_server(path, preferred_port=8000):
    """Serve only the generated map; never expose source code or credentials."""
    path = Path(path).resolve()
    payload = path.read_bytes()
    route = "/" + quote(path.name, safe="")
    preferred_url = f"http://127.0.0.1:{preferred_port}{route}"

    class MapHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlsplit(self.path).path != route:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    try:
        server = ThreadingHTTPServer(("127.0.0.1", preferred_port), MapHandler)
    except OSError:
        # Reuse a server only when it serves exactly this map. Otherwise choose
        # a free port without interfering with the process already listening.
        try:
            with urlopen(preferred_url, timeout=2) as response:
                reusable = response.read(len(payload) + 1) == payload
        except (OSError, URLError):
            reusable = False
        if reusable:
            yield preferred_url, False
            return
        server = ThreadingHTTPServer(("127.0.0.1", 0), MapHandler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}{route}", True
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def show_map(path):
    try:
        with map_server(path) as (url, owned):
            click.echo(f"Map URL: {url}", err=True)
            if not open_browser_url(url):
                click.echo("Could not open the browser automatically. Open the URL above.", err=True)
            click.echo("Map ready. Press Ctrl+C to close the app." +
                       (" Its local server will stop." if owned else " Using an existing server."), err=True)
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass
        click.echo("App closed. Local server stopped." if owned else
                   "App closed. Existing server left running.", err=True)
    except OSError as exc:
        raise click.ClickException(f"Cannot serve map: {exc.strerror}") from None


@click.command()
@click.option("-n", "--number", required=True, help="National or international phone number.")
@click.option("--region", default="GR", show_default=True, help="Country for national numbers (ISO code).")
@click.option("--twilio", is_flag=True, help="Request Twilio carrier data; provider charges may apply.")
@click.option("--map", "map_output", type=click.Path(dir_okay=False), help="Save an approximate area map as HTML (requires OpenCage).")
@click.option("--open-map", is_flag=True, help="Serve the map over HTTP and open the browser; Ctrl+C stops the app. Requires --map.")
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON.")
def main(number, region, twilio, map_output, open_map, as_json):
    """Validate phone numbers and display metadata. No external requests by default."""
    if open_map and not map_output:
        raise click.UsageError("--open-map requires --map FILE.html.")
    result = analyze_number(number, region)
    if twilio:
        enrich_twilio(result)
    if map_output:
        create_map(result, map_output, open_map)
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        if open_map and result.get("map_file"):
            show_map(result["map_file"])
        return
    for label, value in [
        ("Number", result["international"]), ("Country code", result["region"]),
        ("Numbering area", result["description"]), ("Line type", result["type"]),
        ("Carrier from prefix (may be outdated)", result["prefix_carrier"]),
        ("Time zones", ", ".join(result["time_zones"])),
    ]:
        click.echo(f"{label}: {value or 'Unavailable'}")
    if result["twilio"]:
        click.echo(f"Twilio carrier: {result['twilio']['carrier'] or 'Unavailable'}")
        click.echo(f"Twilio line type: {result['twilio']['type'] or 'Unavailable'}")
    if result.get("map_file"):
        click.echo(f"Map saved: {result['map_file']}")
    click.echo(result["notice"])
    for warning in result["warnings"]:
        click.echo(f"Warning: {warning}", err=True)
    if open_map and result.get("map_file"):
        show_map(result["map_file"])


if __name__ == "__main__":
    main()
