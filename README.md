# WindSync

A field maintenance management web app for wind farm technicians to view work orders, log task progress, and receive real-time notifications — designed to work offline in remote environments.

## Features

- **Plan of Day** — View assigned work orders grouped by proximity on a map, optimized for efficient routing between turbines
- **Work Order Details** — AI-powered fault diagnostics, tribal knowledge notes, tap-to-log checklists, and photo/text logging
- **Technician Dashboard** — Personal performance metrics and completed task history
- **Manager Dashboard** — Fleet-wide analytics and operations overview
- **Notifications** — Priority-based alerts (Critical / High / Medium / Low) with offline support and automatic sync when connectivity returns

## Requirements

- Python 3.12+
- Streamlit 1.47+
- Pandas
- Pillow

## Setup

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd WindSync
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install streamlit pandas pillow
   ```

4. **Initialize the database**
   ```bash
   python database_setup.py
   ```

5. **Run the app**
   ```bash
   streamlit run windsync_app.py
   ```

The app will open in your browser at `http://localhost:8501`. The demo is pre-loaded with a technician (Alex Ray, `tech_007`) and sample work orders across three turbine sites.

## Project Structure

```
windsync_app.py                  # Main application
windsync_with_notifications.py   # App with integrated real-time notifications
database_setup.py                # Database schema setup and demo data
notifications_system.py          # Notification manager (core logic)
notification_api.py              # REST-style notification API layer
sync_manager.py                  # Offline sync queue with retry logic
static/
  css/notifications.css          # Notification UI styles
  js/notifications.js            # Client-side offline/sync logic (IndexedDB)
tests/
  test_notifications.py          # Unit tests
```

## Running Tests

```bash
python -m pytest tests/test_notifications.py
python test_phase2_integration.py
```

## Offline Support

The notification system is built for intermittent connectivity. Notifications are stored locally (IndexedDB in the browser, SQLite on the backend) and synced to the server when a connection is available. Sync is prioritized by severity — critical alerts retry first, with exponential backoff.
