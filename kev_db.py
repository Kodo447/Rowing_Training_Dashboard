import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime

try:
    # Enables click events on Plotly charts
    from streamlit_plotly_events import plotly_events
except ImportError:  # graceful fallback if not installed
    plotly_events = None

# Page config
st.set_page_config(
    page_title="Rowing Training Dashboard",
    page_icon="🚣",
    layout="wide"
)

# Google Sheets URLs
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ka1T_HJo7W6C20gWn3VfcNmYTTij24lWwfHyxeBenVc/edit?gid=477886919#gid=477886919"
whoop_URl = "https://docs.google.com/spreadsheets/d/1ka1T_HJo7W6C20gWn3VfcNmYTTij24lWwfHyxeBenVc/edit?gid=355675609#gid=355675609"
intervals_URL = "https://docs.google.com/spreadsheets/d/1ka1T_HJo7W6C20gWn3VfcNmYTTij24lWwfHyxeBenVc/edit?gid=1473267175#gid=1473267175"
strava_URL = "https://docs.google.com/spreadsheets/d/1ka1T_HJo7W6C20gWn3VfcNmYTTij24lWwfHyxeBenVc/edit?gid=543202266#gid=543202266"
weights_URL = "https://docs.google.com/spreadsheets/d/1ka1T_HJo7W6C20gWn3VfcNmYTTij24lWwfHyxeBenVc/edit?gid=2001405235#gid=2001405235"


@st.cache_data
def load_data_from_sheets(url):
    """Load data from Google Sheets using the share link."""
    sheet_id = url.split("/d/")[1].split("/")[0]
    gid = url.split("gid=")[1].split("#")[0] if "gid=" in url else "0"
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

    df = pd.read_csv(csv_url)
    return df


if st.button("🔄 Refresh data"):
    st.cache_data.clear()

# region Load data
whoop_df = load_data_from_sheets(whoop_URl)
whoop_df["date"] = pd.to_datetime(whoop_df["date"]).dt.normalize()
whoop_df["recovery"] = pd.to_numeric(whoop_df["recovery"], errors="coerce")
whoop_df["hrv"] = pd.to_numeric(whoop_df["hrv"], errors="coerce")
whoop_df["sleep_hours"] = pd.to_numeric(whoop_df["sleep_hours"], errors="coerce")
whoop_df["sleep_hours"] = whoop_df["sleep_hours"] / 60  # Convert minutes to hours

df = load_data_from_sheets(SHEET_URL)
df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")

intervals_df = load_data_from_sheets(intervals_URL)
intervals_df["date"] = pd.to_datetime(
    intervals_df["session_id"].str.split("_").str[0],
    format="%Y%m%d",
    errors="coerce",
)

strava_df = load_data_from_sheets(strava_URL)
strava_df["date"] = (
    pd.to_datetime(strava_df["activity_start_date"])
    .dt.tz_localize(None)
    .dt.normalize()
)
strava_df["activity.distance"] = pd.to_numeric(
    strava_df["activity.distance"], errors="coerce"
)
strava_df = strava_df[strava_df["activity.distance"] != 0]

weights_df = load_data_from_sheets(weights_URL)
weights_df["date"] = pd.to_datetime(
    weights_df["session_id"].astype(str).str.split("_").str[0],
    format="%Y%m%d",
    errors="coerce",
)
for col in ["set", "reps", "weight_kg", "rpe"]:
    if col in weights_df.columns:
        weights_df[col] = pd.to_numeric(weights_df[col], errors="coerce")

st.title("Rowing Training Dashboard")
# end region

tab_rowing, tab_weights = st.tabs(["Rowing & Recovery", "Weights Training"])

with tab_rowing:
    # Choose filter mode: date-range or week navigation
    use_week_filter = st.checkbox(
        "Filter by week (use arrow buttons to change weeks)", value=True
    )
    selected_week_labels = []

    if use_week_filter:
        # initialize current week start (Monday) in session state
        if "current_week_initialized_v2" not in st.session_state:
            today = pd.Timestamp.today().normalize()
            min_date = df["date"].min().normalize()
            max_date = df["date"].max().normalize()

            # Clamp today's date into the dataset range
            if today < min_date:
                base_date = min_date
            elif today > max_date:
                base_date = max_date
            else:
                base_date = today

            monday = (
                base_date - pd.Timedelta(days=int(base_date.weekday()))
            ).normalize()
            st.session_state["current_week_start"] = monday
            st.session_state["current_week_initialized_v2"] = True

        nav_left, nav_center, nav_right = st.columns([1, 6, 1])

        if nav_left.button("◀"):
            st.session_state["current_week_start"] = (
                st.session_state["current_week_start"] - pd.Timedelta(days=7)
            )

        week_start = st.session_state["current_week_start"]
        week_end = (week_start + pd.Timedelta(days=6)).normalize()
        nav_center.markdown(
            f"**Week:** {week_start.date()} — {week_end.date()} (ISO {week_start.isocalendar().week})"
        )

        if nav_right.button("▶"):
            st.session_state["current_week_start"] = (
                st.session_state["current_week_start"] + pd.Timedelta(days=7)
            )

        # Clamp week within dataset bounds
        min_allowed = df["date"].min().normalize()
        max_allowed = df["date"].max().normalize()
        if st.session_state["current_week_start"] < (
            min_allowed - pd.Timedelta(days=6)
        ):
            st.session_state["current_week_start"] = (
                min_allowed - pd.Timedelta(days=int(min_allowed.weekday()))
            ).normalize()
        if st.session_state["current_week_start"] > max_allowed:
            st.session_state["current_week_start"] = (
                max_allowed - pd.Timedelta(days=int(max_allowed.weekday()))
            ).normalize()

        start_date = st.session_state["current_week_start"]
        end_date = (
            (start_date + pd.Timedelta(days=6)).date()
            if hasattr(start_date, "date")
            else (start_date + pd.Timedelta(days=6))
        )
        # Date range already pins us to a single calendar week
    else:
        col1, col2, col3 = st.columns(3)

        with col1:
            start_date = st.date_input("Start Date", value=df["date"].min())

        with col2:
            end_date = st.date_input("End Date", value=df["date"].max())

        with col3:
            iso = df["date"].dt.isocalendar()
            week_keys = (
                pd.DataFrame({"year": iso["year"], "week": iso["week"]})
                .dropna()
                .drop_duplicates()
                .sort_values(["year", "week"])
            )
            week_options = (
                week_keys["year"].astype(str)
                + "-W"
                + week_keys["week"].astype(int).astype(str).str.zfill(2)
            ).tolist()
            selected_week_labels = st.multiselect(
                "Week (year-week)",
                options=week_options,
            )

    # Filter data
    df_filtered = df[
        (df["date"] >= pd.Timestamp(start_date))
        & (df["date"] <= pd.Timestamp(end_date))
    ]

    if selected_week_labels:
        iso_f = df_filtered["date"].dt.isocalendar()
        labels_f = (
            iso_f["year"].astype(str)
            + "-W"
            + iso_f["week"].astype(int).astype(str).str.zfill(2)
        )
        df_filtered = df_filtered[labels_f.isin(selected_week_labels)]

    df = df_filtered

    mask = whoop_df["date"].between(
        pd.Timestamp(start_date), pd.Timestamp(end_date)
    )
    whoop_df_filtered = whoop_df.loc[mask]
    if selected_week_labels:
        iso_w = whoop_df_filtered["date"].dt.isocalendar()
        labels_w = (
            iso_w["year"].astype(str)
            + "-W"
            + iso_w["week"].astype(int).astype(str).str.zfill(2)
        )
        whoop_df_filtered = whoop_df_filtered[labels_w.isin(selected_week_labels)]

    # Strava filter
    mask_strava = strava_df["date"].between(
        pd.Timestamp(start_date), pd.Timestamp(end_date)
    )
    strava_df_filtered = strava_df.loc[mask_strava]
    if selected_week_labels:
        iso_s = strava_df_filtered["date"].dt.isocalendar()
        labels_s = (
            iso_s["year"].astype(str)
            + "-W"
            + iso_s["week"].astype(int).astype(str).str.zfill(2)
        )
        strava_df_filtered = strava_df_filtered[labels_s.isin(selected_week_labels)]

    # Session summary cards
    # Rowing (erg/rp3/bike/etc.) from df, Strava activities, and weights sessions
    rowing_sessions = df["session_id"].nunique()
    # Treat erg and rp3 as "erg" sessions
    erg_sessions = df[df["workout_type"].isin(["erg", "rp3"])]["session_id"].nunique()
    bike_sessions = df[df["workout_type"] == "bike"]["session_id"].nunique()

    # Strava "row" sessions: count filtered rows (one per activity)
    row_strava_sessions = len(strava_df_filtered)

    # Weights sessions in the same date range/week filters
    weights_row_summary = weights_df[
        (weights_df["date"] >= pd.Timestamp(start_date))
        & (weights_df["date"] <= pd.Timestamp(end_date))
    ].copy()
    if selected_week_labels:
        iso_wr_cards = weights_row_summary["date"].dt.isocalendar()
        labels_wr_cards = (
            iso_wr_cards["year"].astype(str)
            + "-W"
            + iso_wr_cards["week"].astype(int).astype(str).str.zfill(2)
        )
        weights_row_summary = weights_row_summary[
            labels_wr_cards.isin(selected_week_labels)
        ]
    weights_sessions = weights_row_summary["session_id"].nunique()

    total_sessions = rowing_sessions + row_strava_sessions + weights_sessions

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Total Sessions", int(total_sessions))
    s2.metric("Weights Sessions", int(weights_sessions))
    s3.metric("Erg Sessions", int(erg_sessions))
    s4.metric("Row (Strava) Sessions", int(row_strava_sessions))
    s5.metric("Bike Sessions", int(bike_sessions))

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        label="Total Distance Rowed",
        value=f"{df['distance_m'].sum() + strava_df_filtered['activity.distance'].sum():,.0f} m",
    )

    col2.metric(
        label="Avg Sleep",
        value=f"{whoop_df_filtered['sleep_hours'].mean():.1f} hrs",
    )

    col3.metric(
        label="Avg Recovery",
        value=f"{whoop_df_filtered['recovery'].mean():.0f} %",
    )

    col4.metric(
        label="Average HRV",
        value=f"{whoop_df_filtered['hrv'].mean():.0f} ms",
    )

    st.dataframe(strava_df_filtered)

    # region Main Table
    # select box: choose a session to view its intervals
    selected_session = st.selectbox(
        "Select Session ID", options=df["session_id"].unique()
    )

    def get_intervals_for_session(session_id):
        """Return intervals rows for a given session_id."""
        return intervals_df[intervals_df["session_id"] == session_id]

    # convert seconds per 500 to split time format
    def seconds_to_split(seconds):
        if pd.isna(seconds):
            return "N/A"
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        tenths = int((seconds - int(seconds)) * 10)
        return f"{minutes}:{secs:02d}.{tenths}"

    df["split_time"] = df["avg_split_500m"].apply(seconds_to_split)

    # Base rowing main table
    main_table = pd.DataFrame(
        {
            "Date": df["date"].dt.date,
            "Weekday": df["date"].dt.day_name(),
            "Workout Type": df["workout_type"],
            "Workout Subtype": df["workout_subtype"],
            "Distance (m)": df["distance_m"],
            "Split Time": df["split_time"],
            "Notes": df["notes"],
        }
    )

    # Add weights sessions as line items
    weights_row_filtered = weights_df[
        (weights_df["date"] >= pd.Timestamp(start_date))
        & (weights_df["date"] <= pd.Timestamp(end_date))
    ].copy()
    if selected_week_labels:
        iso_wr = weights_row_filtered["date"].dt.isocalendar()
        labels_wr = (
            iso_wr["year"].astype(str)
            + "-W"
            + iso_wr["week"].astype(int).astype(str).str.zfill(2)
        )
        weights_row_filtered = weights_row_filtered[labels_wr.isin(selected_week_labels)]

    if not weights_row_filtered.empty:
        session_summary = (
            weights_row_filtered.assign(
                session_volume=weights_row_filtered["weight_kg"]
                * weights_row_filtered["reps"]
            )
            .groupby(["date", "session_id"])
            .agg(
                total_sets=("set", "count"),
                total_reps=("reps", "sum"),
                volume_kg=("session_volume", "sum"),
                avg_rpe=("rpe", "mean"),
            )
            .reset_index()
        )

        weights_rows = pd.DataFrame(
            {
                "Date": session_summary["date"].dt.date,
                "Weekday": session_summary["date"].dt.day_name(),
                "Workout Type": ["Weights"] * len(session_summary),
                "Workout Subtype": ["Gym"] * len(session_summary),
                "Distance (m)": [None] * len(session_summary),
                "Split Time": ["N/A"] * len(session_summary),
                "Notes": session_summary.apply(
                    lambda r: f"Weights session: {r.total_sets} sets, {r.total_reps} reps, {r.volume_kg:.0f} kg, avg RPE {r.avg_rpe:.1f}",
                    axis=1,
                ),
            }
        )

        main_table = pd.concat([main_table, weights_rows], ignore_index=True)

    # Show combined table
    st.dataframe(
        main_table.sort_values(["Date", "Weekday", "Workout Type"]),
        use_container_width=True,
    )
    # end region

    # Show intervals for selected session (if any)
    if selected_session:
        intervals_for_session = get_intervals_for_session(selected_session)
        if not intervals_for_session.empty:
            st.subheader(f"Intervals for {selected_session}")

            intervals_display = intervals_for_session.copy()

            # Convert any numeric "split" columns to mm:ss.x (rowing split) format
            split_cols = [
                c
                for c in intervals_display.columns
                if "split" in str(c).lower()
            ]

            def format_split_value(val):
                if pd.isna(val):
                    return "N/A"
                try:
                    seconds = float(val)
                except (TypeError, ValueError):
                    return val
                minutes = int(seconds) // 60
                secs = int(seconds) % 60
                tenths = int(round((seconds - int(seconds)) * 10))
                return f"{minutes}:{secs:02d}.{tenths}"

            for col in split_cols:
                if pd.api.types.is_numeric_dtype(intervals_display[col]):
                    intervals_display[col] = intervals_display[col].apply(
                        format_split_value
                    )

            st.dataframe(intervals_display)
        else:
            st.info("No intervals found for selected session.")

    col1, col2 = st.columns(2)

    # df for bar chart
    strava_df_filtered_subset = strava_df_filtered[
        ["date", "activity.distance"]
    ].copy()
    strava_df_filtered_subset = strava_df_filtered_subset.rename(
        columns={"activity.distance": "distance_m"}
    )
    strava_df_filtered_subset["workout_type"] = "Strava"
    bar_chart_df = pd.concat(
        [df[["date", "distance_m", "workout_type"]], strava_df_filtered_subset],
        ignore_index=True,
    )

    with col2:
        bar_chart = px.bar(
            bar_chart_df,
            x="date",
            y="distance_m",
            title="Distance Rowed Over Time",
            color="workout_type",
        )

        st.plotly_chart(bar_chart)

    # Recovery over time
    line_chart = px.line(
        whoop_df_filtered,
        x="date",
        y="recovery",
        title="Recovery Over Time",
        markers=True,
    )
    line_chart.update_yaxes(range=[0, 100])

    # Build per-point colors: green when recovery > threshold, otherwise default
    colors = []
    for r in whoop_df_filtered["recovery"]:
        if r is None:
            colors.append("gray")
        elif r > 66:
            colors.append("green")
        elif r > 33:
            colors.append("orange")
        else:
            colors.append("red")

    with col1:
        line_chart.update_traces(
            marker=dict(color=colors, size=12, symbol="cross"),
            line=dict(color="blue"),
        )

        st.plotly_chart(line_chart)

with tab_weights:
    st.subheader("Weights Training Analysis")

    if "date" not in weights_df.columns or weights_df["date"].dropna().empty:
        st.info("No weights data available.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            w_start = st.date_input(
                "Start Date",
                value=weights_df["date"].min().date(),
                key="weights_start",
            )
        with col2:
            w_end = st.date_input(
                "End Date",
                value=weights_df["date"].max().date(),
                key="weights_end",
            )

        weights_filtered = weights_df[
            (weights_df["date"] >= pd.Timestamp(w_start))
            & (weights_df["date"] <= pd.Timestamp(w_end))
        ].copy()

        exercises = sorted(
            weights_filtered["exercise"].dropna().unique()
        )
        selected_exercises = st.multiselect(
            "Exercise filter",
            options=exercises,
            default=exercises,
        )
        if selected_exercises:
            weights_filtered = weights_filtered[
                weights_filtered["exercise"].isin(selected_exercises)
            ]

        if weights_filtered.empty:
            st.info("No weights sessions found for the selected filters.")
        else:
            # Summary metrics
            m1, m2, m3, m4 = st.columns(4)

            total_sessions = weights_filtered["session_id"].nunique()
            total_sets = weights_filtered["set"].sum()
            total_reps = weights_filtered["reps"].sum()
            total_volume = (weights_filtered["weight_kg"] * weights_filtered["reps"]).sum()
            avg_rpe = weights_filtered["rpe"].mean()

            m1.metric("Sessions", int(total_sessions))
            m2.metric("Total Volume (kg)", f"{total_volume:,.0f}")
            m3.metric("Total Reps", int(total_reps))
            m4.metric(
                "Average RPE",
                f"{avg_rpe:.1f}" if pd.notna(avg_rpe) else "N/A",
            )

            # Volume over time
            col_a, col_b = st.columns(2)

            volume_by_day = (
                weights_filtered.assign(
                    session_volume=weights_filtered["weight_kg"]
                    * weights_filtered["reps"]
                )
                .groupby("date")["session_volume"]
                .sum()
                .reset_index(name="volume_kg")
            )

            with col_a:
                fig_day = px.bar(
                    volume_by_day,
                    x="date",
                    y="volume_kg",
                    title="Total Volume per Day",
                )
                fig_day.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Volume (kg)",
                )

                if plotly_events is not None:
                    # Capture clicks on daily volume bars
                    clicked_points = plotly_events(
                        fig_day,
                        click_event=True,
                        select_event=False,
                        hover_event=False,
                        key="weights_volume_click",
                    )
                    if clicked_points:
                        idx = clicked_points[0]["pointIndex"]
                        clicked_date = volume_by_day.iloc[idx]["date"].date()
                        st.session_state["weights_session_date"] = clicked_date
                else:
                    st.plotly_chart(fig_day, use_container_width=True)

            # Volume by exercise
            volume_by_exercise = (
                weights_filtered.assign(
                    session_volume=weights_filtered["weight_kg"]
                    * weights_filtered["reps"]
                )
                .groupby("exercise")["session_volume"]
                .sum()
                .reset_index(name="volume_kg")
                .sort_values("volume_kg", ascending=True)
            )

            with col_b:
                fig_ex = px.bar(
                    volume_by_exercise,
                    x="volume_kg",
                    y="exercise",
                    orientation="h",
                    title="Volume by Exercise",
                )
                fig_ex.update_layout(
                    xaxis_title="Volume (kg)",
                    yaxis_title="Exercise",
                )
                st.plotly_chart(fig_ex, use_container_width=True)

            # Progression chart: top set weight over time
            st.markdown("### Exercise load progression")
            if not weights_filtered.empty:
                progression = (
                    weights_filtered.groupby(["date", "exercise"])["weight_kg"]
                    .max()
                    .reset_index()
                )
                progression["date"] = progression["date"].dt.date

                if selected_exercises and len(selected_exercises) == 1:
                    exercise_name = selected_exercises[0]
                    progression = progression[
                        progression["exercise"] == exercise_name
                    ]
                    title = f"{exercise_name} — top set weight over time"
                else:
                    title = "Top set weight over time by exercise"

                fig_prog = px.line(
                    progression,
                    x="date",
                    y="weight_kg",
                    color="exercise" if len(selected_exercises) != 1 else None,
                    markers=True,
                    title=title,
                )
                fig_prog.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Weight (kg)",
                )
                st.plotly_chart(fig_prog, use_container_width=True)

            # Session browser (date + session filter)
            st.markdown("### Session browser")
            available_dates = sorted(
                weights_filtered["date"].dropna().dt.date.unique()
            )
            if available_dates:
                # If the user has clicked a day on the volume chart, use that;
                # otherwise default to the latest available date.
                default_session_date = available_dates[-1]
                if "weights_session_date" in st.session_state:
                    default_session_date = st.session_state["weights_session_date"]

                session_date = st.date_input(
                    "Select session date",
                    value=default_session_date,
                    min_value=available_dates[0],
                    max_value=available_dates[-1],
                    key="weights_session_date",
                )

                sessions_on_date = (
                    weights_filtered[
                        weights_filtered["date"].dt.date == session_date
                    ]["session_id"]
                    .dropna()
                    .unique()
                )

                if len(sessions_on_date) == 0:
                    st.info("No sessions on this date for the current filters.")
                else:
                    selected_session_id = st.selectbox(
                        "Session on selected date",
                        options=sorted(sessions_on_date),
                        key="weights_session_id",
                    )

                    session_df = weights_filtered[
                        weights_filtered["session_id"] == selected_session_id
                    ].sort_values(["exercise", "set"])

                    st.markdown(f"#### Session details: {selected_session_id}")

                    # Per-session summary
                    s_col1, s_col2, s_col3 = st.columns(3)
                    session_volume = (
                        session_df["weight_kg"] * session_df["reps"]
                    ).sum()
                    session_reps = session_df["reps"].sum()
                    session_avg_rpe = session_df["rpe"].mean()

                    s_col1.metric(
                        "Session volume (kg)",
                        f"{session_volume:,.0f}",
                    )
                    s_col2.metric("Session reps", int(session_reps))
                    s_col3.metric(
                        "Session avg RPE",
                        f"{session_avg_rpe:.1f}"
                        if pd.notna(session_avg_rpe)
                        else "N/A",
                    )

                    st.dataframe(
                        session_df[
                            [
                                "exercise",
                                "set",
                                "reps",
                                "weight_kg",
                                "rpe",
                            ]
                        ],
                        use_container_width=True,
                    )

            # Detailed table
            st.markdown("### Weights Session Details")
            details = weights_filtered.copy()
            details["date"] = details["date"].dt.date
            details = details.sort_values(
                ["date", "session_id", "exercise", "set"]
            )
            st.dataframe(
                details[
                    [
                        "date",
                        "session_id",
                        "exercise",
                        "set",
                        "reps",
                        "weight_kg",
                        "rpe",
                    ]
                ],
                use_container_width=True,
            )

