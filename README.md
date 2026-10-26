# Phone Details

Validate and format a phone number and display country, numbering area, line type,
time zones and the carrier associated with its prefix. Default country: Greece.
Basic lookup runs locally and needs no API keys.

## Run (WSL)

```bash
pipenv install
# Διεθνής αριθμός και έξοδος JSON
pipenv run python main.py --number "+306975954890" --json

# Εθνικός αριθμός άλλης χώρας
pipenv run python main.py --number "020 8366 1177" --region GB

# Προαιρετική αναζήτηση μέσω Twilio, με πιθανή χρέωση υπηρεσίας
pipenv run python main.py --number "6975954890" --twilio

# Προαιρετικός χάρτης, με ρυθμισμένο OPENCAGE_API_KEY
pipenv run python main.py --number "6975954890" --map phones_location.html
```

Use `--help` for all options. International numbers starting with `+` or `00`
override the default country. Invalid numbers are rejected. Number validity only
means the format matches a numbering plan; it does not prove an active connection.
Prefix carrier data can be outdated after number portability.

## Optional Twilio lookup

Set credentials in the same terminal, then explicitly enable the remote lookup.
Provider charges may apply. This uses Lookup v2 Line Type Intelligence.

```bash
export TWILIO_ACCOUNT_SID='your-account-sid'
read -rsp 'Twilio Auth Token: ' TWILIO_AUTH_TOKEN; echo
export TWILIO_AUTH_TOKEN
pipenv run python main.py --number "6975954890" --twilio
```

Missing credentials, API failures and unavailable carrier data produce warnings
while preserving the local results. No remote calls are made without the option.

## Optional map

```bash
read -rsp 'OpenCage API key: ' OPENCAGE_API_KEY; echo
export OPENCAGE_API_KEY
pipenv run python main.py --number "6975954890" --map phones_location.html
```

Add `--open-map` to start a local HTTP server and open the map URL in your
browser (including the Windows browser from WSL). Keep the app running while
viewing the map. Press Ctrl+C in its terminal to stop the app and its server.
Closing only the browser tab does not stop the app.

The app tries port 8000, reuses an existing server only if it returns the exact
same map, and selects an available port if another application owns port 8000.
Servers started outside this app are left running. The built-in server binds
only to 127.0.0.1 and serves only the map, not the project source files.

```bash
pipenv run python main.py --number "6975954890" --map phones_location.html --open-map
```

Without `--open-map`, the command only saves the HTML and exits. OpenCage receives the area
name, not the phone number. Online map tiles need an internet connection.
A missing/rejected key, quota failure or empty geocoding result skips the map
with a warning. No map file is created for a failed request.

The map shows the approximate center of a numbering area, sometimes an entire
country. It does not locate the phone, track its movement, identify its owner,
or verify whether it is reachable.

Keep credentials out of source code and version control. The app automatically loads `.env` from the project folder. Existing shell
environment variables take priority over values in `.env`. The `.env` file is
excluded from Git; `.env.example` contains only empty configuration fields. Replace any
credentials previously exposed or committed using the provider console.

## Tests

```bash
pipenv run python -m unittest discover -s tests -v
```

Tests use mocks for external services and make no paid API requests.

## Local credentials

The app reads `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `OPENCAGE_API_KEY`
from the local `.env` file. Keep this file on your computer and never commit it.
For a fresh checkout, copy `.env.example` to `.env` and fill in your own values.
