# run this command to setup the database file
# python database_setup.py

# database_setup.py
import sqlite3
import os

# --- Configuration ---
# DB_FILE = "windsync.db"
# TECHNICIAN_ID = "tech_007"
# TECHNICIAN_NAME = "Alex Ray"

# # Delete existing database file if it exists, for a clean setup
# if os.path.exists(DB_FILE):
#     os.remove(DB_FILE)

# # Connect to the SQLite database (this will create the file)
# conn = sqlite3.connect(DB_FILE)
# cursor = conn.cursor()

# # --- Create Tables ---

# # Technicians Table
# cursor.execute("""
# CREATE TABLE technicians (
#     id TEXT PRIMARY KEY,
#     name TEXT NOT NULL
# )
# """)

# # Assets (Turbines) Table
# cursor.execute("""
# CREATE TABLE assets (
#     id TEXT PRIMARY KEY,
#     name TEXT NOT NULL,
#     latitude REAL NOT NULL,
#     longitude REAL NOT NULL,
#     model TEXT
# )
# """)

# # Work Orders Table
# cursor.execute("""
# CREATE TABLE work_orders (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     technician_id TEXT,
#     asset_id TEXT,
#     title TEXT NOT NULL,
#     description TEXT,
#     priority TEXT,
#     status TEXT,
#     tools_required TEXT,
#     parts_required TEXT,
#     FOREIGN KEY (technician_id) REFERENCES technicians (id),
#     FOREIGN KEY (asset_id) REFERENCES assets (id)
# )
# """)

# # Technician Logs Table (for notes and photos)
# cursor.execute("""
# CREATE TABLE logs (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     work_order_id INTEGER,
#     log_text TEXT,
#     photo BLOB,
#     FOREIGN KEY (work_order_id) REFERENCES work_orders (id)
# )
# """)

# # --- Populate with Sample Data ---

# # Add our demo technician
# cursor.execute("INSERT INTO technicians (id, name) VALUES (?, ?)", (TECHNICIAN_ID, TECHNICIAN_NAME))

# # Add sample assets (turbines)
# # Group 1 (within 10-mile radius)
# cursor.execute("INSERT INTO assets (id, name, latitude, longitude, model) VALUES (?, ?, ?, ?, ?)",
#                ('WTG-A01', 'Turbine A01 - North Ridge', 47.6588, -122.1411, 'Siemens Gamesa 4.5-145'))
# cursor.execute("INSERT INTO assets (id, name, latitude, longitude, model) VALUES (?, ?, ?, ?, ?)",
#                ('WTG-A04', 'Turbine A04 - North Ridge', 47.6519, -122.1333, 'Siemens Gamesa 4.5-145'))
# # Group 2 (another location)
# cursor.execute("INSERT INTO assets (id, name, latitude, longitude, model) VALUES (?, ?, ?, ?, ?)",
#                ('WTG-C12', 'Turbine C12 - West Valley', 47.5952, -122.3321, 'Vestas V117-4.2'))
# # Group 3 (isolated location)
# cursor.execute("INSERT INTO assets (id, name, latitude, longitude, model) VALUES (?, ?, ?, ?, ?)",
#                ('WTG-B07', 'Turbine B07 - East Mesa', 47.6097, -122.0123, 'GE 2.8-127'))


# # Add sample work orders assigned to Alex Ray
# work_orders_data = [
#     (TECHNICIAN_ID, 'WTG-A01', 'Gearbox Vibration Analysis', 'High vibrations detected in gearbox. Perform full diagnostic check.', 'High', 'New',
#      'Vibration Analyzer, Torque Wrench Set, Standard Tool Kit', 'Vibration Sensor #789, Gearbox Oil Filter'),
#     (TECHNICIAN_ID, 'WTG-A04', 'Routine Blade Inspection', 'Annual visual inspection of all three blades for wear and tear.', 'Medium', 'New',
#      'High-Res Camera, Drone (optional), Safety Harness, Binoculars', 'Blade Sealant Kit'),
#     (TECHNICIAN_ID, 'WTG-C12', 'Hydraulic Leak Repair', 'Small hydraulic leak detected at the base. Identify source and repair.', 'High', 'New',
#      'Hydraulic Fluid Pump, Wrench Set, Oil Spill Kit', 'Hydraulic Hose #H-12, O-Ring Seal Kit'),
#     (TECHNICIAN_ID, 'WTG-B07', 'Software Update & Calibration', 'Install latest firmware patch and recalibrate pitch control system.', 'Low', 'New',
#      'Ruggedized Laptop, Calibration Unit #C-45', 'None')
# ]

# cursor.executemany("""
# INSERT INTO work_orders (technician_id, asset_id, title, description, priority, status, tools_required, parts_required)
# VALUES (?, ?, ?, ?, ?, ?, ?, ?)
# """, work_orders_data)

# # Commit changes and close the connection
# conn.commit()
# conn.close()

# print(f"Database '{DB_FILE}' created and populated successfully.")


# database_setup.py
import sqlite3
import os

# --- Configuration ---
DB_FILE = "windsync.db"
TECHNICIAN_ID = "tech_007"
TECHNICIAN_NAME = "Alex Ray"

# Delete existing database file if it exists, for a clean setup
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

# Connect to the SQLite database (this will create the file)
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# --- Create Tables ---

cursor.execute("CREATE TABLE technicians (id TEXT PRIMARY KEY, name TEXT NOT NULL, certifications TEXT)")
cursor.execute("CREATE TABLE assets (id TEXT PRIMARY KEY, name TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL, model TEXT)")

# UPDATED: Added new columns for AI features
cursor.execute("""
CREATE TABLE work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    technician_id TEXT,
    asset_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT,
    status TEXT,
    tools_required TEXT,
    parts_required TEXT,
    ai_alert_title TEXT,
    ai_confidence INTEGER,
    tribal_knowledge_note TEXT,
    FOREIGN KEY (technician_id) REFERENCES technicians (id),
    FOREIGN KEY (asset_id) REFERENCES assets (id)
)
""")

cursor.execute("""
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id INTEGER,
    log_text TEXT,
    photo BLOB,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (work_order_id) REFERENCES work_orders (id)
)
""")

# --- Populate with Sample Data ---

cursor.execute("INSERT INTO technicians (id, name, certifications) VALUES (?, ?, ?)", (TECHNICIAN_ID, TECHNICIAN_NAME, "GWO Certified, Electrical Level II"))

cursor.execute("INSERT INTO assets (id, name, latitude, longitude, model) VALUES (?, ?, ?, ?, ?)",
               ('WTG-A01', 'Turbine A01 - North Ridge', 47.6588, -122.1411, 'Siemens Gamesa 4.5-145'))
cursor.execute("INSERT INTO assets (id, name, latitude, longitude, model) VALUES (?, ?, ?, ?, ?)",
               ('WTG-A04', 'Turbine A04 - North Ridge', 47.6519, -122.1333, 'Siemens Gamesa 4.5-145'))
cursor.execute("INSERT INTO assets (id, name, latitude, longitude, model) VALUES (?, ?, ?, ?, ?)",
               ('WTG-C12', 'Turbine C12 - West Valley', 47.5952, -122.3321, 'Vestas V117-4.2'))

# UPDATED: Populate the new AI feature columns
work_orders_data = [
    (TECHNICIAN_ID, 'WTG-A01', 'Gearbox Vibration Analysis', 'High vibrations detected. Perform full diagnostic check.', 'High', 'New',
     'Vibration Analyzer, Torque Wrench Set', 'Vibration Sensor #789',
     'Gearbox Bearing Fault', 95, 'Note: This unit had a yaw motor alignment last quarter. Check for related stress.'),
    (TECHNICIAN_ID, 'WTG-A04', 'Routine Blade Inspection', 'Annual visual inspection of all three blades for wear and tear.', 'Medium', 'New',
     'High-Res Camera, Drone (optional)', 'Blade Sealant Kit',
     'No Fault Detected', 100, 'Standard procedure. No known issues with this asset.'),
    (TECHNICIAN_ID, 'WTG-C12', 'Hydraulic Leak Repair', 'Small hydraulic leak detected at the base. Identify source and repair.', 'High', 'New',
     'Hydraulic Fluid Pump, Oil Spill Kit', 'Hydraulic Hose #H-12',
     'Hydraulic Hose Fatigue', 85, 'This model is prone to hose fatigue near the main pump connection. Check there first.')
]

cursor.executemany("""
INSERT INTO work_orders (technician_id, asset_id, title, description, priority, status, tools_required, parts_required, ai_alert_title, ai_confidence, tribal_knowledge_note)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", work_orders_data)

# Add a completed work order for the dashboard
cursor.execute("""
INSERT INTO work_orders (technician_id, asset_id, title, description, priority, status, tools_required, parts_required, ai_alert_title, ai_confidence, tribal_knowledge_note)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (TECHNICIAN_ID, 'WTG-A04', 'Past Filter Change', 'Completed filter change.', 'Low', 'Completed', 'Wrench', 'Filter #123', 'N/A', 100, ''))


conn.commit()
conn.close()

print(f"Database '{DB_FILE}' created and populated successfully.")