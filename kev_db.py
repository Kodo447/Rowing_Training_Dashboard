import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime

# Page confi
st.set_page_config(
    page_title="Rowing Training Dashboard",
    page_icon="🚣",
    layout="wide"
)

# Your Google Sheets URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ka1T_HJo7W6C20gWn3VfcNmYTTij24lWwfHyxeBenVc/edit?gid=477886919#gid=477886919"
whoop_URl ="https://docs.google.com/spreadsheets/d/1ka1T_HJo7W6C20gWn3VfcNmYTTij24lWwfHyxeBenVc/edit?gid=355675609#gid=355675609"
intervals_URL = "https://docs.google.com/spreadsheets/d/1ka1T_HJo7W6C20gWn3VfcNmYTTij24lWwfHyxeBenVc/edit?gid=1473267175#gid=1473267175"
strava_URL = "https://docs.google.com/spreadsheets/d/1ka1T_HJo7W6C20gWn3VfcNmYTTij24lWwfHyxeBenVc/edit?gid=543202266#gid=543202266"
@st.cache_data
def load_data_from_sheets(url):
    """Load data from Google Sheets using the share link"""
    sheet_id = url.split('/d/')[1].split('/')[0]
    gid = url.split('gid=')[1].split('#')[0] if 'gid=' in url else '0'
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    
    df = pd.read_csv(csv_url)
    return df

if st.button("🔄 Refresh data"):
    st.cache_data.clear()

# region Load and display the data
whoop_df = load_data_from_sheets(whoop_URl)
whoop_df["date"] = pd.to_datetime(whoop_df["date"]).dt.normalize()
whoop_df["recovery"] = pd.to_numeric(whoop_df["recovery"], errors='coerce')
whoop_df["hrv"] = pd.to_numeric(whoop_df["hrv"], errors='coerce')
whoop_df["sleep_hours"] = pd.to_numeric(whoop_df["sleep_hours"], errors='coerce')
whoop_df["sleep_hours"]= whoop_df["sleep_hours"]/60  # Convert minutes to hours
df = load_data_from_sheets(SHEET_URL)
df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors='coerce')
intervals_df = load_data_from_sheets(intervals_URL)
intervals_df["date"] = pd.to_datetime(intervals_df["session_id"].str.split("_").str[0], format="%Y%m%d", errors='coerce')
strava_df = load_data_from_sheets(strava_URL)
strava_df["date"] = pd.to_datetime(strava_df["activity_start_date"]).dt.tz_localize(None).dt.normalize()
strava_df["activity.distance"] = pd.to_numeric(strava_df["activity.distance"], errors='coerce')
strava_df = strava_df[strava_df["activity.distance"] != 0]
st.title("Rowing Training Dashboard")
# end region


# Choose filter mode: date-range or week navigation
use_week_filter = st.checkbox("Filter by week (use arrow buttons to change weeks)", value=False)

if use_week_filter:
    # initialize current week start (Monday) in session state
    if 'current_week_start' not in st.session_state:
        min_date = df['date'].min()
        monday = (min_date - pd.Timedelta(days=int(min_date.weekday()))).normalize()
        st.session_state['current_week_start'] = monday

    nav_left, nav_center, nav_right = st.columns([1,6,1])

    if nav_left.button('◀'):
        st.session_state['current_week_start'] = st.session_state['current_week_start'] - pd.Timedelta(days=7)

    week_start = st.session_state['current_week_start']
    week_end = (week_start + pd.Timedelta(days=6)).normalize()
    nav_center.markdown(f"**Week:** {week_start.date()} — {week_end.date()} (ISO {week_start.isocalendar().week})")

    if nav_right.button('▶'):
        st.session_state['current_week_start'] = st.session_state['current_week_start'] + pd.Timedelta(days=7)

    # Clamp week within dataset bounds
    min_allowed = df['date'].min().normalize()
    max_allowed = df['date'].max().normalize()
    if st.session_state['current_week_start'] < (min_allowed - pd.Timedelta(days=6)):
        st.session_state['current_week_start'] = (min_allowed - pd.Timedelta(days=int(min_allowed.weekday()))).normalize()
    if st.session_state['current_week_start'] > max_allowed:
        st.session_state['current_week_start'] = (max_allowed - pd.Timedelta(days=int(max_allowed.weekday()))).normalize()

    start_date = st.session_state['current_week_start']
    end_date = (start_date + pd.Timedelta(days=6)).date() if hasattr(start_date, 'date') else (start_date + pd.Timedelta(days=6))
    week_number = [start_date.isocalendar().week]
else:
    col1, col2, col3 = st.columns(3)

    with col1:
        start_date = st.date_input("Start Date", value=df["date"].min())

    with col2:
        end_date = st.date_input("End Date", value=df["date"].max())

    with col3:
        week_number = st.multiselect("Week Number", options=sorted(df["date"].dt.isocalendar().week.unique()))

# Filter data
df_filtered = df[(df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))]

if week_number:
    df_filtered = df_filtered[df_filtered["date"].dt.isocalendar().week.isin(week_number)]

df = df_filtered

mask = whoop_df["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
whoop_df_filtered = whoop_df.loc[mask]
if week_number:
    whoop_df_filtered = whoop_df_filtered[whoop_df_filtered["date"].dt.isocalendar().week.isin(week_number)]

#strave filter
mask_strava = strava_df["date"].between(pd.Timestamp(start_date), pd.Timestamp(end_date))
strava_df_filtered = strava_df.loc[mask_strava]
if week_number:
    strava_df_filtered = strava_df_filtered[strava_df_filtered["date"].dt.isocalendar().week.isin(week_number)]

col1, col2, col3,col4 = st.columns(4)

col1.metric(
    label="Total Distance Rowed",
    value=f"{df['distance_m'].sum()+strava_df_filtered['activity.distance'].sum():,.0f} m"
)

col2.metric(
    label="Avg Sleep",
    value=f"{whoop_df_filtered['sleep_hours'].mean():.1f} hrs"
)

col3.metric(
    label="Avg Recovery",
    value=f"{whoop_df_filtered['recovery'].mean():.0f} %"
)

col4.metric(
    label="Average HRV",
    value=f"{whoop_df_filtered['hrv'].mean():.0f} ms"
)

st.dataframe(strava_df_filtered)

#region Main Table
# select box: choose a session to view its intervals
selected_session = st.selectbox("Select Session ID", options=df["session_id"].unique())

def get_intervals_for_session(session_id):
    """Return intervals rows for a given session_id."""
    return intervals_df[intervals_df['session_id'] == session_id]
#convert seconds per 500 to splite time format
def seconds_to_split(seconds):
    if pd.isna(seconds):
        return "N/A"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    tenths = int((seconds - int(seconds)) * 10)
    return f"{minutes}:{secs:02d}.{tenths}"
df['split_time'] = df['avg_split_500m'].apply(seconds_to_split)
main_table = pd.DataFrame({"Date": df["date"].dt.date, "Weekday": df["date"].dt.day_name(), "Workout Type": df["workout_type"], "Workout Subtype": df["workout_subtype"], "Distance (m)": df["distance_m"], "Split Time": df["split_time"]
                           ,"Notes": df["notes"]})
st.dataframe(main_table)
# end region

# Show intervals for selected session (if any)
if selected_session:
    intervals_for_session = get_intervals_for_session(selected_session)
    if not intervals_for_session.empty:
        st.subheader(f"Intervals for {selected_session}")
        st.dataframe(intervals_for_session)
    else:
        st.info("No intervals found for selected session.")

col1, col2 = st.columns(2)

#df for bar chart 
strava_df_filtered_subset = strava_df_filtered[['date', 'activity.distance']].copy()
strava_df_filtered_subset = strava_df_filtered_subset.rename(columns={'activity.distance': 'distance_m'})
strava_df_filtered_subset['workout_type'] = 'Strava' 
bar_chart_df = pd.concat([df[['date', 'distance_m', 'workout_type']], strava_df_filtered_subset], ignore_index=True)

with col2:
    bar_chart = px.bar(bar_chart_df, x='date', y='distance_m', title='Distance Rowed Over Time',
                 color="workout_type")

    st.plotly_chart(bar_chart)

# Recovery over time

line_chart = px.line(whoop_df_filtered, x='date', y='recovery', title='Recovery Over Time',
                 markers=True)
line_chart.update_yaxes(range=[0, 100])

# Build per-point colors: green when recovery > threshold, otherwise default blue
colors = []
for r in whoop_df_filtered['recovery']:
    if r is None:
        colors.append("gray")
    elif r > 66:
        colors.append("green")
    elif r > 33:
        colors.append("orange")
    else:  # r <= 0.33
        colors.append("red")

   

with col1:
    line_chart.update_traces(marker=dict(color=colors, size=12,symbol ="cross"), line=dict(color='blue'))

    st.plotly_chart((line_chart))

