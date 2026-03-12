# # main file to run, use this command:
# # streamlit run windsync_app.py

# windsync_app.py
# import streamlit as st
# import sqlite3
# import pandas as pd
# from PIL import Image
# import io
# import math

# # --- Configuration & Page Setup ---
# st.set_page_config(page_title="WindSync Demo", layout="wide")
# DB_FILE = "windsync.db"
# TECHNICIAN_ID = "tech_007" # The demo technician we'll be showcasing

# # --- Database Connection & Utility Functions ---
# def get_db_connection():
#     """Establishes a connection to the SQLite database."""
#     conn = sqlite3.connect(DB_FILE, check_same_thread=False)
#     conn.row_factory = sqlite3.Row
#     return conn

# def haversine(lat1, lon1, lat2, lon2):
#     """Calculate the distance between two points on Earth in miles."""
#     R = 3958.8  # Earth radius in miles
#     dLat = math.radians(lat2 - lat1)
#     dLon = math.radians(lon2 - lon1)
#     lat1 = math.radians(lat1)
#     lat2 = math.radians(lat2)
#     a = math.sin(dLat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dLon / 2)**2
#     c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     distance = R * c
#     return distance

# def style_priority(row):
#     """Applies color to rows based on priority."""
#     priority = row['priority']
#     if priority == 'High':
#         return ['background-color: #FFCDD2'] * len(row)
#     elif priority == 'Medium':
#         return ['background-color: #FFF9C4'] * len(row)
#     elif priority == 'Low':
#         return ['background-color: #C8E6C9'] * len(row)
#     return [''] * len(row)

# # --- NEW: Function to clear logs ---
# def clear_log_entries():
#     """Connects to the DB and clears all entries from the logs table."""
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor()
#         cursor.execute("DELETE FROM logs")
#         cursor.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
#         conn.commit()
#         conn.close()
#         st.toast("✅ Success: All log entries have been cleared!")
#     except Exception as e:
#         st.error(f"An error occurred while clearing logs: {e}")


# # --- View Functions ---

# def plan_of_day_view():
#     """Displays the main dashboard for the technician's Plan of Day (POD)."""
#     conn = get_db_connection()
#     work_orders_df = pd.read_sql_query(
#         """
#         SELECT wo.id, wo.title, wo.priority, wo.status, a.name as asset_name, a.latitude, a.longitude
#         FROM work_orders wo
#         JOIN assets a ON wo.asset_id = a.id
#         WHERE wo.technician_id = ? AND wo.status != 'Completed'
#         """, conn, params=(TECHNICIAN_ID,))
#     conn.close()

#     st.subheader("Plan of Day (POD)")

#     if work_orders_df.empty:
#         st.success("No active work orders. Great job!")
#         return

#     col1, col2 = st.columns(2)
#     with col1:
#         sort_by = st.selectbox("Sort tasks by:", ["Priority", "Default Order"])
#     with col2:
#         priorities = work_orders_df['priority'].unique().tolist()
#         selected_priorities = st.multiselect("Filter by priority:", options=priorities, default=priorities)

#     filtered_df = work_orders_df[work_orders_df['priority'].isin(selected_priorities)]

#     if sort_by == "Priority":
#         priority_order = ["High", "Medium", "Low"]
#         filtered_df['priority'] = pd.Categorical(filtered_df['priority'], categories=priority_order, ordered=True)
#         filtered_df = filtered_df.sort_values('priority')

#     if filtered_df.empty:
#         st.warning("No work orders match your current filter selection.")
#         return
        
#     st.info("💡 **Optimization Simulation**: Tasks within a 10-mile radius are grouped for efficiency.")
    
#     optimized_groups = []
#     processed_indices = set()
#     for i, row1 in filtered_df.iterrows():
#         if i in processed_indices: continue
#         current_group = [row1]; processed_indices.add(i)
#         for j, row2 in filtered_df.iterrows():
#             if j in processed_indices: continue
#             if haversine(row1['latitude'], row1['longitude'], row2['latitude'], row2['longitude']) <= 10.0:
#                 current_group.append(row2); processed_indices.add(j)
#         if len(current_group) > 1:
#             optimized_groups.append(pd.DataFrame(current_group))

#     for i, group_df in enumerate(optimized_groups):
#         with st.expander(f"**Optimized Work Group {i+1} (Geographically Clustered)**", expanded=True):
#             st.dataframe(
#                 group_df[['title', 'asset_name', 'priority', 'status']].style.apply(style_priority, axis=1),
#                 use_container_width=True
#             )
            
#     st.subheader("Job Site Locations")
#     st.map(filtered_df, latitude='latitude', longitude='longitude', size=20)


# def work_order_detail_view():
#     """Displays details for a selected work order and allows for logging."""
#     conn = get_db_connection()
#     work_order_list = pd.read_sql_query(
#         "SELECT wo.id, wo.title, a.name FROM work_orders wo JOIN assets a ON wo.asset_id = a.id WHERE wo.technician_id = ?",
#         conn, params=(TECHNICIAN_ID,))
    
#     wo_display_list = [f"{row['id']}: {row['title']} ({row['name']})" for index, row in work_order_list.iterrows()]

#     st.subheader("Work Order Details & Logging")
#     selected_wo_display = st.selectbox("Select a Work Order to view details:", wo_display_list)

#     if not selected_wo_display:
#         st.warning("Please select a work order."); conn.close(); return

#     selected_wo_id = int(selected_wo_display.split(":")[0])
    
#     wo_details = pd.read_sql_query("SELECT wo.*, a.name as asset_name, a.model FROM work_orders wo JOIN assets a ON wo.asset_id = a.id WHERE wo.id = ?", conn, params=(selected_wo_id,)).iloc[0]

#     col1, col2 = st.columns(2)
#     with col1:
#         st.markdown(f"#### {wo_details['title']}")
#         st.markdown(f"**Asset:** {wo_details['asset_name']} ({wo_details['model']})")
#         st.markdown(f"**Priority:** {wo_details['priority']}"); st.markdown(f"**Status:** {wo_details['status']}")
#         st.markdown(f"**Description:** {wo_details['description']}")
#     with col2:
#         st.warning("**Required Tools & Parts**")
#         st.markdown(f"**Tools:**\n> {wo_details['tools_required']}")
#         st.markdown(f"**Parts:**\n> {wo_details['parts_required']}")

#     st.divider()
#     st.markdown("#### Work Checklist & Logging")
    
#     checklist_items = ["Perform safety lockout/tagout", "Visually inspect the area", "Complete primary task", "Run system diagnostics", "Clean up work area"]
#     for item in checklist_items:
#         st.checkbox(item, key=f"check_{selected_wo_id}_{item}")
    
#     LOG_TEMPLATES = {
#         "-- Custom Note --": "",
#         "Routine Inspection": "Completed routine visual inspection. All components appear to be in good working order. No anomalies detected.",
#         "Part Replacement": "Identified faulty [PART_NAME]. Replaced with new part [PART_NUMBER]. System tested and is now operating within normal parameters.",
#         "Weather Delay": "Unable to complete work due to high winds exceeding safety limits. Will reschedule for the next available weather window."
#     }
    
#     template_choice = st.selectbox("Select a Log Template (Optional):", options=list(LOG_TEMPLATES.keys()))
#     template_text = LOG_TEMPLATES[template_choice]

#     with st.form("log_form", clear_on_submit=True):
#         log_text = st.text_area("Add a text note for documentation:", value=template_text, height=150)
#         log_photo = st.file_uploader("Upload a photo (optional):", type=['png', 'jpg', 'jpeg'])
#         submitted = st.form_submit_button("Save Log Entry")
#         if submitted:
#             photo_data = log_photo.getvalue() if log_photo else None
#             cursor = conn.cursor()
#             cursor.execute("INSERT INTO logs (work_order_id, log_text, photo) VALUES (?, ?, ?)", (selected_wo_id, log_text, photo_data))
#             conn.commit(); st.success("Log entry saved successfully!")

#     st.divider()
#     st.markdown("#### Previous Logs for this Work Order")
#     logs_df = pd.read_sql_query("SELECT * FROM logs WHERE work_order_id = ?", conn, params=(selected_wo_id,))
#     if logs_df.empty:
#         st.info("No previous logs for this work order.")
#     else:
#         for index, log in logs_df.iterrows():
#             with st.container(border=True):
#                 st.markdown(f"**Log Entry #{log['id']}**"); st.write(log['log_text'])
#                 if log['photo']:
#                     st.image(Image.open(io.BytesIO(log['photo'])), caption="Attached Photo", width=300)
#     conn.close()
    

# def manager_dashboard_view():
#     """Displays a dashboard for managers with the cost savings chart."""
#     st.subheader("Downtime Cost Savings Analysis 📈")
#     st.markdown("This chart shows the estimated monthly costs associated with asset downtime, comparing performance before and after the implementation of WindSync.")

#     # Create Mock Data for the chart
#     chart_data = {
#         'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
#         'Before WindSync ($)': [55000, 62000, 48000, 51000, 75000, 68000],
#         'With WindSync ($)':   [47000, 52000, 41000, 44000, 63000, 59000]
#     }
#     cost_df = pd.DataFrame(chart_data)

#     # --- THE FIX: Enforce Chronological Order ---
#     # Define the correct order of the months.
#     month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']

#     # Convert the 'Month' column to a special 'Categorical' data type with the correct order.
#     # This ensures any chart created from this DataFrame will respect this custom sort order.
#     cost_df['Month'] = pd.Categorical(cost_df['Month'], categories=month_order, ordered=True)
#     # --- END OF FIX ---

#     # Display the bar chart, which will now be correctly ordered.
#     st.bar_chart(cost_df, x='Month', y=['Before WindSync ($)', 'With WindSync ($)'])

#     # Calculate and display summary metrics (this part remains the same)
#     total_before = cost_df['Before WindSync ($)'].sum()
#     total_with = cost_df['With WindSync ($)'].sum()
#     total_savings = total_before - total_with
#     percent_reduction = (total_savings / total_before) * 100

#     st.divider()
#     st.subheader("6-Month Performance Summary")
#     col1, col2, col3 = st.columns(3)
#     col1.metric("Total Savings", f"${total_savings:,.0f}", help="Total reduction in downtime costs over 6 months.")
#     col2.metric("Cost Reduction", f"{percent_reduction:.1f}%", help="The percentage decrease in downtime costs.")
#     col3.metric("Cost w/ WindSync", f"${total_with:,.0f}", help="Total downtime costs incurred while using WindSync.")


# # --- Main App Router ---
# st.title("WindSync Demo")

# st.sidebar.title("Navigation")
# app_mode = st.sidebar.selectbox("Choose Your View",
#                                 ["Technician: Plan of Day", "Technician: Work Order Details", "Manager: Dashboard"])

# # --- UPDATED: Add the clear logs button to the sidebar ---
# st.sidebar.divider()
# st.sidebar.markdown("### Demo Controls")
# if st.sidebar.button("⚠️ Clear All Log Entries"):
#     clear_log_entries()
#     st.rerun() # Rerun the app to reflect the changes immediately

# # Main content display
# if app_mode == "Technician: Plan of Day":
#     plan_of_day_view()
# elif app_mode == "Technician: Work Order Details":
#     work_order_detail_view()
# elif app_mode == "Manager: Dashboard":
#     manager_dashboard_view()


# windsync_app.py
import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
import io
import math
import datetime

# Import our notification system
from notifications_system import (
    create_notification_manager,
    create_safety_alert,
    create_task_update,
    create_equipment_alert
)
from notification_api import create_streamlit_api

# --- Configuration & Page Setup ---
st.set_page_config(page_title="WindSync Demo", layout="wide")
DB_FILE = "windsync.db"
TECHNICIAN_ID = "tech_007"

# Initialize notification manager (cached for performance)
@st.cache_resource
def get_notification_manager():
    """Initialize and cache the notification manager"""
    return create_notification_manager(development_mode=True)

# Initialize Streamlit API for notifications (cached for performance)
@st.cache_resource
def get_streamlit_api():
    """Initialize and cache the Streamlit notification API"""
    return create_streamlit_api(development_mode=True)

# --- Database Connection & Utility Functions ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dLat, dLon, lat1, lat2 = map(math.radians, [lat2 - lat1, lon2 - lon1, lat1, lat2])
    a = math.sin(dLat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dLon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def style_priority(row):
    priority_colors = {'High': '#FFCDD2', 'Medium': '#FFF9C4', 'Low': '#C8E6C9'}
    color = priority_colors.get(row['priority'], '')
    return [f'background-color: {color}'] * len(row) if color else [''] * len(row)

def clear_log_entries():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
        conn.commit()
        conn.close()
        st.toast("✅ Success: All log entries have been cleared!")
    except Exception as e:
        st.error(f"An error occurred while clearing logs: {e}")

# --- NEW: Notification Integration Functions ---

def create_work_order_notification(work_order_id, title, priority_change=None):
    """Create notification when work order is updated"""
    manager = get_notification_manager()
    
    if priority_change:
        message = f"Work order #{work_order_id} priority changed to {priority_change}"
        priority = "high" if priority_change == "High" else "medium"
    else:
        message = f"Work order #{work_order_id}: {title} has been updated"
        priority = "medium"
    
    notification_id = create_task_update(
        manager,
        f"📋 Work Order Update",
        message,
        TECHNICIAN_ID,
        priority,
        {
            "work_order_id": work_order_id,
            "title": title,
            "update_time": datetime.datetime.now().isoformat()
        }
    )
    return notification_id

def create_equipment_diagnostic_notification(asset_name, diagnostic_info):
    """Create notification for equipment diagnostics"""
    manager = get_notification_manager()
    
    notification_id = create_equipment_alert(
        manager,
        f"🤖 AI Diagnostic: {diagnostic_info['ai_alert_title']}",
        f"AI system detected {diagnostic_info['ai_alert_title']} on {asset_name} with {diagnostic_info['ai_confidence']}% confidence.",
        TECHNICIAN_ID,
        "high" if diagnostic_info['ai_confidence'] > 80 else "medium",
        {
            "asset_name": asset_name,
            "ai_alert_title": diagnostic_info['ai_alert_title'],
            "ai_confidence": diagnostic_info['ai_confidence'],
            "tribal_knowledge": diagnostic_info['tribal_knowledge_note']
        }
    )
    return notification_id

def create_safety_notification(title, message, metadata=None):
    """Create safety notification"""
    manager = get_notification_manager()
    
    notification_id = create_safety_alert(
        manager,
        title,
        message,
        TECHNICIAN_ID,
        metadata or {}
    )
    return notification_id

def show_notification_badge():
    """Show notification badge in sidebar"""
    manager = get_notification_manager()
    unread_count = manager.get_unread_count(TECHNICIAN_ID)
    
    if unread_count > 0:
        st.sidebar.markdown(f"""
        <div style="
            background-color: #ff4444;
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 1rem;
            text-align: center;
            margin: 0.5rem 0;
            font-weight: bold;
        ">
            🔔 {unread_count} New Notification{'s' if unread_count != 1 else ''}
        </div>
        """, unsafe_allow_html=True)

# --- View Functions ---

def plan_of_day_view():
    st.subheader("Plan of Day (POD)")
    conn = get_db_connection()
    work_orders_df = pd.read_sql_query(
        """
        SELECT wo.id, wo.title, wo.priority, wo.status, a.name as asset_name, a.latitude, a.longitude
        FROM work_orders wo JOIN assets a ON wo.asset_id = a.id
        WHERE wo.technician_id = ? AND wo.status != 'Completed'
        """, conn, params=(TECHNICIAN_ID,))
    conn.close()

    if work_orders_df.empty:
        st.success("No active work orders. Great job!"); return

    # Filtering and Sorting (Preserved Feature)
    col1, col2 = st.columns(2)
    sort_by = col1.selectbox("Sort tasks by:", ["Priority", "Default Order"])
    priorities = work_orders_df['priority'].unique().tolist()
    selected_priorities = col2.multiselect("Filter by priority:", options=priorities, default=priorities)
    filtered_df = work_orders_df[work_orders_df['priority'].isin(selected_priorities)].copy()
    
    # Define priority_order for use throughout the function
    priority_order = ["High", "Medium", "Low"]
    
    if sort_by == "Priority":
        filtered_df['priority'] = pd.Categorical(filtered_df['priority'], categories=priority_order, ordered=True)
        filtered_df = filtered_df.sort_values('priority')

    if filtered_df.empty:
        st.warning("No work orders match filter selection."); return
        
    st.info("💡 **Optimization Simulation**: Tasks are clustered by location.")
    
    # NEW: Add notification trigger for priority changes
    st.markdown("#### 🔔 Notification Testing")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚨 Simulate High Wind Alert"):
            create_safety_notification(
                "🌪️ High Wind Warning",
                "Wind speeds exceeding 25 mph detected. Suspend all tower work immediately.",
                {"wind_speed": 28, "location": "North Ridge"}
            )
            st.success("Safety alert created!")
            st.rerun()
    
    with col2:
        if st.button("📋 Simulate Priority Change"):
            if not filtered_df.empty:
                first_wo = filtered_df.iloc[0]
                create_work_order_notification(
                    first_wo['id'], 
                    first_wo['title'], 
                    "High"
                )
                st.success("Work order notification created!")
                st.rerun()
    
    # Display work orders with notification integration
    for i, row in filtered_df.iterrows():
        with st.container(border=True):
            primary_task_col, secondary_task_col = st.columns([2,1])
            with primary_task_col:
                st.markdown(f"**Primary Task:** {row['title']} ({row['asset_name']})")
                st.markdown(f"**Priority:** {row['priority']}")
            
            # Find a nearby, lower-priority task
            secondary_task = None
            for j, other_row in filtered_df.iterrows():
                if row['id'] != other_row['id'] and haversine(row['latitude'], row['longitude'], other_row['latitude'], other_row['longitude']) <= 10.0:
                    if (priority_order.index(other_row['priority']) > priority_order.index(row['priority'])):
                         secondary_task = other_row
                         break
            with secondary_task_col:
                if secondary_task is not None:
                     st.success(f"**Suggested Secondary Task:**\n{secondary_task['title']}")
                else:
                     st.text("No nearby secondary task found.")
    
    st.subheader("Job Site Locations")
    st.map(filtered_df, latitude='latitude', longitude='longitude', size=20)

def work_order_detail_view():
    st.subheader("Work Order Details & Logging")
    conn = get_db_connection()
    work_order_list = pd.read_sql_query(
        "SELECT wo.id, wo.title, a.name FROM work_orders wo JOIN assets a ON wo.asset_id = a.id WHERE wo.technician_id = ?",
        conn, params=(TECHNICIAN_ID,))
    
    wo_display_list = [f"{row['id']}: {row['title']} ({row['name']})" for _, row in work_order_list.iterrows()]
    selected_wo_display = st.selectbox("Select a Work Order to view details:", wo_display_list)

    if not selected_wo_display:
        st.warning("Please select a work order."); conn.close(); return

    selected_wo_id = int(selected_wo_display.split(":")[0])
    wo_details = pd.read_sql_query("SELECT * FROM work_orders WHERE id = ?", conn, params=(selected_wo_id,)).iloc[0]

    # NEW: AI Diagnostic Alert and Tribal Knowledge with notification integration
    if wo_details.get('ai_alert_title'):
        st.error(f"**AI Diagnostic Alert:** {wo_details['ai_alert_title']} ({wo_details['ai_confidence']}% confidence)")
        
        # Button to create notification from AI diagnostic
        if st.button("🔔 Create Notification from AI Alert"):
            create_equipment_diagnostic_notification(
                wo_details['title'],
                {
                    'ai_alert_title': wo_details['ai_alert_title'],
                    'ai_confidence': wo_details['ai_confidence'],
                    'tribal_knowledge_note': wo_details['tribal_knowledge_note']
                }
            )
            st.success("Equipment diagnostic notification created!")
            st.rerun()
    
    if wo_details.get('tribal_knowledge_note'):
        st.info(f"**Tribal Knowledge:** {wo_details['tribal_knowledge_note']}")
    
    st.divider()

    st.markdown(f"#### {wo_details['title']}")
    st.markdown(f"**Required Tools:** {wo_details['tools_required']} | **Required Parts:** {wo_details['parts_required']}")
    
    # NEW: "Tap-to-Log" Checklist with notification integration
    st.markdown("#### \"Tap-to-Log\" Checklist")
    checklist_items = ["Safety lockout/tagout", "Visual inspection", "Primary task", "System diagnostics", "Cleanup"]
    
    completed_items = 0
    for item in checklist_items:
        checkbox_key = f"check_{selected_wo_id}_{item.replace(' ', '_')}"
        if st.checkbox(item, key=checkbox_key):
            log_message = f"Checklist item completed: {item}"
            cursor = conn.cursor()
            existing_log = conn.execute("SELECT id FROM logs WHERE work_order_id = ? AND log_text = ?", (selected_wo_id, log_message)).fetchone()
            if not existing_log:
                cursor.execute("INSERT INTO logs (work_order_id, log_text) VALUES (?, ?)", (selected_wo_id, log_message))
                conn.commit()
                st.toast(f"Logged: {item}")
            completed_items += 1
    
    # NEW: Auto-create completion notification when all items checked
    if completed_items == len(checklist_items):
        st.success("🎉 All checklist items completed!")
        if st.button("🔔 Create Completion Notification"):
            create_task_update(
                get_notification_manager(),
                "✅ Work Order Completed",
                f"All checklist items completed for work order: {wo_details['title']}",
                TECHNICIAN_ID,
                "medium",
                {
                    "work_order_id": selected_wo_id,
                    "completion_time": datetime.datetime.now().isoformat(),
                    "completed_items": len(checklist_items)
                }
            )
            st.success("Completion notification created!")
            st.rerun()
    
    # Custom Logging Form (Preserved Feature)
    with st.form("log_form", clear_on_submit=True):
        log_text = st.text_area("Add a custom note or upload a photo:")
        log_photo = st.file_uploader("Upload Photo:", type=['png', 'jpg', 'jpeg'])
        submitted = st.form_submit_button("Save Custom Log")
        if submitted:
            photo_data = log_photo.getvalue() if log_photo else None
            cursor = conn.cursor()
            cursor.execute("INSERT INTO logs (work_order_id, log_text, photo) VALUES (?, ?, ?)", (selected_wo_id, log_text, photo_data))
            conn.commit()
            st.success("Custom log entry saved!")

    # Display Logs
    st.divider()
    st.markdown("#### Activity Log")
    logs_df = pd.read_sql_query("SELECT log_text, photo, strftime('%Y-%m-%d %H:%M', timestamp) as formatted_time FROM logs WHERE work_order_id = ? ORDER BY timestamp DESC", conn, params=(selected_wo_id,))
    if not logs_df.empty:
        for _, log in logs_df.iterrows():
            st.markdown(f"**{log['formatted_time']}**: {log['log_text']}")
            if log['photo']:
                st.image(Image.open(io.BytesIO(log['photo'])), width=200)
    conn.close()

def technician_dashboard_view():
    st.subheader("My Performance Dashboard")
    conn = get_db_connection()
    my_work_orders = pd.read_sql_query("SELECT * FROM work_orders WHERE technician_id = ?", conn, params=(TECHNICIAN_ID,))
    conn.close()

    completed_today = my_work_orders[my_work_orders['status'] == 'Completed'].shape[0] # Simplified for demo
    active_tasks = my_work_orders[my_work_orders['status'] != 'Completed'].shape[0]
    high_priority_tasks = my_work_orders[my_work_orders['priority'] == 'High'].shape[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Tasks Completed (Today)", completed_today)
    col2.metric("Active Tasks", active_tasks)
    col3.metric("High-Priority Tasks", high_priority_tasks)

    st.divider()
    st.markdown("#### Task Completion by Priority")
    if not my_work_orders.empty:
        priority_counts = my_work_orders['priority'].value_counts()
        st.bar_chart(priority_counts)

def manager_dashboard_view():
    st.subheader("Manager: Downtime Cost Savings 📈")
    chart_data = {'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], 'Before WindSync ($)': [55000, 62000, 48000, 51000, 75000, 68000], 'With WindSync ($)': [47000, 52000, 41000, 44000, 63000, 59000]}
    cost_df = pd.DataFrame(chart_data)
    month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    cost_df['Month'] = pd.Categorical(cost_df['Month'], categories=month_order, ordered=True)
    st.bar_chart(cost_df, x='Month', y=['Before WindSync ($)', 'With WindSync ($)'])
    
    # NEW: Manager notification controls
    st.divider()
    st.markdown("#### 📢 Manager Notification Controls")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚨 Send Emergency Broadcast"):
            manager = get_notification_manager()
            technicians = ["tech_007", "tech_008", "tech_009"]
            
            for tech_id in technicians:
                create_safety_alert(
                    manager,
                    "📢 EMERGENCY BROADCAST",
                    "Site-wide emergency declared. All personnel report to muster points immediately.",
                    tech_id,
                    {
                        "broadcast_type": "site_emergency",
                        "muster_point": "Main Office",
                        "sender": "operations_manager"
                    }
                )
            
            st.success(f"Emergency broadcast sent to {len(technicians)} technicians!")
            st.rerun()
    
    with col2:
        if st.button("📋 Send Shift Update"):
            create_task_update(
                get_notification_manager(),
                "📋 Shift Update",
                "New shift assignments have been posted. Check your updated work orders.",
                TECHNICIAN_ID,
                "medium",
                {
                    "update_type": "shift_assignment",
                    "sender": "operations_manager"
                }
            )
            st.success("Shift update notification sent!")
            st.rerun()

def notifications_view():
    """NEW: Dedicated notifications view"""
    st.subheader("🔔 Notifications Center")
    
    manager = get_notification_manager()
    notifications = manager.get_notifications(TECHNICIAN_ID)
    unread_count = manager.get_unread_count(TECHNICIAN_ID)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Notifications", len(notifications))
    with col2:
        st.metric("Unread", unread_count)
    with col3:
        critical_count = len([n for n in notifications if n['priority'] == 'critical'])
        st.metric("Critical", critical_count, delta=None if critical_count == 0 else "⚠️")
    with col4:
        pending_ack = len([n for n in notifications if n['requires_acknowledgment'] and not n['acknowledged_at']])
        st.metric("Pending ACK", pending_ack, delta=None if pending_ack == 0 else "⏳")
    
    if not notifications:
        st.info("No notifications found.")
        return
    
    # Quick actions
    st.markdown("#### Quick Actions")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Mark All as Read"):
            for notification in notifications:
                if not notification['read_at']:
                    manager.mark_as_read(notification['id'], TECHNICIAN_ID)
            st.success("All notifications marked as read!")
            st.rerun()
    
    with col2:
        if st.button("Acknowledge All Critical"):
            for notification in notifications:
                if notification['priority'] == 'critical' and notification['requires_acknowledgment'] and not notification['acknowledged_at']:
                    manager.acknowledge_notification(notification['id'], TECHNICIAN_ID)
            st.success("All critical notifications acknowledged!")
            st.rerun()
    
    with col3:
        critical_unread = [n for n in notifications if n['priority'] == 'critical' and not n['read_at']]
        if critical_unread:
            st.error(f"⚠️ {len(critical_unread)} Critical Unread")
    
    # Filter controls
    col1, col2 = st.columns(2)
    with col1:
        priority_filter = st.multiselect(
            "Filter by Priority:",
            ["critical", "high", "medium", "low"],
            default=["critical", "high", "medium", "low"]
        )
    with col2:
        show_read = st.checkbox("Show Read Notifications", value=True)
    
    # Filter and display notifications
    filtered_notifications = [
        n for n in notifications 
        if n['priority'] in priority_filter and (show_read or not n['read_at'])
    ]
    
    st.markdown(f"#### Notifications ({len(filtered_notifications)} shown)")
    
    for notification in filtered_notifications:
        display_notification_card(manager, notification, TECHNICIAN_ID)

def display_notification_card(manager, notification, technician_id):
    """Display a notification card"""
    priority_colors = {
        'critical': '#dc3545',
        'high': '#fd7e14', 
        'medium': '#ffc107',
        'low': '#28a745'
    }
    
    priority_emojis = {
        'critical': '🚨',
        'high': '⚠️',
        'medium': '📋',
        'low': '💡'
    }
    
    priority = notification['priority']
    
    with st.container():
        st.markdown(f"""
        <div style="
            border-left: 4px solid {priority_colors[priority]};
            padding: 1rem;
            margin: 0.5rem 0;
            background-color: {'#fff5f5' if priority == 'critical' else '#f8f9fa'};
            border-radius: 0 8px 8px 0;
        ">
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"**{priority_emojis[priority]} {notification['title']}**")
            st.markdown(notification['message'])
        
        with col2:
            read_status = "👁️ Read" if notification['read_at'] else "📬 Unread"
            st.markdown(f"**Status:** {read_status}")
            
            created_time = datetime.datetime.fromisoformat(notification['created_at'].replace('Z', '+00:00'))
            st.markdown(f"**Time:** {created_time.strftime('%H:%M')}")
        
        with col3:
            if not notification['read_at']:
                if st.button("Mark Read", key=f"read_{notification['id']}"):
                    manager.mark_as_read(notification['id'], technician_id)
                    st.rerun()
            
            if notification['requires_acknowledgment'] and not notification['acknowledged_at']:
                if st.button("Acknowledge", key=f"ack_{notification['id']}", type="primary"):
                    manager.acknowledge_notification(notification['id'], technician_id)
                    st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)

# --- Main App Router ---
st.title("WindSync Demo")

# NEW: Handle API requests from JavaScript frontend
try:
    query_params = st.query_params
except AttributeError:
    # Fallback for older Streamlit versions
    query_params = st.experimental_get_query_params() if hasattr(st, 'experimental_get_query_params') else {}

# Handle notification API requests
if 'api' in query_params:
    streamlit_api = get_streamlit_api()
    response = streamlit_api.handle_request(query_params)
    if response:
        st.json(response)
        st.stop()

# NEW: Add JavaScript and CSS for notifications
st.markdown("""
<link rel="stylesheet" href="/static/css/notifications.css">
<script src="/static/js/notifications.js"></script>
<script>
// Initialize notifications when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (typeof WindSyncNotifications !== 'undefined') {
        window.windSyncNotifications = new WindSyncNotifications({
            technicianId: 'tech_007',
            developmentMode: true
        });
        window.windSyncNotifications.init();
    }
});
</script>
""", unsafe_allow_html=True)

# Show notification badge in sidebar
show_notification_badge()

st.sidebar.title("Navigation")

# NEW: Added Notifications view to navigation
app_mode = st.sidebar.selectbox("Choose Your View", [
    "Technician: Plan of Day", 
    "Technician: Work Order Details", 
    "Technician: My Dashboard",
    "🔔 Notifications",  # NEW: Added notifications view
    "Manager: Dashboard"
])

st.sidebar.divider()
st.sidebar.markdown("### Demo Controls")
if st.sidebar.button("⚠️ Clear All Log Entries"):
    clear_log_entries()
    st.rerun()

# NEW: Notification system status in sidebar
manager = get_notification_manager()
unread_count = manager.get_unread_count(TECHNICIAN_ID)
if unread_count > 0:
    st.sidebar.markdown(f"### 🔔 Notification Status")
    st.sidebar.markdown(f"**Unread:** {unread_count}")
    
    # Show recent critical notifications
    notifications = manager.get_notifications(TECHNICIAN_ID)
    critical_unread = [n for n in notifications if n['priority'] == 'critical' and not n['read_at']]
    
    if critical_unread:
        st.sidebar.error(f"⚠️ {len(critical_unread)} Critical Alert{'s' if len(critical_unread) != 1 else ''}")
        for notification in critical_unread[:2]:  # Show max 2
            st.sidebar.markdown(f"• {notification['title']}")

# Main content display
if app_mode == "Technician: Plan of Day":
    plan_of_day_view()
elif app_mode == "Technician: Work Order Details":
    work_order_detail_view()
elif app_mode == "Technician: My Dashboard":
    technician_dashboard_view()
elif app_mode == "🔔 Notifications":
    notifications_view()
elif app_mode == "Manager: Dashboard":
    manager_dashboard_view()