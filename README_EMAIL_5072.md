# FloodGuard BD — Google Apps Script Email Alerts

This build connects the Flask app to a Google Apps Script Web App that sends mail through Gmail.

## Environment variable (optional)
`FLOODGUARD_EMAIL_WEBAPP_URL`

The current Apps Script `/exec` URL is already included as a fallback, so the app can work without adding this variable. For production, setting the environment variable in Render is recommended so the URL can be changed without editing code.

## Alert behavior
- Welcome: one time after the user enables alerts.
- Risk change: one message only when the zone's risk category transitions.
- Daily: one message per calendar day.
- Test: available under My account & alerts.

The website remains usable without login. Login is only for personalized alerts and saved preferences.
