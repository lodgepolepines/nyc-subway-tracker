import streamlit as st
import requests
import google.transit.gtfs_realtime_pb2 as gtfs_rt
import time
from datetime import datetime
import pytz
from google.protobuf.message import DecodeError
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
G_TRAIN_FEED = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g"
SEVEN_TRAIN_FEED = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"
EASTERN_TZ = pytz.timezone('America/New_York')

# Station IDs remain the same...
GREENPOINT_AVE_G = "G26N"
GREENPOINT_AVE_G_S = "G26S"
VERNON_JACKSON_7 = "721N"
VERNON_JACKSON_7_S = "721S"

# CSS for the 8-bit train animation and styling
CUSTOM_CSS = """
<style>
    /* Hide Streamlit Menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Import R46 Font */
    @font-face {
        font-family: 'NYCTA-R46';
        src: url('nycta-r46.ttf') format('truetype');
    }

    /* Base MTA Font Stack */
    * {
        font-family: "Helvetica Neue", Helvetica, -apple-system, BlinkMacSystemFont, Arial, sans-serif !important;
    }

    /* Override Streamlit's default fonts */
    .stMarkdown, .stText, h1, h2, h3, p, div {
        font-family: "Helvetica Neue", Helvetica, -apple-system, BlinkMacSystemFont, Arial, sans-serif !important;
    }

    /* Headers */
    h1, h2, h3 {
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }
    
    /* Train animation */
    .train-container {
        width: 100%;
        height: 50px;
        position: relative;
        overflow: hidden;
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
    
    /* LED Display Styling */
    .time-display {
        font-family: 'NYCTA-R46', monospace !important;
        font-size: 20px;
        padding: 8px 12px;
        border-radius: 2px;
        margin: 4px 0;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        background: #000;
        border: 1px solid #333;
        line-height: 1.2;
    }
    
    .g-time { 
        color: #6CBE45;
        text-shadow: 0 0 2px rgba(108, 190, 69, 0.7);
    }
    
    .seven-time { 
        color: #B933AD;
        text-shadow: 0 0 2px rgba(185, 51, 173, 0.7);
    }

    /* Express badge with LED effect */
    .express-badge {
        font-family: 'NYCTA-R46', monospace !important;
        background-color: #B933AD;
        color: #fff;
        padding: 2px 6px;
        border-radius: 2px;
        font-size: 0.8em;
        margin-left: 5px;
        text-shadow: 0 0 2px rgba(255, 255, 255, 0.7);
        display: inline-block;
    }

    /* Subtle scanline effect */
    .time-display::after {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(
            transparent 0%,
            rgba(255, 255, 255, 0.02) 50%,
            transparent 100%
        );
        pointer-events: none;
    }
</style>
"""

TRAIN_HTML = """
<div class="train-container">
    <div class="train">
        🚃🚃🚃🚃🚃🚃🚃🚃
    </div>
</div>
"""

def setup_page():
    st.set_page_config(page_title="MTA Tracker", page_icon="🚇")
    st.title("MTA Tracker")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown(TRAIN_HTML, unsafe_allow_html=True)

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

def is_express_train(trip_update):
    try:
        route_id = trip_update.trip.route_id
        return route_id == "7X" or "..express.." in str(trip_update.trip.trip_id).lower()
    except:
        return False

def convert_to_eastern_time(timestamp):
    """Convert UTC timestamp to Eastern Time."""
    utc_dt = datetime.fromtimestamp(timestamp, pytz.UTC)
    eastern_dt = utc_dt.astimezone(EASTERN_TZ)
    return eastern_dt

def process_train_times(feed, station_ids, line_type):
    """Process train times for specified station IDs and line type"""
    if not feed:
        return []
    
    arrival_times = []
    current_time = int(time.time())
    
    try:
        for entity in feed.entity:
            if entity.HasField('trip_update'):
                update = entity.trip_update
                for stop_time in update.stop_time_update:
                    if stop_time.stop_id in station_ids:
                        if stop_time.HasField('arrival'):
                            arrival_time = stop_time.arrival.time
                            if arrival_time > current_time:
                                if line_type == 'G' and stop_time.stop_id.endswith('N'):
                                    continue
                                    
                                direction = "Church Ave-bound" if line_type == 'G' else \
                                          "Manhattan-bound" if stop_time.stop_id.endswith('N') else "Flushing-bound"
                                
                                is_express = is_express_train(update)
                                arrival_times.append((arrival_time, direction, is_express))
        
        if line_type == '7':
            manhattan_bound = [(t, d, e) for t, d, e in arrival_times if d == "Manhattan-bound"]
            flushing_bound = [(t, d, e) for t, d, e in arrival_times if d == "Flushing-bound"]
            
            manhattan_bound.sort(key=lambda x: x[0])
            flushing_bound.sort(key=lambda x: x[0])
            
            return manhattan_bound[:3] + flushing_bound[:3]
        else:
            return sorted(arrival_times, key=lambda x: x[0])[:6]
    
    except Exception as e:
        logger.error(f"Error processing times: {e}")
        return []

def display_train_times(times, station_name, train_line):
    css_class = "g-time" if train_line == "G" else "seven-time"
    line_color = "#6CBE45" if train_line == "G" else "#B933AD"
    
    st.markdown(f'<h3 style="color: {line_color};">{train_line} Train - {station_name}</h3>', unsafe_allow_html=True)
    
    if not times:
        st.markdown(f'<div class="{css_class} time-display">No upcoming trains</div>', unsafe_allow_html=True)
    else:
        for arrival_time, direction, is_express in times:
            eastern_time = convert_to_eastern_time(arrival_time)
            time_str = eastern_time.strftime("%I:%M %p").lstrip("0").lower()
            express_badge = '<span class="express-badge">EXPRESS</span>' if is_express else ''
            st.markdown(
                f'<div class="{css_class} time-display">{direction} - {time_str} {express_badge}</div>',
                unsafe_allow_html=True
            )

def update_displays():
    with st.spinner("Loading train data..."):
        g_feed = fetch_feed(G_TRAIN_FEED)
        seven_feed = fetch_feed(SEVEN_TRAIN_FEED)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if g_feed:
            g_times = process_train_times(g_feed, [GREENPOINT_AVE_G_S], 'G')
            display_train_times(g_times, "Greenpoint Ave", "G")
    
    with col2:
        if seven_feed:
            seven_times = process_train_times(seven_feed, [VERNON_JACKSON_7, VERNON_JACKSON_7_S], '7')
            display_train_times(seven_times, "Vernon-Jackson", "7")
    
    current_eastern = datetime.now(EASTERN_TZ)
    st.markdown(f"Last updated: {current_eastern.strftime('%I:%M:%S %p %Z')}")

def main():
    setup_page()
    
    try:
        placeholder = st.empty()
        while True:
            with placeholder.container():
                update_displays()
            time.sleep(30)
            placeholder.empty()
    
    except Exception as e:
        logger.error(f"Main loop error: {e}")
        st.error("An error occurred. Please try again.")

if __name__ == "__main__":
    main()