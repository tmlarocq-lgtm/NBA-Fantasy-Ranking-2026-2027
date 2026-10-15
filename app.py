from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="NBA Fantasy Dashboard",
    page_icon="🏀",
    layout="wide",
)

st.title("🏀 NBA Fantasy Dashboard")
st.caption("Explore 2025–26 NBA player game logs.")


# Find CSV files saved alongside this app or inside the data folder.
app_folder = Path(__file__).resolve().parent

csv_files = sorted(
    list(app_folder.glob("*.csv"))
    + list((app_folder / "data").glob("*.csv"))
)

uploaded_file = st.file_uploader(
    "Optional: upload a player game-log CSV",
    type=["csv"],
)

if uploaded_file is not None:
    source = uploaded_file
elif csv_files:
    selected_file = st.selectbox(
        "Choose your dataset",
        csv_files,
        format_func=lambda path: str(path.relative_to(app_folder)),
    )
    source = selected_file
else:
    st.info(
        "No CSV found yet. Use the upload button above. "
        "If your download is a ZIP, extract it first and upload "
        "the CSV from inside it."
    )
    st.stop()

try:
    df = pd.read_csv(source)
except Exception as error:
    st.error(f"Could not open this CSV: {error}")
    st.stop()

df.columns = df.columns.astype(str).str.strip()

if df.empty:
    st.warning("This CSV has no data rows.")
    st.stop()

with st.expander("Preview your dataset"):
    st.dataframe(df.head(10), use_container_width=True)
    st.write("Columns:", list(df.columns))

st.info(
    "Use one row per player per game. "
    "Choose the matching columns below before reading the rankings."
)


# Suggest likely column names, but let you change them.
def choose_column(label, guesses):
    columns = list(df.columns)
    lookup = {column.casefold(): column for column in columns}
    suggested = None

    for guess in guesses:
        if guess.casefold() in lookup:
            suggested = lookup[guess.casefold()]
            break

    options = ["-- Select a column --"] + columns
    index = options.index(suggested) if suggested else 0

    return st.selectbox(label, options, index=index)


st.sidebar.header("1. Match your columns")

player_column = choose_column(
    "Player name",
    ["Player", "PLAYER_NAME", "player_name", "Name"],
)

stat_columns = {
    "Points": choose_column("Points", ["PTS", "Points"]),
    "Rebounds": choose_column(
        "Total rebounds", ["TRB", "REB", "Rebounds"]
    ),
    "Assists": choose_column("Assists", ["AST", "Assists"]),
    "Steals": choose_column("Steals", ["STL", "Steals"]),
    "Blocks": choose_column("Blocks", ["BLK", "Blocks"]),
    "Turnovers": choose_column(
        "Turnovers", ["TOV", "TO", "Turnovers"]
    ),
}

required_columns = [player_column] + list(stat_columns.values())

if "-- Select a column --" in required_columns:
    st.warning(
        "Select the player name and all six stat columns "
        "in the left sidebar."
    )
    st.stop()

if len(set(required_columns)) != len(required_columns):
    st.warning("Choose a different source column for each field.")
    st.stop()


# Create a consistent table from your chosen columns.
games = pd.DataFrame(index=df.index)
games["Player"] = df[player_column].astype("string").str.strip()

for stat_name, column_name in stat_columns.items():
    games[stat_name] = pd.to_numeric(
        df[column_name], errors="coerce"
    )

rows_before = len(games)
games = games.dropna(subset=["Player"] + list(stat_columns))
games = games[games["Player"] != ""]

if games.empty:
    st.warning(
        "No usable rows found. Check the selected columns "
        "and make sure the stats contain numbers."
    )
    st.stop()

if len(games) < rows_before:
    st.caption(
        f"Excluded {rows_before - len(games):,} rows with "
        "missing player names or nonnumeric stats."
    )


st.sidebar.header("2. Set scoring")
st.sidebar.caption(
    "These are practice weights, NOT verified ESPN defaults. "
    "Change them to match your league. "
    "This starter includes only the six stats listed below."
)

default_weights = {
    "Points": 1.0,
    "Rebounds": 1.2,
    "Assists": 1.5,
    "Steals": 3.0,
    "Blocks": 3.0,
    "Turnovers": -1.0,
}

games["Fantasy points"] = 0.0

for stat_name, default in default_weights.items():
    weight = st.sidebar.number_input(
        f"Fantasy points per {stat_name.lower()}",
        value=default,
        step=0.1,
        key=f"weight_{stat_name}",
    )
    games["Fantasy points"] += games[stat_name] * weight


# Each usable row is counted as one game.
summary = (
    games.groupby("Player")
    .agg(
        Games=("Fantasy points", "size"),
        Fantasy_PPG=("Fantasy points", "mean"),
        Fantasy_Total=("Fantasy points", "sum"),
        Points_PG=("Points", "mean"),
        Rebounds_PG=("Rebounds", "mean"),
        Assists_PG=("Assists", "mean"),
        Steals_PG=("Steals", "mean"),
        Blocks_PG=("Blocks", "mean"),
        Turnovers_PG=("Turnovers", "mean"),
    )
    .reset_index()
)

st.sidebar.header("3. Filter rankings")

minimum_games = st.sidebar.number_input(
    "Minimum games",
    min_value=1,
    value=1,
    step=1,
)

summary = summary[summary["Games"] >= minimum_games]

sort_by = st.sidebar.selectbox(
    "Rank players by",
    ["Fantasy_PPG", "Fantasy_Total"],
)

summary = summary.sort_values(sort_by, ascending=False)

if summary.empty:
    st.warning("No players match. Lower the minimum-games filter.")
    st.stop()

col1, col2, col3 = st.columns(3)

col1.metric("Players in rankings", len(summary))
col2.metric("Usable game-log rows", len(games))
col3.metric("Top-ranked player", summary.iloc[0]["Player"])

st.subheader("Player rankings")
st.dataframe(
    summary.round(2),
    hide_index=True,
    use_container_width=True,
)

st.subheader("Top 15 players")
st.bar_chart(
    summary.head(15).set_index("Player")[[sort_by]]
)

st.subheader("Explore a player")

selected_player = st.selectbox(
    "Player",
    sorted(summary["Player"].tolist()),
)

player_games = games[games["Player"] == selected_player]

st.dataframe(
    player_games.round(2),
    hide_index=True,
    use_container_width=True,
)

st.download_button(
    "Download rankings as CSV",
    data=summary.round(2).to_csv(index=False).encode("utf-8"),
    file_name="nba_2025_26_fantasy_rankings.csv",
    mime="text/csv"
