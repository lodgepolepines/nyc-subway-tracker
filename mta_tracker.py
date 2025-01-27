import streamlit as st
import requests
import google.transit.gtfs_realtime_pb2 as gtfs_rt
import time
from datetime import datetime
from google.protobuf.message import DecodeError
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
G_TRAIN_FEED = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g"
SEVEN_TRAIN_FEED = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"

# Station IDs
GREENPOINT_AVE_G = "G26N"  # Northbound
GREENPOINT_AVE_G_S = "G26S"  # Southbound
VERNON_JACKSON_7 = "721N"  # Manhattan-bound
VERNON_JACKSON_7_S = "721S"  # Flushing-bound

# CSS for the 8-bit train animation and styling
CUSTOM_CSS = """
<style>
    .train-container {
        width: 100%;
        height: 50px;
        position: relative;
        overflow: hidden;
        margin: 20px 0;
    }
    
    .train {
        position: absolute;
        left: -50px;
        font-size: 24px;
        animation: moveRight 10s infinite;
    }
    
    @keyframes moveRight {
        0% { left: -50px; }
        40% { left: 45%; }
        60% { left: 45%; }
        100% { left: 100%; }
    }
    
    .g-train { color: #6CBE45; }
    .seven-train { color: #B933AD; }
    
    .train-header {
        font-family: 'Courier New', monospace;
        font-size: 24px;
    }
    
    .time-display {
        padding: 5px 10px;
        border-radius: 5px;
        margin: 2px 0;
    }
    
    .g-time { background-color: rgba(108, 190, 69, 0.1); }
    .seven-time { background-color: rgba(185, 51, 173, 0.1); }
</style>
"""

# 8-bit style train ASCII art
TRAIN_HTML = """
<div class="train-container">
    <div class="train">
        🚃🚃🚃🚃🚃🚃🚃🚃
    </div>
</div>
"""

def setup_page():
    st.set_page_config(page_title="NYC Subway Tracker - G & 7 Lines", page_icon="🚇")
    st.title("NYC Subway Tracker")
    
    # Insert custom CSS and train animation
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown(TRAIN_HTML, unsafe_allow_html=True)
    
    st.subheader("G & 7 Lines at Greenpoint Ave and Vernon-Jackson")

def fetch_feed(url):
    headers = {
        'Accept': 'application/x-google-protobuf',
        'User-Agent': 'Mozilla/5.0'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Feed response: status={response.status_code}, "
                   f"content-type={response.headers.get('content-type')}, "
                   f"length={len(response.content)}")
        
        feed = gtfs_rt.FeedMessage()
        try:
            feed.ParseFromString(response.content)
            return feed
        except DecodeError as e:
            logger.error(f"Protobuf decode error: {e}")
            st.error(f"Error decoding transit data")
            return None
            
    except Exception as e:
        logger.error(f"Feed fetch error: {e}")
        st.error("Unable to fetch transit data")
        return None

def process_train_times(feed, station_id):
    if not feed:
        return []
    
    arrival_times = []
    current_time = int(time.time())
    
    try:
        for entity in feed.entity:
            if entity.HasField('trip_update'):
                update = entity.trip_update
                for stop_time in update.stop_time_update:
                    if stop_time.stop_id == station_id:
                        if stop_time.HasField('arrival'):
                            arrival_time = stop_time.arrival.time
                            if arrival_time > current_time:
                                minutes_away = (arrival_time - current_time) // 60
                                if 0 <= minutes_away <= 120:
                                    arrival_times.append(minutes_away)
        
        return sorted(arrival_times)[:3]
    
    except Exception as e:
        logger.error(f"Error processing times: {e}")
        return []

def display_train_times(times, station_name, direction, train_line):
    # Define CSS class based on train line
    css_class = "g-time" if train_line == "G" else "seven-time"
    line_color = "#6CBE45" if train_line == "G" else "#B933AD"
    
    st.markdown(f'<h3 style="color: {line_color};">{train_line} Train - {station_name}</h3>', unsafe_allow_html=True)
    st.markdown(f'<p style="color: {line_color};">{direction}</p>', unsafe_allow_html=True)
    
    if not times:
        st.markdown(f'<div class="{css_class} time-display">No upcoming trains</div>', unsafe_allow_html=True)
    else:
        for i, minutes in enumerate(times, 1):
            st.markdown(
                f'<div class="{css_class} time-display">Train {i}: {minutes} minutes away</div>',
                unsafe_allow_html=True
            )

def update_displays():
    with st.spinner("Loading train data..."):
        g_feed = fetch_feed(G_TRAIN_FEED)
        seven_feed = fetch_feed(SEVEN_TRAIN_FEED)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if g_feed:
            g_north = process_train_times(g_feed, GREENPOINT_AVE_G)
            g_south = process_train_times(g_feed, GREENPOINT_AVE_G_S)
            display_train_times(g_north, "Greenpoint Ave", "Northbound (Court Sq)", "G")
            display_train_times(g_south, "Greenpoint Ave", "Southbound (Church Ave)", "G")
    
    with col2:
        if seven_feed:
            seven_manhattan = process_train_times(seven_feed, VERNON_JACKSON_7)
            seven_flushing = process_train_times(seven_feed, VERNON_JACKSON_7_S)
            display_train_times(seven_manhattan, "Vernon-Jackson", "Manhattan-bound", "7")
            display_train_times(seven_flushing, "Vernon-Jackson", "Flushing-bound", "7")
    
    st.markdown(f"Last updated: {datetime.now().strftime('%I:%M:%S %p')}")

def main():
    setup_page()
    
    debug_mode = st.sidebar.checkbox("Debug Mode")
    if debug_mode:
        logger.setLevel(logging.DEBUG)
    
    auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=True)
    
    try:
        if auto_refresh:
            placeholder = st.empty()
            while True:
                with placeholder.container():
                    update_displays()
                time.sleep(30)
                placeholder.empty()
        else:
            update_displays()
    
    except Exception as e:
        logger.error(f"Main loop error: {e}")
        st.error("An error occurred. Please try again.")

if __name__ == "__main__":
    main()