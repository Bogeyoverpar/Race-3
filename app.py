from pathlib import Path
import random

import pandas as pd
import streamlit as st

from sim.models import load_drivers, load_schedule
from sim.event_engine import RaceSession


def status_icon(status):
    if status == "OUT":
        return "❌ OUT"
    if status == "HEAVY_DAMAGE":
        return "🔴 Heavy"
    if status == "DAMAGED":
        return "🟠 Damaged"
    return "🟢 Running"


def fuel_icon(fuel):
    try:
        fuel = int(fuel)
    except Exception:
        return fuel
    if fuel <= 0:
        return "❌ Empty"
    if fuel <= 12:
        return f"🔴 {fuel}"
    if fuel <= 25:
        return f"🟡 {fuel}"
    return f"🟢 {fuel}"


def tire_icon(age):
    try:
        age = int(age)
    except Exception:
        return age
    if age >= 25:
        return f"🔴 {age}"
    if age >= 15:
        return f"🟡 {age}"
    return f"🟢 {age}"


def event_color(event_type):
    colors = {
        "CAUTION": "#d6a800",
        "CRASH": "#c0392b",
        "GREEN_FLAG": "#1e8449",
        "RACE_FINISH": "#111111",
        "PIT_WINDOW": "#2471a3",
        "QUALIFYING": "#6c3483",
        "RACE_CONTROL": "#34495e",
        "MECHANICAL": "#8e44ad",
        "LAP_COMPLETE": "#2c3e50",
        "STAGE_END": "#b9770e",
    }
    return colors.get(event_type, "#333333")


def get_selected_cars_from_labels(labels, running_cars):
    selected_objects = []
    for label in labels:
        try:
            pos_text = label.split(" — ")[0]
            pos = int(pos_text.replace("P", ""))
        except Exception:
            continue
        for car in running_cars:
            if car.position == pos:
                selected_objects.append(car)
                break
    return selected_objects


def format_ticker_row(row):
    movement = row.get("+/-", 0)
    try:
        movement = int(movement)
    except Exception:
        movement = 0
    if movement > 0:
        move_text = f"▲{movement}"
    elif movement < 0:
        move_text = f"▼{abs(movement)}"
    else:
        move_text = "—"
    return f"P{row['Pos']} #{row['Car']} {row['Driver']} {move_text}"


DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="LRA Race Control", layout="wide")
st.title("🏁 LRA Race Control")
st.caption("Offline event-driven racing simulator UI")

# Load data
drivers = load_drivers(DATA_DIR / "drivers.csv")
schedule = load_schedule(DATA_DIR / "schedule.csv")

# Sidebar
with st.sidebar:
    st.header("Race Setup")
    race_names = [f"{race.race_id} — {race.name}" for race in schedule]
    selected_race = st.selectbox("Race", race_names)
    race = schedule[race_names.index(selected_race)]
    chaos = st.slider("Chaos Level", 1, 10, race.chaos)

    st.divider()
    st.write("### Race Info")
    st.write(f"**Track:** {race.track}")
    st.write(f"**Type:** {race.track_type.title()}")
    st.write(f"**Laps:** {race.laps}")
    st.write(f"**Stages:** {race.stage_1_end}, {race.stage_2_end}")

    st.divider()
    start_race = st.button("Start / Reset Race", type="primary", use_container_width=True)

# Start/reset race before referencing session
if start_race or "session" not in st.session_state:
    generated_seed = random.randint(1, 999999999)
    st.session_state.seed = generated_seed
    st.session_state.session = RaceSession(
        race,
        drivers,
        seed=generated_seed,
        chaos_override=int(chaos),
    )
    st.session_state.last_event = None
    st.session_state.followup = None

session: RaceSession = st.session_state.session

# Top race status
standings_df_raw = pd.DataFrame(session.standings_snapshot())
running_snapshot = standings_df_raw
if not standings_df_raw.empty and "Status" in standings_df_raw.columns:
    running_snapshot = standings_df_raw[standings_df_raw["Status"] != "OUT"]

leader_name = session.running_order()[0].driver.name if session.running_order() else "—"
lowest_fuel_driver = "—"
lowest_fuel_value = "—"
if not running_snapshot.empty and "Fuel" in running_snapshot.columns:
    fuel_sorted = running_snapshot.sort_values("Fuel", ascending=True)
    lowest_fuel_driver = fuel_sorted.iloc[0]["Driver"]
    lowest_fuel_value = fuel_sorted.iloc[0]["Fuel"]

top = st.columns(7)
top[0].metric("Lap", f"{session.current_lap} / {session.race.laps}")
top[1].metric("Flag", session.flag)
top[2].metric("Track", session.race.track_type.title())
top[3].metric("Chaos", session.race.chaos)
top[4].metric("Leader", leader_name)
top[5].metric("Lowest Fuel", f"{lowest_fuel_driver}: {lowest_fuel_value}")
top[6].metric("Seed", st.session_state.seed)

# Broadcast ticker
ticker_df = standings_df_raw.head(8)
ticker_text = "No cars loaded"
if not ticker_df.empty:
    ticker_text = "   |   ".join([format_ticker_row(row) for _, row in ticker_df.iterrows()])

st.markdown(
    f'''
    <div style="
        background-color:#111;
        color:white;
        padding:12px;
        border-radius:8px;
        font-size:18px;
        font-weight:700;
        white-space:nowrap;
        overflow-x:auto;
        margin-top:12px;
    ">
        {ticker_text}
    </div>
    ''',
    unsafe_allow_html=True,
)

st.divider()
control_col, event_col = st.columns([1, 2])

# Left panel
with control_col:
    st.subheader("Race Control")
    advance_col1, advance_col2 = st.columns(2)
    with advance_col1:
        if st.button("Advance 1 Lap", use_container_width=True, disabled=session.finished):
            st.session_state.last_event = session.advance_one_lap()
            st.session_state.followup = None
            st.rerun()
    with advance_col2:
        if st.button("Advance to Next Event", use_container_width=True, disabled=session.finished):
            st.session_state.last_event = session.run_until_next_action()
            st.session_state.followup = None
            st.rerun()

    st.divider()
    event = st.session_state.last_event
    if event and event.requires_decision:
        st.write("### Decision Required")
        for option in event.options:
            label = option.replace("_", " ").title()
            if st.button(label, key=f"decision_{option}", use_container_width=True):
                if option == "apply_penalty":
                    st.session_state.pending_penalty = True
                else:
                    st.session_state.followup = session.apply_decision(option)
                    st.rerun()

    st.divider()
    st.write("### Qualifying")
    q_col1, q_col2 = st.columns(2)
    with q_col1:
        if st.button("Start Qualifying", use_container_width=True, disabled=session.current_lap > 0 or session.finished):
            st.session_state.last_event = session.start_qualifying()
            st.session_state.followup = None
            st.rerun()
    with q_col2:
        if st.button("Run Next Car", use_container_width=True, disabled=session.current_lap > 0 or session.finished):
            st.session_state.last_event = session.run_next_qualifier()
            st.session_state.followup = None
            st.rerun()

    q_col3, q_col4 = st.columns(2)
    with q_col3:
        if st.button("Run All Qualifying", use_container_width=True, disabled=session.current_lap > 0 or session.finished):
            st.session_state.last_event = session.run_all_qualifying()
            st.session_state.followup = None
            st.rerun()
    with q_col4:
        if st.button("Lock Grid", use_container_width=True, disabled=session.current_lap > 0 or session.finished):
            st.session_state.last_event = session.finalize_qualifying()
            st.session_state.followup = None
            st.rerun()
    st.caption("Qualifying can be run before the green flag. Once laps start, the grid is locked.")

    st.divider()
    st.write("### Pit Strategy")
    running_cars = session.running_order()
    pit_labels = [f"P{car.position} — #{car.driver.car_number} {car.driver.name}" for car in running_cars]
    selected_pit_cars = st.multiselect("Select cars to pit", pit_labels, key="pit_cars_select")

    pit_col1, pit_col2 = st.columns(2)
    with pit_col1:
        if st.button("Pit Selected Cars", use_container_width=True, disabled=session.finished):
            selected_objects = get_selected_cars_from_labels(selected_pit_cars, running_cars)
            st.session_state.followup = session.pit_cars(selected_objects)
            st.rerun()
    with pit_col2:
        if st.button("Pit Entire Field", use_container_width=True, disabled=session.finished):
            st.session_state.followup = session.pit_cars(running_cars)
            st.rerun()

    quick_pit_col1, quick_pit_col2 = st.columns(2)
    with quick_pit_col1:
        if st.button("Pit Damaged Cars", use_container_width=True, disabled=session.finished):
            damaged_cars = [
                car for car in running_cars
                if getattr(car, "damage_status", "RUNNING") in ["DAMAGED", "HEAVY_DAMAGE"]
            ]
            st.session_state.followup = session.pit_cars(damaged_cars)
            st.rerun()
    with quick_pit_col2:
        if st.button("Pit Cars Under 12 Fuel", use_container_width=True, disabled=session.finished):
            low_fuel_cars = [car for car in running_cars if getattr(car, "fuel", 100) < 12]
            st.session_state.followup = session.pit_cars(low_fuel_cars)
            st.rerun()
    st.caption("Green-flag stops cost more track position. Caution stops reorder pitting cars by pit crew performance.")

    st.divider()
    st.write("### Manual Actions")
    if st.button("Throw Manual Caution", use_container_width=True, disabled=session.finished):
        st.session_state.followup = session.apply_decision("throw_caution")
        st.rerun()

    with st.expander("Apply Penalty"):
        driver_labels = [f"{driver.driver_id} — #{driver.car_number} {driver.name}" for driver in drivers]
        selected_driver = st.selectbox("Driver", driver_labels)
        penalty_amount = st.slider("Penalty Amount", 1, 30, 5)
        if st.button("Apply Penalty"):
            driver_id = selected_driver.split(" — ")[0]
            st.session_state.followup = session.apply_decision("apply_penalty", driver_id=driver_id, penalty=penalty_amount)
            st.rerun()

    with st.expander("Retire / Black Flag Cars"):
        running_cars_for_retire = session.running_order()
        retire_labels = [f"P{car.position} — #{car.driver.car_number} {car.driver.name}" for car in running_cars_for_retire]
        selected_retire_cars = st.multiselect("Select cars to retire", retire_labels, key="retire_cars_select")
        retire_reason = st.text_input("Reason", value="Black flagged by race control")
        if st.button("Retire Selected Cars", disabled=session.finished):
            selected_objects = get_selected_cars_from_labels(selected_retire_cars, running_cars_for_retire)
            st.session_state.followup = session.retire_cars(selected_objects, reason=retire_reason)
            st.rerun()

    if session.finished:
        results_df = pd.DataFrame(session.final_results())
        csv_data = results_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Final Results CSV",
            data=csv_data,
            file_name=f"{session.race.race_id}_{session.race.name.replace(' ', '_')}_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

# Right panel
with event_col:
    st.subheader("Current Event")
    event = st.session_state.last_event
    if event:
        color = event_color(event.event_type)
        st.markdown(
            f'''
            <div style="
                background-color:{color};
                color:white;
                padding:18px;
                border-radius:10px;
                margin-bottom:12px;
            ">
                <h2 style="margin:0;">Lap {event.lap} — {event.event_type}</h2>
                <h3 style="margin:4px 0 0 0;">{event.title}</h3>
            </div>
            ''',
            unsafe_allow_html=True,
        )
        st.text(event.message)
        if event.options:
            st.caption("Available decisions: " + ", ".join(event.options))
    else:
        st.info("Start the race using the controls on the left.")

    if st.session_state.followup:
        followup = st.session_state.followup
        st.success(f"{followup.title}: {followup.message}")

    st.divider()
    st.subheader("Race Feed")
    feed_rows = [f"**Lap {e.lap} — {e.title}**  \\n{e.message}" for e in reversed(session.event_log[-8:])]
    if feed_rows:
        st.markdown("---\\n".join(feed_rows))
    else:
        st.write("No race updates yet.")

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Running Order", "Qualifying", "Event Log", "Driver Ratings", "Final Results"])

with tab1:
    standings_df = pd.DataFrame(session.standings_snapshot())
    if not standings_df.empty:
        if "Fuel" in standings_df.columns:
            standings_df["Fuel"] = standings_df["Fuel"].apply(fuel_icon)
        if "Tire Age" in standings_df.columns:
            standings_df["Tire Age"] = standings_df["Tire Age"].apply(tire_icon)
        if "Status" in standings_df.columns:
            standings_df["Status"] = standings_df["Status"].apply(status_icon)
    st.subheader("Full Running Order")
    st.dataframe(standings_df, use_container_width=True, hide_index=True)

with tab2:
    qualifying_df = pd.DataFrame(session.qualifying_snapshot())
    if qualifying_df.empty:
        st.write("No qualifying runs completed yet.")
    else:
        preferred_cols = ["Rank", "Car", "Driver", "Team", "Manufacturer", "Lap 1", "Lap 2", "Best Lap", "Qualifying Score"]
        display_cols = [col for col in preferred_cols if col in qualifying_df.columns]
        st.subheader("Live Qualifying Board")
        st.dataframe(qualifying_df[display_cols], use_container_width=True, hide_index=True)

with tab3:
    if session.event_log:
        log_rows = []
        for e in session.event_log:
            log_rows.append({"Lap": e.lap, "Type": e.event_type, "Title": e.title, "Message": e.message.replace("\n", " | ")})
        st.dataframe(pd.DataFrame(log_rows), use_container_width=True, hide_index=True)
    else:
        st.write("No events yet.")

with tab4:
    rating_rows = []
    for driver in drivers:
        rating_rows.append({
            "Driver ID": driver.driver_id,
            "Car": driver.car_number,
            "Driver": driver.name,
            "Team": driver.team,
            "Manufacturer": driver.manufacturer,
            "Speed": driver.speed,
            "Consistency": driver.consistency,
            "Aggression": driver.aggression,
            "Qualifying": driver.qualifying,
            "Pit Crew": driver.pit_crew,
            "Tire Saving": driver.tire_saving,
        })
    st.dataframe(pd.DataFrame(rating_rows), use_container_width=True, hide_index=True)

with tab5:
    if session.finished:
        st.dataframe(pd.DataFrame(session.final_results()), use_container_width=True, hide_index=True)
    else:
        st.write("Final results will appear after the checkered flag.")
