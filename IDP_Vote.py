import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date, time
from streamlit_autorefresh import st_autorefresh

# ============== DATA FILE ==============
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voting_data.json")

def load_data():
    """Load all data from JSON file"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_data():
    """Save all data to JSON file"""
    data = {
        "contestants": st.session_state.contestants,
        "votes": st.session_state.votes,
        "allowed_voters": st.session_state.allowed_voters,
        "voted_emails": list(st.session_state.voted_emails),
        "voter_picks": st.session_state.voter_picks,
        "vote_timestamps": st.session_state.vote_timestamps,
        "voting_open": st.session_state.voting_open,
        "schedule_start": st.session_state.schedule_start,
        "schedule_end": st.session_state.schedule_end,
        "app_title": st.session_state.app_title,
        "app_subtitle": st.session_state.app_subtitle,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_contestant_label(c):
    """Get display label for a contestant dict"""
    num = str(c.get("Number", ""))
    name = c.get("Name", "")
    if name:
        return f"#{num} - {name}"
    return f"#{num}"

st.set_page_config(page_title="Office Talent Show - Voting", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.title {
    color: #FF4B4B;
    font-size: 36px;
    font-weight: bold;
    text-align: center;
    animation: popIn 0.8s cubic-bezier(0.68, -0.55, 0.27, 1.55) both;
}
@keyframes popIn {
    0% { transform: scale(0.3); opacity: 0; }
    50% { transform: scale(1.15); opacity: 0.9; }
    70% { transform: scale(0.95); opacity: 1; }
    100% { transform: scale(1); opacity: 1; }
}
.subtitle {
    color: #555;
    font-size: 18px;
    text-align: center;
    margin-bottom: 20px;
}
.stButton > button {
    background-color: #FF4B4B;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 40px;
    font-size: 18px;
}
.stButton > button:hover {
    background-color: #cc0000;
    color: white;
}
.small-link {
    font-size: 11px;
    color: #999;
    text-decoration: none;
    padding: 2px 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    float: right;
}
.small-link:hover {
    color: #FF4B4B;
    border-color: #FF4B4B;
}
[data-testid="collapsedControl"] { display: none; }
section[data-testid="stSidebar"] { display: none; }

/* ===== PODIUM ===== */
.podium-container {
    display: flex;
    justify-content: center;
    align-items: flex-end;
    gap: 12px;
    margin: 30px auto 20px;
    max-width: 600px;
}
.podium-block {
    text-align: center;
    border-radius: 16px 16px 0 0;
    padding: 18px 14px 14px;
    min-width: 140px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    position: relative;
    transition: transform 0.3s;
}
.podium-block:hover { transform: translateY(-6px); }
.podium-gold {
    background: linear-gradient(135deg, #FFD700, #FFA500);
    height: 180px;
    order: 2;
}
.podium-silver {
    background: linear-gradient(135deg, #C0C0C0, #A8A8A8);
    height: 180px;
    order: 1;
}
.podium-bronze {
    background: linear-gradient(135deg, #CD7F32, #A0522D);
    height: 180px;
    order: 3;
}
.podium-rank {
    font-size: 38px;
    margin-bottom: 4px;
}
.podium-name {
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    text-shadow: 1px 1px 3px rgba(0,0,0,0.3);
    word-break: break-word;
}
.podium-votes {
    font-size: 22px;
    font-weight: 800;
    color: #fff;
    margin-top: 6px;
    text-shadow: 1px 1px 3px rgba(0,0,0,0.3);
}

/* ===== ANIMATED BARS ===== */
.results-bar-container {
    margin: 8px 0;
    padding: 10px 16px;
    background: #1e1e2f;
    border-radius: 12px;
}
.results-bar-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
}
.results-bar-name {
    color: #fff;
    font-weight: 600;
    font-size: 15px;
}
.results-bar-count {
    color: #aaa;
    font-size: 14px;
}
.results-bar-track {
    background: #2a2a3d;
    border-radius: 8px;
    height: 22px;
    overflow: hidden;
}
.results-bar-fill {
    height: 100%;
    border-radius: 8px;
    background: linear-gradient(90deg, #FF4B4B, #FF8C00, #FFD700);
    transition: width 1s ease;
    animation: bar-glow 2s ease-in-out infinite alternate;
}
@keyframes bar-glow {
    0% { box-shadow: 0 0 6px rgba(255,75,75,0.4); }
    100% { box-shadow: 0 0 14px rgba(255,215,0,0.6); }
}

.live-badge {
    display: inline-block;
    background: #FF4B4B;
    color: white;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    animation: pulse-badge 1.5s infinite;
    margin-left: 10px;
}
@keyframes pulse-badge {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
</style>
""", unsafe_allow_html=True)

# ============== ADMIN PASSWORD ==============
ADMIN_PASSWORD = "Admin123"
MAX_VOTES_PER_PERSON = 3

# --- Load saved data ---
saved = load_data()

if "contestants" not in st.session_state:
    st.session_state.contestants = saved["contestants"] if saved and isinstance(saved.get("contestants", None), list) and len(saved.get("contestants", [])) > 0 and isinstance(saved["contestants"][0], dict) else []

if "votes" not in st.session_state:
    st.session_state.votes = saved["votes"] if saved and "votes" in saved else {}
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "allowed_voters" not in st.session_state:
    st.session_state.allowed_voters = saved["allowed_voters"] if saved else []
if "voter_logged_in" not in st.session_state:
    st.session_state.voter_logged_in = False
if "voter_name" not in st.session_state:
    st.session_state.voter_name = ""
if "voter_email" not in st.session_state:
    st.session_state.voter_email = ""
if "voted_emails" not in st.session_state:
    st.session_state.voted_emails = set(saved["voted_emails"]) if saved and "voted_emails" in saved else set()
if "voter_picks" not in st.session_state:
    st.session_state.voter_picks = saved["voter_picks"] if saved and "voter_picks" in saved else {}
if "vote_timestamps" not in st.session_state:
    st.session_state.vote_timestamps = saved["vote_timestamps"] if saved and "vote_timestamps" in saved else {}
if "voting_open" not in st.session_state:
    st.session_state.voting_open = saved["voting_open"] if saved and "voting_open" in saved else True
if "schedule_start" not in st.session_state:
    st.session_state.schedule_start = saved["schedule_start"] if saved and "schedule_start" in saved else ""
if "schedule_end" not in st.session_state:
    st.session_state.schedule_end = saved["schedule_end"] if saved and "schedule_end" in saved else ""
if "app_title" not in st.session_state:
    st.session_state.app_title = saved["app_title"] if saved and "app_title" in saved else "🎤 IDP Got Talent 💃"
if "app_subtitle" not in st.session_state:
    st.session_state.app_subtitle = saved["app_subtitle"] if saved and "app_subtitle" in saved else "Vote for your favourite performers!"

# Always refresh votes, contestants, voted_emails and voter_picks from JSON for real-time updates
if saved:
    if "votes" in saved:
        st.session_state.votes = saved["votes"]
    if isinstance(saved.get("contestants", None), list) and len(saved.get("contestants", [])) > 0 and isinstance(saved["contestants"][0], dict):
        st.session_state.contestants = saved["contestants"]
    if "voted_emails" in saved:
        st.session_state.voted_emails = set(saved["voted_emails"])
    if "allowed_voters" in saved:
        st.session_state.allowed_voters = saved["allowed_voters"]
    if "voter_picks" in saved:
        st.session_state.voter_picks = saved["voter_picks"]
    if "vote_timestamps" in saved:
        st.session_state.vote_timestamps = saved["vote_timestamps"]
    if "voting_open" in saved:
        st.session_state.voting_open = saved["voting_open"]
    if "schedule_start" in saved:
        st.session_state.schedule_start = saved["schedule_start"]
    if "schedule_end" in saved:
        st.session_state.schedule_end = saved["schedule_end"]
    if "app_title" in saved:
        st.session_state.app_title = saved["app_title"]
    if "app_subtitle" in saved:
        st.session_state.app_subtitle = saved["app_subtitle"]

# --- Auto schedule check (runs on every page load / refresh) ---
now = datetime.now()
sched_start = st.session_state.schedule_start
sched_end = st.session_state.schedule_end
if sched_start and sched_end:
    try:
        start_dt = datetime.fromisoformat(sched_start)
        end_dt = datetime.fromisoformat(sched_end)
        if start_dt <= now <= end_dt:
            if not st.session_state.voting_open:
                st.session_state.voting_open = True
                save_data()
        elif now < start_dt:
            if st.session_state.voting_open:
                st.session_state.voting_open = False
                save_data()
        elif now > end_dt:
            if st.session_state.voting_open:
                st.session_state.voting_open = False
            # Auto clear schedule after end time
            st.session_state.schedule_start = ""
            st.session_state.schedule_end = ""
            save_data()
    except:
        pass

# --- Page from query params ---
params = st.query_params
current_page = params.get("page", "voting")

# ============================================================
#                     VOTING PAGE
# ============================================================
if current_page == "voting":

    contestants = st.session_state.contestants
    contestant_labels = [get_contestant_label(c) for c in contestants]

    st.markdown('<div style="text-align:center;"><img src="https://images.ctfassets.net/8bbwomjfix8m/55AePSl50ZnwVBce2lROSW/ff063dcfbec1eb176c59e2179eef57e2/idp-logo.svg" width="180" style="margin-bottom:10px;"></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="title">{st.session_state.app_title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">{st.session_state.app_subtitle}</div>', unsafe_allow_html=True)

    voting_allowed = st.session_state.voting_open

    # --- Voter Login ---
    if not voting_allowed:
        if st.session_state.schedule_start and st.session_state.schedule_end:
            try:
                s_dt = datetime.fromisoformat(st.session_state.schedule_start)
                e_dt = datetime.fromisoformat(st.session_state.schedule_end)
                now_check = datetime.now()
                if now_check < s_dt:
                    st.warning(f"⏳ Voting will open on **{s_dt.strftime('%d %b %Y, %I:%M %p')}**")
                elif now_check > e_dt:
                    st.warning(f"⏸️ Voting ended on **{e_dt.strftime('%d %b %Y, %I:%M %p')}**")
                else:
                    st.warning("⏸️ Voting is currently closed.")
            except:
                st.warning("⏸️ Voting is currently closed. Please check back later.")
        else:
            st.warning("⏸️ Voting is currently closed. Please check back later.")
    elif not st.session_state.voter_logged_in:
        if len(st.session_state.allowed_voters) == 0:
            st.warning("Voting is not open yet. Please check back later.")
        else:
            login_email = st.text_input("📧 Enter Your Email")

            if st.button("Continue"):
                if not login_email.strip():
                    st.warning("Please enter your Email!")
                else:
                    matched_voter = None
                    for v in st.session_state.allowed_voters:
                        if v["Email"].strip().lower() == login_email.strip().lower():
                            matched_voter = v
                            break
                    if matched_voter:
                        st.session_state.voter_logged_in = True
                        st.session_state.voter_name = matched_voter["Name"].strip()
                        st.session_state.voter_email = login_email.strip().lower()
                        st.rerun()
                    else:
                        st.error("❌ Your Email not found in the voter list. Contact Admin.")
    else:
        st.success(f"✅ Welcome, **{st.session_state.voter_name}**! ({st.session_state.voter_email})")

        st.markdown("---")

        # Check if already voted
        already_voted = st.session_state.voter_email in st.session_state.voted_emails

        if already_voted:
            my_picks = st.session_state.voter_picks.get(st.session_state.voter_email, [])
            if my_picks:
                st.success(f"🎉 Thanks {st.session_state.voter_name}! You voted for: {', '.join(my_picks)}")
            else:
                st.info("✅ You have already voted. Thank you!")
        elif len(contestants) == 0:
            st.info("No contestants added yet.")
        else:
            st.markdown(f"<p style='font-size:20px; font-weight:600; margin-bottom:4px;'>🗳️ Select your Top {MAX_VOTES_PER_PERSON} performers</p>", unsafe_allow_html=True)

            selected = st.multiselect(
                "Choose your favourites:",
                options=contestant_labels,
                max_selections=MAX_VOTES_PER_PERSON,
                key="vote_select"
            )

            if st.button("✅ Submit"):
                if len(selected) == 0:
                    st.warning("Please select at least 1 performer!")
                elif len(selected) > MAX_VOTES_PER_PERSON:
                    st.error(f"You can vote for maximum {MAX_VOTES_PER_PERSON} performers!")
                else:
                    # Record votes
                    for pick in selected:
                        st.session_state.votes[pick] = st.session_state.votes.get(pick, 0) + 1
                    st.session_state.voted_emails.add(st.session_state.voter_email)
                    st.session_state.voter_picks[st.session_state.voter_email] = selected
                    st.session_state.vote_timestamps[st.session_state.voter_email] = datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
                    save_data()
                    st.rerun()

    # Show Live Results only after voting
    if st.session_state.voter_logged_in and st.session_state.voter_email in st.session_state.voted_emails:
        st.markdown("---")
        st.markdown('## Live Results <span class="live-badge">● LIVE</span>', unsafe_allow_html=True)

        total_votes = sum(st.session_state.votes.values())
        if total_votes == 0:
            st.info("No votes yet.")
        else:
            # Sort by votes descending
            sorted_contestants = sorted(contestants, key=lambda c: st.session_state.votes.get(get_contestant_label(c), 0), reverse=True)
            sorted_labels = [get_contestant_label(c) for c in sorted_contestants]
            sorted_counts = [st.session_state.votes.get(lbl, 0) for lbl in sorted_labels]

            # === PODIUM (Top 3 with votes > 0 only) ===
            medal_emoji = ["🥇", "🥈", "🥉"]
            podium_class = ["podium-gold", "podium-silver", "podium-bronze"]
            # Filter: only contestants who have at least 1 vote
            podium_candidates = [(lbl, cnt) for lbl, cnt in zip(sorted_labels, sorted_counts) if cnt > 0]
            top3 = min(3, len(podium_candidates))

            if top3 > 0:
                podium_html = '<div class="podium-container">'
                for i in range(top3):
                    lbl, cnt = podium_candidates[i]
                    podium_html += f'''
                    <div class="podium-block {podium_class[i]}">
                        <div class="podium-rank">{medal_emoji[i]}</div>
                        <div class="podium-name">{lbl}</div>
                        <div class="podium-votes">{cnt} votes</div>
                    </div>'''
                podium_html += '</div>'
                st.markdown(podium_html, unsafe_allow_html=True)

            st.markdown("")
            st.markdown("### Top 5 Scoreboard")

            # === ANIMATED BARS (Top 5 only) ===
            top5_labels = sorted_labels[:5]
            top5_counts = sorted_counts[:5]
            max_count = max(top5_counts) if top5_counts else 1
            rank_icons = {0: "🥇", 1: "🥈", 2: "🥉"}
            for i, (lbl, cnt) in enumerate(zip(top5_labels, top5_counts)):
                pct = int((cnt / max_count) * 100) if max_count > 0 else 0
                pct_total = int((cnt / total_votes) * 100) if total_votes > 0 else 0
                # Only show medal icon if they have votes
                if cnt > 0:
                    icon = rank_icons.get(i, f"#{i+1}")
                else:
                    icon = f"#{i+1}"
                bar_html = f'''
                <div class="results-bar-container">
                    <div class="results-bar-header">
                        <span class="results-bar-name">{icon} {lbl}</span>
                        <span class="results-bar-count">{cnt} votes ({pct_total}%)</span>
                    </div>
                    <div class="results-bar-track">
                        <div class="results-bar-fill" style="width: {pct}%;"></div>
                    </div>
                </div>'''
                st.markdown(bar_html, unsafe_allow_html=True)

            st.markdown(f"<p style='text-align:center; color:#888; margin-top:16px;'>🗳️ Total Votes Cast: <b>{total_votes}</b></p>", unsafe_allow_html=True)

        # Auto-refresh every 5 seconds for real-time updates (smooth, no visible page reload)
        st_autorefresh(interval=5000, limit=None, key="live_refresh")

    # Auto-refresh for schedule auto-open/close (runs even when voting is closed)
    if st.session_state.schedule_start and st.session_state.schedule_end:
        st_autorefresh(interval=10000, limit=None, key="schedule_refresh")

# ============================================================
#                     ADMIN PANEL
# ============================================================
elif current_page == "admin":

    # Tiny voting link on top-right
    st.markdown('<a class="small-link" href="?page=voting" target="_self">🗳️ Voting</a>', unsafe_allow_html=True)

    st.markdown('<div class="title">🔐 Admin Panel</div>', unsafe_allow_html=True)
    st.markdown("---")

    # --- Login ---
    if not st.session_state.admin_logged_in:
        pwd = st.text_input("Enter Admin Password", type="password")
        if st.button("🔓 Login"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Wrong password!")
    else:
        st.success("✅ Logged in as Admin")

        if st.button("🔒 Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

        st.markdown("---")



        # --- Live Voting Stats ---
        st.markdown('### 📊 Live Voting Stats <span class="live-badge">● LIVE</span>', unsafe_allow_html=True)

        total_voted = len(st.session_state.voted_emails)
        total_voters = len(st.session_state.allowed_voters)
        st.caption(f"🗳️ {total_voted} / {total_voters} voters have voted")

        if total_voted > 0:
            # Build voter name lookup
            voter_name_map = {}
            for v in st.session_state.allowed_voters:
                voter_name_map[v["Email"].strip().lower()] = v["Name"].strip()

            # Build table data — one row per pick (most recent first)
            stats_rows = []
            for email in st.session_state.voted_emails:
                name = voter_name_map.get(email, email)
                picks = st.session_state.voter_picks.get(email, [])
                voted_time = st.session_state.vote_timestamps.get(email, "—")
                for pick in picks:
                    stats_rows.append({
                        "Voter": name,
                        "Email": email,
                        "Voted For": pick,
                        "Time": voted_time
                    })

            # Sort by time descending (most recent first)
            stats_rows.sort(key=lambda r: r["Time"], reverse=True)

            stats_df = pd.DataFrame(stats_rows)
            st.dataframe(stats_df, use_container_width=True, hide_index=True, height=200)
        else:
            st.info("No votes yet.")

        st.markdown("---")

        # --- Customize Title & Subtitle ---
        st.markdown("**✏️ Page Title & Subtitle**")
        tc1, tc2 = st.columns(2)
        with tc1:
            new_title = st.text_input("Title", value=st.session_state.app_title, key="edit_title")
        with tc2:
            new_subtitle = st.text_input("Subtitle", value=st.session_state.app_subtitle, key="edit_subtitle")
        if st.button("💾 Save Title", use_container_width=False):
            st.session_state.app_title = new_title
            st.session_state.app_subtitle = new_subtitle
            save_data()
            st.success("✅ Title & Subtitle updated!")
            st.rerun()

        st.markdown("---")

        # --- Upload CSVs side by side ---
        st.markdown("### 📂 Upload CSV Files")
        col_voter, col_contestant = st.columns(2)

        with col_voter:
            st.markdown("**📄 Voter List**")
            st.caption("Columns: `Name`, `Email`")
            uploaded_file = st.file_uploader("Upload Voter CSV", type=["csv"], label_visibility="collapsed")
            if uploaded_file is not None:
                try:
                    df = pd.read_csv(uploaded_file, sep=None, engine="python", encoding="utf-8-sig")
                    df.columns = df.columns.str.strip().str.replace(r'\s+', ' ', regex=True)
                    col_map = {col.lower(): col for col in df.columns}
                    name_col = col_map.get("name", None)
                    email_col = col_map.get("email", None)
                    if name_col and email_col:
                        voter_df = df[[name_col, email_col]].dropna().rename(columns={name_col: "Name", email_col: "Email"})
                        st.session_state.allowed_voters = voter_df.to_dict("records")
                        save_data()
                        st.success(f"✅ {len(st.session_state.allowed_voters)} voters loaded")
                    else:
                        st.error(f"❌ Need 'Name' & 'Email' columns! Found: {list(df.columns)}")
                except Exception as e:
                    st.error(f"Error: {e}")

        with col_contestant:
            st.markdown("**🎭 Contestants**")
            st.caption("Columns: `Number`, `Name`, `Photo`(URL)")
            contestants_csv = st.file_uploader("Upload Contestants CSV", type=["csv"], key="contestants_csv", label_visibility="collapsed")
            if contestants_csv is not None:
                try:
                    df = pd.read_csv(contestants_csv, sep=None, engine="python", encoding="utf-8-sig")
                    df.columns = df.columns.str.strip().str.replace(r'\s+', ' ', regex=True)
                    col_map = {col.lower(): col for col in df.columns}
                    num_col = col_map.get("number", None)
                    name_col = col_map.get("name", None)
                    photo_col = col_map.get("photo", None)

                    if num_col:
                        df["Number"] = df[num_col].astype(str).str.strip()
                        df["Name"] = df[name_col].astype(str).str.strip() if name_col else ""
                        df["Photo"] = df[photo_col].astype(str).str.strip() if photo_col else ""
                        df = df.fillna("")
                        df["Name"] = df["Name"].replace("nan", "")
                        df["Photo"] = df["Photo"].replace("nan", "")
                        contestants_list = df[["Number", "Name", "Photo"]].to_dict("records")
                        st.session_state.contestants = contestants_list
                        st.session_state.votes = {get_contestant_label(c): 0 for c in contestants_list}
                        st.session_state.voted_emails = set()
                        save_data()
                        st.success(f"✅ {len(contestants_list)} contestants loaded")
                    else:
                        st.error(f"❌ Need 'Number' column! Found: {list(df.columns)}")
                except Exception as e:
                    st.error(f"Error: {e}")

        # Show loaded data summary
        s1, s2 = st.columns(2)
        with s1:
            if len(st.session_state.allowed_voters) > 0:
                st.caption(f"👥 {len(st.session_state.allowed_voters)} voters loaded")
        with s2:
            if len(st.session_state.contestants) > 0:
                st.caption(f"🎭 {len(st.session_state.contestants)} contestants loaded")

        st.markdown("---")


        # --- Control Panel ---
        st.markdown("**🔄 Control Panel**")
        v1, v2, r1, r2 = st.columns([1, 1, 1, 1])
        with v1:
            if st.session_state.voting_open:
                if st.button("Close Voting", use_container_width=True):
                    st.session_state.voting_open = False
                    save_data()
                    st.rerun()
            else:
                if st.button("Open Voting", use_container_width=True):
                    st.session_state.voting_open = True
                    save_data()
                    st.rerun()
        with v2:
            status = "🟢 Open" if st.session_state.voting_open else "🔴 Closed"
            st.markdown(f"<p style='padding-top:8px; font-weight:600;'>{status}</p>", unsafe_allow_html=True)
        with r1:
            if st.button("Reset Votes", use_container_width=True):
                st.session_state.votes = {get_contestant_label(c): 0 for c in st.session_state.contestants}
                st.session_state.voted_emails = set()
                st.session_state.voter_picks = {}
                st.session_state.vote_timestamps = {}
                save_data()
                st.success("All votes reset!")
                st.rerun()
        with r2:
            if st.button("Reset All", use_container_width=True):
                st.session_state.votes = {get_contestant_label(c): 0 for c in st.session_state.contestants}
                st.session_state.voted_emails = set()
                st.session_state.voter_picks = {}
                st.session_state.vote_timestamps = {}
                st.session_state.contestants = []
                st.session_state.allowed_voters = []
                st.session_state.schedule_start = ""
                st.session_state.schedule_end = ""
                save_data()
                st.success("Everything reset!")
                st.rerun()

        st.markdown("---")

        # --- Vote Schedule ---
        st.markdown("**📅 Vote Schedule**")
        st.caption("Set start & end date/time — voting will auto open/close")
        sc1, sc2 = st.columns(2)
        with sc1:
            start_date = st.date_input("Start Date", value=date.today(), key="sched_start_date")
            start_time_str = st.text_input("Start Time (HH:MM)", value="09:00", key="sched_start_time")
        with sc2:
            end_date = st.date_input("End Date", value=date.today(), key="sched_end_date")
            end_time_str = st.text_input("End Time (HH:MM)", value="18:00", key="sched_end_time")

        btn1, btn2, _ = st.columns([1, 1, 2])
        with btn1:
            set_sched = st.button("Set", use_container_width=True)
        with btn2:
            clear_sched = st.button("Clear", use_container_width=True)

        if set_sched:
            try:
                start_time_parsed = datetime.strptime(start_time_str.strip(), "%H:%M").time()
                end_time_parsed = datetime.strptime(end_time_str.strip(), "%H:%M").time()
            except ValueError:
                st.error("❌ Invalid time format! Use HH:MM (e.g. 09:00, 14:30)")
                st.stop()
            start_dt = datetime.combine(start_date, start_time_parsed)
            end_dt = datetime.combine(end_date, end_time_parsed)
            if end_dt <= start_dt:
                st.error("❌ End time must be after start time!")
            else:
                st.session_state.schedule_start = start_dt.isoformat()
                st.session_state.schedule_end = end_dt.isoformat()
                now = datetime.now()
                if start_dt <= now <= end_dt:
                    st.session_state.voting_open = True
                else:
                    st.session_state.voting_open = False
                save_data()
                st.success(f"✅ Scheduled: {start_dt.strftime('%d %b %Y, %I:%M %p')} — {end_dt.strftime('%d %b %Y, %I:%M %p')}")
                st.rerun()

        if st.session_state.schedule_start and st.session_state.schedule_end:
            try:
                s = datetime.fromisoformat(st.session_state.schedule_start)
                e = datetime.fromisoformat(st.session_state.schedule_end)
                st.caption(f"📆 Current: {s.strftime('%d %b %Y, %I:%M %p')} — {e.strftime('%d %b %Y, %I:%M %p')}")
            except:
                pass

        if clear_sched:
            st.session_state.schedule_start = ""
            st.session_state.schedule_end = ""
            save_data()
            st.success("Schedule cleared!")
            st.rerun()

        # Auto-refresh admin panel every 5 seconds for live voting stats
        st_autorefresh(interval=5000, limit=None, key="admin_live_refresh")
