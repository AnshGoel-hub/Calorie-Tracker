# Calorie Tracker

A personal calorie, macro, water and weight tracker. A single-page frontend (`index.html`) talks to a small FastAPI backend (`main.py`) that stores your data in a local JSON file and, optionally, asks Google Gemini to estimate foods that aren't in the built-in list.

## Features

- Log food by unit (piece, bowl, tsp, biscuit...) or exact grams, grouped by meal
- Daily calorie ring and protein / carbs / fat totals, with a 5% margin before a day counts as over target
- Water and weight tracking
- "Last 7 days" summary: averages, streaks, and days recorded for food, water and weight
- Trend charts for calories, macros, weight (with a 7-day average) and water
- Gemini estimates for unknown foods (home-cooked, packaged, restaurant or homemade recipe), validated and shown for review before you save them
- Add your own foods, export and import backups, light and dark theme

## Setup

1. Create and activate a Python virtual environment.
   ```bash
   python -m venv venv
   venv\Scripts\activate          # Windows
   source venv/bin/activate       # macOS / Linux
   ```
2. Install the dependencies.
   ```bash
   pip install -r requirements.txt
   ```
   If your `requirements.txt` doesn't include them, run `pip install fastapi uvicorn`.
3. (Optional, for Gemini estimates) Create a `.env` file next to `main.py`:
   ```bash
   copy .env.example .env         # Windows
   cp .env.example .env           # macOS / Linux
   ```
   Open `.env` and replace `your-key-here` with your own key from Google AI Studio:
   ```
   GEMINI_API_KEY=your-key-here
   ```
   No quotes or spaces around the `=`. Without a key, everything works except the "Estimate with Gemini" button.
4. Start the server.
   ```bash
   python main.py
   ```
5. Open **http://127.0.0.1:8000** in your browser.

Do not open `index.html` by double-clicking it. The page must be loaded from the server, because the backend only accepts requests from its own address.

Restart `python main.py` whenever you change `.env`.

## Using it

- **Add a food:** start typing in the Food box, pick a suggestion, choose the meal, then a unit and a quantity. Use "Exact grams" if you weighed it.
- **Food not in the list:** pick what kind of food it is and press "Estimate with Gemini". The numbers appear under "Add your own" so you can check and edit them. Press "Save food", then add it to your log. Saved estimates are labelled "est." with their type.
- **Your own food:** under "Add your own", enter kcal, protein, carbs and fat per 100 g, and units as `name:grams`, for example `piece:40` or `small bowl:100, medium bowl:150`.
- **Edit or remove an entry:** use the pencil and cross next to it.
- **Backup:** "Export backup" and "Import backup" are in the Target record section at the bottom.

## Where your data lives

- `tracker_data.json`, next to `main.py`, is the main copy.
- A second copy is kept in your browser, so the app still works if the server is stopped. When the server is back, whichever copy was saved most recently is used.

## Gemini and your API key

- The key stays on the server. The browser never sees it and never calls Gemini directly.
- Optional setting in `.env`: `GEMINI_MODEL=` to choose a different model. The default is `gemini-3.5-flash-lite`.
- Estimates are approximate. Each one is checked for sensible values (calories match the macros, realistic serving weights), but accuracy is not guaranteed, especially for branded and restaurant foods. For packaged food, copying the per-100 g values from the label is more reliable.

## Sharing this project

Share `index.html`, `main.py`, `requirements.txt`, `.env.example`, `.gitignore` and this README. Do **not** share:

- `.env` (your API key)
- `tracker_data.json` (your personal data)
- `venv/`

Each person should use their own Gemini key. Keep the `.gitignore` file named exactly `.gitignore` so git skips `.env` and your data.

## Using it on your phone (same Wi-Fi)

1. In `main.py`, change the last line to `uvicorn.run(app, host="0.0.0.0", port=8000)` and restart.
2. Allow the app through the firewall on private networks if prompted.
3. Find your computer's local IP address (`ipconfig` on Windows) and open `http://<that-address>:8000` on your phone.

There is no login, so only do this on a network you trust. Anyone who can reach the address can read your data and use your Gemini key.

## Troubleshooting

| Problem | Likely cause and fix |
| --- | --- |
| "couldn't reach the backend" | The page isn't loaded from `http://127.0.0.1:8000`, or the server isn't running. Start `python main.py` and open that address. |
| "the backend has no Gemini key" | `.env` is missing, misnamed (for example `.env.txt`), in the wrong folder, or the server wasn't restarted after editing it. |
| "Gemini error 400 or 403" | The API key is wrong or has a typo. Create a new one in Google AI Studio. |
| "Gemini error 404" | The model isn't available to your account. Set a different `GEMINI_MODEL` in `.env`. |
| "Gemini error 429" | You've hit the usage limit. Wait and try again. |
| Changes don't show after updating files | Hard-refresh the page with Ctrl+Shift+R and restart the server. |

The terminal running the server prints a line starting with `[estimate]` that explains any Gemini failure.