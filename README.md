# FloodGuard BD — Professional Dashboard

Public-facing Bangladesh flood intelligence dashboard built with Flask.

## Run locally
1. Install Python 3.11+.
2. Open a terminal in this folder.
3. Run `python -m pip install -r requirements.txt`.
4. Run `python app.py`.
5. Open the URL shown by Flask (Render uses `$PORT`; locally the app defaults to 5081).

## Render
Build command:
`pip install -r requirements.txt`

Start command:
`gunicorn --bind 0.0.0.0:$PORT app:app`

The homepage is served from the root `index.html` so the deployment does not depend on a `templates/` copy.

## Notes
- The public dashboard works without login.
- Login is optional and is for saved preferences and future notification delivery.
- Observed/source data, forecast/reference data, and AI projections are kept distinct in the UI.
- Long-range forecasts are experimental and uncertain; official authorities remain the emergency decision source.


ALERT CONFIGURATION
- Website is login-optional.
- Users can save a preferred zone, language, WhatsApp number, and alert choices.
- One welcome alert, one daily alert, and one alert per daily risk-state change are tracked per user.
- Email delivery uses SMTP environment variables: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM.
- WhatsApp delivery uses Twilio environment variables: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM.
- `/api/alerts/dispatch` can be called by an external cron for reliable scheduled delivery.


## v5091 performance pass

Reduced expensive continuous effects, removed the blocking transition overlay, deferred large hidden-page work, and reduced repeated DOM/animation work for smoother scrolling and navigation.
