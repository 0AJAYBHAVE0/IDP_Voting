import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, date, time

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voting_data.db")
LIVE_DB_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "live_voting_data.db"
)


def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=5, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS contestants (
        number TEXT PRIMARY KEY,
        name TEXT,
        photo TEXT
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS votes (
        contestant_number TEXT,
        voter_email TEXT,
        timestamp TEXT,
        PRIMARY KEY (contestant_number, voter_email)
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS vote_changes (
        voter_email TEXT PRIMARY KEY,
        changed_once INTEGER DEFAULT 0
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS voters (
        email TEXT PRIMARY KEY,
        name TEXT
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )"""
    )
    conn.commit()
    conn.close()


def init_live_db():
    conn = sqlite3.connect(LIVE_DB_FILE, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS live_votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contestant_number TEXT,
        voter_email TEXT,
        timestamp TEXT,
        is_edit INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending'
    )"""
    )
    conn.commit()
    conn.close()


def clear_live_votes_db():
    """Wipes the live votes cache (used when Admin resets votes)."""
    try:
        conn = sqlite3.connect(LIVE_DB_FILE, timeout=5, check_same_thread=False)
        conn.execute("DELETE FROM live_votes")
        conn.commit()
        conn.close()
    except Exception:
        pass


def sync_live_to_primary_db():
    """Background task to transfer 'pending' votes from live DB to primary DB."""
    try:
        live_conn = sqlite3.connect(LIVE_DB_FILE, timeout=5, check_same_thread=False)
        live_c = live_conn.cursor()
        live_c.execute(
            "SELECT id, contestant_number, voter_email, timestamp, is_edit FROM live_votes WHERE status = 'pending'"
        )
        pending_votes = live_c.fetchall()
        if not pending_votes:
            live_conn.close()
            return
        primary_conn = sqlite3.connect(DB_FILE, timeout=5, check_same_thread=False)
        primary_c = primary_conn.cursor()
        primary_conn.execute("BEGIN TRANSACTION")
        synced_ids = []
        edits_processed = set()
        for row in pending_votes:
            id_val, pick, email, ts, is_edit = row
            if is_edit and email not in edits_processed:
                primary_c.execute("DELETE FROM votes WHERE voter_email = ?", (email,))
                primary_c.execute(
                    "INSERT OR REPLACE INTO vote_changes (voter_email, changed_once) VALUES (?, 1)",
                    (email,),
                )
                edits_processed.add(email)
            primary_c.execute(
                "INSERT OR IGNORE INTO votes (contestant_number, voter_email, timestamp) VALUES (?, ?, ?)",
                (pick, email, ts),
            )
            synced_ids.append(id_val)
        primary_conn.commit()
        primary_conn.close()
        if synced_ids:
            placeholders = ",".join(["?"] * len(synced_ids))
            live_c.execute(
                f"UPDATE live_votes SET status = 'synced' WHERE id IN ({placeholders})",
                tuple(synced_ids),
            )
            live_conn.commit()
            live_c.execute("DELETE FROM live_votes WHERE status = 'synced'")
            live_conn.commit()
        live_conn.close()
    except Exception as e:
        print(f"Sync error: {e}")
        pass


init_db()
init_live_db()


def load_data():
    """Load all data from SQLite database"""
    conn = sqlite3.connect(DB_FILE, timeout=5, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT number, name, photo FROM contestants")
    contestants = [
        {"Number": row[0], "Name": row[1], "Photo": row[2]} for row in c.fetchall()
    ]
    c.execute("SELECT contestant_number, voter_email, timestamp FROM votes")
    votes = {}
    voted_emails = set()
    voter_picks = {}
    vote_timestamps = {}
    for row in c.fetchall():
        votes[row[0]] = votes.get(row[0], 0) + 1
        voted_emails.add(row[1])
        voter_picks.setdefault(row[1], []).append(row[0])
        vote_timestamps[row[1]] = row[2]
    c.execute("SELECT voter_email, changed_once FROM vote_changes")
    vote_changed_users = {row[0]: bool(row[1]) for row in c.fetchall()}
    c.execute("SELECT email, name FROM voters")
    allowed_voters = [{"Email": row[0], "Name": row[1]} for row in c.fetchall()]
    c.execute("SELECT key, value FROM settings")
    settings = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    try:
        live_conn = sqlite3.connect(LIVE_DB_FILE, timeout=5, check_same_thread=False)
        live_c = live_conn.cursor()
        live_c.execute(
            "SELECT contestant_number, voter_email, timestamp, is_edit FROM live_votes WHERE status = 'pending'"
        )
        for row in live_c.fetchall():
            pick, email, ts, is_edit = row
            if (
                is_edit
                and email in voted_emails
                and not vote_changed_users.get(email, False)
            ):
                old_picks = voter_picks.get(email, [])
                for old in old_picks:
                    if old in votes and votes[old] > 0:
                        votes[old] -= 1
                voter_picks[email] = []
                vote_changed_users[email] = True
            voted_emails.add(email)
            if pick not in voter_picks.get(email, []):
                voter_picks.setdefault(email, []).append(pick)
            votes[pick] = votes.get(pick, 0) + 1
            vote_timestamps[email] = ts
        live_conn.close()
    except Exception:
        pass
    data = {
        "contestants": contestants,
        "votes": votes,
        "allowed_voters": allowed_voters,
        "voted_emails": list(voted_emails),
        "voter_picks": voter_picks,
        "vote_timestamps": vote_timestamps,
        "vote_changed_users": vote_changed_users,
        "voting_open": settings.get("voting_open", "True") == "True",
        "schedule_start": settings.get("schedule_start", ""),
        "schedule_end": settings.get("schedule_end", ""),
        "app_title": settings.get("app_title", "🎤 IDP Got Talent 💃"),
        "app_subtitle": settings.get(
            "app_subtitle", "Vote for your favourite performers!"
        ),
        "admin_password": settings.get("admin_password", "Admin123"),
        "allow_vote_change": settings.get("allow_vote_change", "False") == "True",
        "max_votes": int(settings.get("max_votes", 3)),
        "show_live_results": settings.get("show_live_results", "False") == "True",
        "show_live_voter_count": settings.get("show_live_voter_count", "True")
        == "True",
        "custom_message": settings.get("custom_message", ""),
    }
    return data


def save_data():
    """Save all data to SQLite database from session_state"""
    conn = sqlite3.connect(DB_FILE, timeout=5, check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM contestants")
    for cst in st.session_state.contestants:
        c.execute(
            "INSERT INTO contestants (number, name, photo) VALUES (?, ?, ?)",
            (cst["Number"], cst["Name"], cst.get("Photo", "")),
        )
    c.execute("DELETE FROM voters")
    for v in st.session_state.allowed_voters:
        c.execute(
            "INSERT INTO voters (email, name) VALUES (?, ?)",
            (v["Email"], v["Name"]),
        )
    c.execute("DELETE FROM votes")
    for voter_email, picks in st.session_state.voter_picks.items():
        for pick in picks:
            ts = st.session_state.vote_timestamps.get(voter_email, "")
            c.execute(
                "INSERT INTO votes (contestant_number, voter_email, timestamp) VALUES (?, ?, ?)",
                (pick, voter_email, ts),
            )
    c.execute("DELETE FROM vote_changes")
    for voter_email, changed_once in st.session_state.vote_changed_users.items():
        c.execute(
            "INSERT INTO vote_changes (voter_email, changed_once) VALUES (?, ?)",
            (voter_email, int(changed_once)),
        )
    c.execute("DELETE FROM settings")
    settings = {
        "voting_open": str(st.session_state.voting_open),
        "schedule_start": st.session_state.schedule_start,
        "schedule_end": st.session_state.schedule_end,
        "app_title": st.session_state.app_title,
        "app_subtitle": st.session_state.app_subtitle,
        "admin_password": st.session_state.admin_password,
        "allow_vote_change": str(st.session_state.allow_vote_change),
        "max_votes": str(st.session_state.max_votes),
        "show_live_results": str(st.session_state.show_live_results),
        "show_live_voter_count": str(st.session_state.show_live_voter_count),
        "custom_message": st.session_state.custom_message,
    }
    for k, v in settings.items():
        c.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()


def submit_vote_to_db(voter_email, selected_picks, is_edit=False):
    """Insert a vote swiftly into the live cache DB. Background sync will handle the rest."""
    conn = sqlite3.connect(LIVE_DB_FILE, timeout=5, check_same_thread=False)
    c = conn.cursor()
    try:
        timestamp = datetime.now().isoformat()
        edit_flag = 1 if is_edit else 0
        for pick in selected_picks:
            c.execute(
                "INSERT INTO live_votes (contestant_number, voter_email, timestamp, is_edit, status) VALUES (?, ?, ?, ?, 'pending')",
                (pick, voter_email, timestamp, edit_flag),
            )
        conn.commit()
    except Exception as e:
        print(f"Error saving vote to live cache: {e}")
    finally:
        conn.close()


def get_contestant_label(c):
    """Get display label for a contestant dict"""
    num = str(c.get("Number", ""))
    name = c.get("Name", "")
    if name:
        return f"#{num} - {name}"
    return f"#{num}"


def save_setting(key, value):
    """Update a single setting in the DB without touching votes/contestants/voters."""
    conn = sqlite3.connect(DB_FILE, timeout=5, check_same_thread=False)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()
    conn.close()


def get_live_voter_count_html(total_voted):
    digits = f"{total_voted:04d}"
    digit_html = ""
    for idx, d in enumerate(digits):
        delay = idx * 0.1
        digit_html += (
            f'<div key="digit-{idx}-{d}-{total_voted}" '
            f'style="animation: flipClock_{total_voted} 0.6s cubic-bezier(0.4, 0.0, 0.2, 1) both; '
            f"animation-delay: {delay}s; transform-origin: 50% 50%; "
            f"background: linear-gradient(to bottom, #333 0%, #111 100%); color: #fff; "
            f"font-size: 48px; font-weight: bold; padding: 10px 15px; border-radius: 8px; "
            f"box-shadow: 0 4px 10px rgba(0,0,0,0.3), inset 0 2px 0 rgba(255,255,255,0.2); "
            f"font-family: 'Courier New', monospace; line-height: 1; position: relative; "
            f'text-align: center; min-width: 35px; display: inline-block;">'
            f"{d}"
            f'<div style="position: absolute; top: 50%; left: 0; right: 0; height: 2px; '
            f"margin-top: -1px; background: rgba(0,0,0,0.8); "
            f'box-shadow: 0 1px 0 rgba(255,255,255,0.2);"></div></div>'
        )
    return f"""
        <style>
        @keyframes flipClock_{total_voted} {{
          0% {{ transform: perspective(400px) rotateX(-90deg); opacity: 0; }}
          100% {{ transform: perspective(400px) rotateX(0deg); opacity: 1; }}
        }}
        </style>
        <div key="counter-box-{total_voted}" style="display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 30px;">
            <div style="color: #555; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px; display: flex; align-items: center;">
                Live Voter Count <span class="live-badge" style="margin-left: 10px; font-size: 10px; padding: 3px 8px;">● LIVE</span>
            </div>
            <div style="display: flex; justify-content: center; gap: 8px; perspective: 1000px;">
                {digit_html}
            </div>
        </div>
        """


def get_live_results_html(contestants, votes):
    total_votes = sum(votes.values())
    if total_votes == 0:
        return (
            '<div class="stAlert"><div class="st-info">No votes yet.</div></div>',
            total_votes,
        )
    sorted_contestants = sorted(
        contestants,
        key=lambda c: votes.get(get_contestant_label(c), 0),
        reverse=True,
    )
    sorted_labels = [get_contestant_label(c) for c in sorted_contestants]
    sorted_counts = [votes.get(lbl, 0) for lbl in sorted_labels]
    html = ""
    medal_emoji = ["🥇", "🥈", "🥉"]
    podium_class = ["podium-gold", "podium-silver", "podium-bronze"]
    podium_candidates = [
        (lbl, cnt) for lbl, cnt in zip(sorted_labels, sorted_counts) if cnt > 0
    ]
    top3 = min(3, len(podium_candidates))
    if top3 > 0:
        podium_html = '<div class="podium-container">'
        for i in range(top3):
            lbl, cnt = podium_candidates[i]
            podium_html += f"""
                <div class="podium-block {podium_class[i]}">
                    <div class="podium-rank">{medal_emoji[i]}</div>
                    <div class="podium-name">{lbl}</div>
                    <div class="podium-votes">{cnt} votes</div>
                </div>"""
        podium_html += "</div>"
        html += podium_html
    html += '<div><h3 style="margin-top:20px;">Top 5 Scoreboard</h3></div>'
    voted_contestants = [
        (lbl, cnt) for lbl, cnt in zip(sorted_labels, sorted_counts) if cnt > 0
    ]
    top5_voted = voted_contestants[:5]
    max_count = max([cnt for _, cnt in top5_voted]) if top5_voted else 1
    rank_icons = {0: "🥇", 1: "🥈", 2: "🥉", 3: "4️⃣", 4: "5️⃣"}
    for i, (lbl, cnt) in enumerate(top5_voted):
        pct = int((cnt / max_count) * 100) if max_count > 0 else 0
        pct_total = int((cnt / total_votes) * 100) if total_votes > 0 else 0
        icon = rank_icons.get(i, f"#{i+1}")
        html += f"""
            <div class="results-bar-container">
                <div class="results-bar-header">
                    <span class="results-bar-name">{icon} {lbl}</span>
                    <span class="results-bar-count">{cnt} votes ({pct_total}%)</span>
                </div>
                <div class="results-bar-track">
                    <div class="results-bar-fill" style="width: {pct}%;"></div>
                </div>
            </div>"""
    html += f"<p style='text-align:center; color:#888; margin-top:16px;'>🗳️ Total Votes Cast: <b>{total_votes}</b></p>"
    return html, total_votes


@st.fragment()
def voter_interaction_widget():
    """Voter interaction area — polls DB every 5s so admin resets/open/close are reflected instantly."""
    fresh = load_data()
    if fresh["schedule_start"] and fresh["schedule_end"]:
        try:
            e_dt = datetime.fromisoformat(fresh["schedule_end"])
            if datetime.now() > e_dt and fresh["voting_open"]:
                save_setting("voting_open", "False")
                save_setting("schedule_start", "")
                save_setting("schedule_end", "")
                fresh["voting_open"] = False
                fresh["schedule_start"] = ""
                fresh["schedule_end"] = ""
        except Exception:
            pass
    if not fresh["voting_open"]:
        if fresh["schedule_start"] and fresh["schedule_end"]:
            try:
                s_dt = datetime.fromisoformat(fresh["schedule_start"])
                e_dt = datetime.fromisoformat(fresh["schedule_end"])
                now_check = datetime.now()
                if now_check < s_dt:
                    st.warning(
                        f"⏳ Voting will open on **{s_dt.strftime('%d %b %Y, %I:%M %p')}**"
                    )
                elif now_check > e_dt:
                    st.warning(
                        f"⏸️ Voting ended on **{e_dt.strftime('%d %b %Y, %I:%M %p')}**"
                    )
                else:
                    st.warning("⏸️ Voting is currently closed.")
            except Exception:
                st.warning("⏸️ Voting is currently closed. Please check back later.")
        else:
            st.warning("⏸️ Voting is currently closed. Please check back later.")
        return
    contestants = fresh["contestants"]
    contestant_labels = [get_contestant_label(c) for c in contestants]
    already_voted = st.session_state.voter_email in set(fresh["voted_emails"])
    can_edit_vote = fresh["allow_vote_change"]
    has_changed_vote = fresh["vote_changed_users"].get(
        st.session_state.voter_email, False
    )
    st.session_state.voted_emails = set(fresh["voted_emails"])
    st.session_state.voter_picks = fresh["voter_picks"]
    st.session_state.vote_changed_users = fresh["vote_changed_users"]
    st.session_state.votes = fresh["votes"]
    st.success(f"✅ Welcome, **{st.session_state.voter_name}**!")
    if already_voted and (not can_edit_vote or (can_edit_vote and has_changed_vote)):
        my_picks = fresh["voter_picks"].get(st.session_state.voter_email, [])
        if can_edit_vote and has_changed_vote:
            st.success(
                f"✏️ You have already changed your vote once. Your final vote: {', '.join(my_picks)}"
            )
        elif my_picks:
            st.success(
                f"🎉 Thanks {st.session_state.voter_name}! You voted for: {', '.join(my_picks)}"
            )
        else:
            st.info("✅ You have already voted. Thank you!")
    elif len(contestants) == 0:
        st.info("No contestants added yet.")
    else:
        if already_voted and can_edit_vote and not has_changed_vote:
            my_picks = fresh["voter_picks"].get(st.session_state.voter_email, [])
            st.info(
                f"✏️ Vote edit is enabled. Your current vote: **{', '.join(my_picks)}**. You can change it below. (You can only change your vote once.)"
            )
        if fresh["custom_message"]:
            st.info(fresh["custom_message"], icon="📢")
        has_any_photos = any(
            str(c.get("Photo", "")).strip()
            and str(c.get("Photo", "")).strip().lower() != "nan"
            for c in contestants
        )
        if has_any_photos:
            st.markdown("### 🎭 Performers", unsafe_allow_html=True)
            grid_cols = st.columns(3)
            for idx, c in enumerate(contestants):
                with grid_cols[idx % 3]:
                    photo_url = str(c.get("Photo", "")).strip()
                    c_name = str(c.get("Name", "C")).strip()
                    c_num = str(c.get("Number", "")).strip()
                    if not photo_url or photo_url.lower() == "nan":
                        photo_url = f"https://ui-avatars.com/api/?name={c_name}&background=random&color=fff&size=150"
                    st.markdown(
                        f"""
                    <div style="text-align:center; padding:12px; background:#fff; border-radius:12px; margin-bottom:15px; box-shadow:0 4px 12px rgba(0,0,0,0.08); border: 1px solid #eee;">
                        <img src="{photo_url}" style="width:100px; height:100px; border-radius:50%; object-fit:cover; margin-bottom:12px; border: 3px solid #ffdbdb; padding:2px;">
                        <div style="font-weight:800; font-size:16px; color:#FF4B4B; margin-bottom:2px;">#{c_num}</div>
                        <div style="font-weight:600; font-size:14px; color:#333; line-height:1.2;">{c_name}</div>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
            st.markdown("---")
        st.markdown(
            f"<p style='font-size:20px; font-weight:600; margin-bottom:4px;'>🗳️ Select your Top {fresh['max_votes']} performers</p>",
            unsafe_allow_html=True,
        )
        default_picks = []
        if already_voted and can_edit_vote:
            prev = fresh["voter_picks"].get(st.session_state.voter_email, [])
            default_picks = [p for p in prev if p in contestant_labels]
        selected = st.multiselect(
            "Choose your favourites:",
            options=contestant_labels,
            default=default_picks,
            key="vote_select",
        )
        btn_label = "✅ Update Vote" if already_voted else "✅ Submit"
        can_submit = not already_voted or (
            already_voted and can_edit_vote and not has_changed_vote
        )
        if st.button(btn_label) and can_submit:
            if len(selected) < fresh["max_votes"]:
                st.warning(f"Please select exactly {fresh['max_votes']} performers!")
            elif len(selected) > fresh["max_votes"]:
                st.error(f"You can vote for maximum {fresh['max_votes']} performers!")
            else:
                is_edit = already_voted and can_edit_vote and not has_changed_vote
                submit_vote_to_db(st.session_state.voter_email, selected, is_edit)
                st.session_state.show_balloons = True
                st.rerun()


@st.fragment(run_every=5)
def voting_closed_banner_widget():
    """Shows real-time open/closed status for non-logged-in visitors.
    Triggers a full rerun when admin opens voting so the login form appears instantly.
    Also proactively opens/closes voting when a schedule window is reached."""
    sync_live_to_primary_db()
    fresh = load_data()
    now_check = datetime.now()
    if fresh["schedule_start"] and fresh["schedule_end"]:
        try:
            s_dt = datetime.fromisoformat(fresh["schedule_start"])
            e_dt = datetime.fromisoformat(fresh["schedule_end"])
            if s_dt <= now_check <= e_dt and not fresh["voting_open"]:
                save_setting("voting_open", "True")
                st.session_state.voting_open = True
                st.rerun()
                return
            elif now_check > e_dt and fresh["voting_open"]:
                save_setting("voting_open", "False")
                save_setting("schedule_start", "")
                save_setting("schedule_end", "")
                st.session_state.voting_open = False
                st.rerun()
                return
        except Exception:
            pass
    if fresh["voting_open"]:
        if not st.session_state.voting_open:
            st.session_state.voting_open = True
            st.rerun()
        return
    if fresh["schedule_start"] and fresh["schedule_end"]:
        try:
            s_dt = datetime.fromisoformat(fresh["schedule_start"])
            e_dt = datetime.fromisoformat(fresh["schedule_end"])
            if now_check < s_dt:
                st.warning(
                    f"⏳ Voting will open on **{s_dt.strftime('%d %b %Y, %I:%M %p')}**"
                )
            elif now_check > e_dt:
                st.warning(
                    f"⏸️ Voting ended on **{e_dt.strftime('%d %b %Y, %I:%M %p')}**"
                )
            else:
                st.warning("⏸️ Voting is currently closed.")
        except Exception:
            st.warning("⏸️ Voting is currently closed. Please check back later.")
    else:
        st.warning("⏸️ Voting is currently closed. Please check back later.")


@st.fragment(run_every=5)
def live_voter_count_widget():
    fresh = load_data()
    total_voted = len(fresh["voted_emails"])
    st.markdown(get_live_voter_count_html(total_voted), unsafe_allow_html=True)


@st.fragment(run_every=5)
def voter_live_panel_widget():
    """
    Polls DB every 5 s and shows/hides Live Voter Count + Live Results
    in real-time based on the admin's current Advanced Settings.
    This ensures that toggling either setting in the admin panel is
    reflected instantly on every voter's screen without a page reload.
    Also hides everything instantly when admin closes voting.
    """
    sync_live_to_primary_db()
    fresh = load_data()
    if not fresh["voting_open"]:
        return
    if fresh["show_live_voter_count"]:
        total_voted = len(fresh["voted_emails"])
        st.markdown(get_live_voter_count_html(total_voted), unsafe_allow_html=True)
    if fresh["show_live_results"]:
        contestants = fresh["contestants"]
        votes = fresh["votes"]
        st.markdown("---")
        st.markdown(
            '## Live Results <span class="live-badge">● LIVE</span>',
            unsafe_allow_html=True,
        )
        html, total_votes = get_live_results_html(contestants, votes)
        if html.startswith('<div class="stAlert">'):
            st.info("No votes yet.")
        else:
            st.markdown(html, unsafe_allow_html=True)


@st.fragment(run_every=5)
def schedule_watcher_widget():
    """General voting-state sync fragment.
    Polls DB every 5 s while the voter is on the login form (voting_open=True in session).
    Handles three cases so the voter page always reflects reality without a manual refresh.
    """
    sync_live_to_primary_db()
    fresh = load_data()
    now_check = datetime.now()
    if fresh["schedule_start"] and fresh["schedule_end"]:
        try:
            s_dt = datetime.fromisoformat(fresh["schedule_start"])
            e_dt = datetime.fromisoformat(fresh["schedule_end"])
            if s_dt <= now_check <= e_dt and not fresh["voting_open"]:
                save_setting("voting_open", "True")
                fresh["voting_open"] = True
            elif now_check > e_dt and fresh["voting_open"]:
                save_setting("voting_open", "False")
                save_setting("schedule_start", "")
                save_setting("schedule_end", "")
                fresh["voting_open"] = False
        except Exception:
            pass
    if fresh["voting_open"] != st.session_state.voting_open:
        st.session_state.voting_open = fresh["voting_open"]
        st.rerun()
        return


@st.fragment(run_every=5)
def admin_stats_widget():
    """Polls DB every 5 s — keeps Voting Stats table and CSV export fresh in real-time."""
    sync_live_to_primary_db()
    fresh = load_data()
    if fresh["voting_open"]:
        stats_badge = '<span class="live-badge">● LIVE</span>'
    else:
        stats_badge = '<span style="display:inline-block;background:#888;color:white;padding:3px 12px;border-radius:20px;font-size:13px;font-weight:600;margin-left:10px;">● CLOSED</span>'
    st.markdown(f"### 📊 Voting Stats {stats_badge}", unsafe_allow_html=True)
    total_voted = len(fresh["voted_emails"])
    st.caption(f"🗳️ {total_voted} voters have voted")
    if total_voted > 0:
        voter_name_map = {
            v["Email"].strip().lower(): v["Name"].strip()
            for v in fresh["allowed_voters"]
        }
        admin_contestants = fresh["contestants"]
        if admin_contestants:
            admin_total = sum(fresh["votes"].values())
            sorted_c = sorted(
                admin_contestants,
                key=lambda c: fresh["votes"].get(get_contestant_label(c), 0),
                reverse=True,
            )
            sorted_lbls = [get_contestant_label(c) for c in sorted_c]
            sorted_cnts = [fresh["votes"].get(l, 0) for l in sorted_lbls]
            medal_emoji = ["🥇", "🥈", "🥉"]
            podium_colors = [
                "linear-gradient(135deg,#FFD700,#FFA500)",
                "linear-gradient(135deg,#C0C0C0,#A8A8A8)",
                "linear-gradient(135deg,#CD7F32,#A0522D)",
            ]
            podium_candidates = [
                (l, cnt) for l, cnt in zip(sorted_lbls, sorted_cnts) if cnt > 0
            ]
            top3 = min(3, len(podium_candidates))
            if top3 > 0:
                podium_html = '<div style="display:flex;justify-content:center;align-items:flex-end;gap:8px;margin:10px auto;">'
                display_order = [1, 0, 2] if top3 == 3 else list(range(top3))
                for i in display_order:
                    if i >= top3:
                        continue
                    lbl, cnt = podium_candidates[i]
                    color = podium_colors[i]
                    podium_html += f"""
                    <div style="text-align:center;border-radius:10px 10px 0 0;padding:8px 6px 6px;min-width:80px;height:70px;background:{color};box-shadow:0 2px 10px rgba(0,0,0,0.15);display:flex;flex-direction:column;justify-content:flex-end;align-items:center;">
                        <div style="font-size:20px;">{medal_emoji[i]}</div>
                        <div style="font-size:11px;font-weight:700;color:#fff;text-shadow:1px 1px 2px rgba(0,0,0,0.3);word-break:break-word;">{lbl}</div>
                        <div style="font-size:14px;font-weight:800;color:#fff;margin-top:4px;">{cnt}v</div>
                    </div>"""
                podium_html += "</div>"
                st.markdown(podium_html, unsafe_allow_html=True)
            if admin_total > 0:
                st.markdown(
                    f"<p style='text-align:center;color:#888;margin-top:8px;font-size:13px;'>🗳️ Total Votes: <b>{admin_total}</b></p>",
                    unsafe_allow_html=True,
                )
        stats_rows = []
        display_rows = []
        for email in fresh["voted_emails"]:
            name = voter_name_map.get(email, email)
            picks = fresh["voter_picks"].get(email, [])
            voted_time_raw = fresh["vote_timestamps"].get(email, "—")
            try:
                dt_obj = datetime.fromisoformat(voted_time_raw)
                display_time = dt_obj.strftime("%d %b %Y, %I:%M:%S %p")
                sort_key = dt_obj.isoformat()
            except Exception:
                display_time = voted_time_raw
                sort_key = voted_time_raw
            display_rows.append(
                {
                    "Voter": name,
                    "Voted For": ", ".join(picks) if picks else "—",
                    "Time": display_time,
                    "_sort_key": sort_key,
                }
            )
            for pick in picks:
                stats_rows.append(
                    {
                        "Voter": name,
                        "Email": email,
                        "Voted For": pick,
                        "Time": display_time,
                        "_sort_key": sort_key,
                    }
                )
        stats_rows.sort(key=lambda r: r["_sort_key"], reverse=True)
        display_rows.sort(key=lambda r: r["_sort_key"], reverse=True)
        for r in stats_rows:
            r.pop("_sort_key", None)
        for r in display_rows:
            r.pop("_sort_key", None)
        full_df = pd.DataFrame(stats_rows)
        display_df = pd.DataFrame(display_rows)
        if not display_df.empty:
            display_df = display_df[["Voter", "Voted For", "Time"]]
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=200)
        csv_data = full_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Results to CSV",
            data=csv_data,
            file_name=f"IDP_Voting_Results_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No votes yet.")


@st.fragment(run_every=5)
def live_results_widget():
    fresh = load_data()
    contestants = fresh["contestants"]
    votes = fresh["votes"]
    st.markdown("---")
    st.markdown(
        '## Live Results <span class="live-badge">● LIVE</span>',
        unsafe_allow_html=True,
    )
    html, total_votes = get_live_results_html(contestants, votes)
    if html.startswith('<div class="stAlert">'):
        st.info("No votes yet.")
    else:
        st.markdown(html, unsafe_allow_html=True)


st.set_page_config(
    page_title="IDP Got Talent Show - Voting",
    page_icon="https://images.ctfassets.net/8bbwomjfix8m/55AePSl50ZnwVBce2lROSW/ff063dcfbec1eb176c59e2179eef57e2/idp-logo.svg",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
<style>
/* Hide Streamlit main menu, settings, rerun, and print */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
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
    border-radius: 2px;
    padding: 2px 8px;
    font-size: 9px;
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
""",
    unsafe_allow_html=True,
)
saved = load_data()
if "contestants" not in st.session_state:
    st.session_state.contestants = (
        saved["contestants"]
        if saved
        and isinstance(saved.get("contestants", None), list)
        and len(saved.get("contestants", [])) > 0
        and isinstance(saved["contestants"][0], dict)
        else []
    )
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
    st.session_state.voted_emails = (
        set(saved["voted_emails"]) if saved and "voted_emails" in saved else set()
    )
if "voter_picks" not in st.session_state:
    st.session_state.voter_picks = (
        saved["voter_picks"] if saved and "voter_picks" in saved else {}
    )
if "vote_changed_users" not in st.session_state:
    st.session_state.vote_changed_users = (
        saved["vote_changed_users"] if saved and "vote_changed_users" in saved else {}
    )
if "vote_timestamps" not in st.session_state:
    st.session_state.vote_timestamps = (
        saved["vote_timestamps"] if saved and "vote_timestamps" in saved else {}
    )
if "admin_password" not in st.session_state:
    st.session_state.admin_password = (
        saved["admin_password"] if saved and "admin_password" in saved else "Admin123"
    )
if "allow_vote_change" not in st.session_state:
    st.session_state.allow_vote_change = (
        saved["allow_vote_change"] if saved and "allow_vote_change" in saved else False
    )
if "voting_open" not in st.session_state:
    st.session_state.voting_open = (
        saved["voting_open"] if saved and "voting_open" in saved else True
    )
if "schedule_start" not in st.session_state:
    st.session_state.schedule_start = (
        saved["schedule_start"] if saved and "schedule_start" in saved else ""
    )
if "schedule_end" not in st.session_state:
    st.session_state.schedule_end = (
        saved["schedule_end"] if saved and "schedule_end" in saved else ""
    )
if "app_title" not in st.session_state:
    st.session_state.app_title = (
        saved["app_title"] if saved and "app_title" in saved else "🎤 IDP Got Talent 💃"
    )
if "app_subtitle" not in st.session_state:
    st.session_state.app_subtitle = (
        saved["app_subtitle"]
        if saved and "app_subtitle" in saved
        else "Vote for your favourite performers!"
    )
if "max_votes" not in st.session_state:
    st.session_state.max_votes = (
        saved["max_votes"] if saved and "max_votes" in saved else 3
    )
if "show_live_results" not in st.session_state:
    st.session_state.show_live_results = (
        saved["show_live_results"] if saved and "show_live_results" in saved else False
    )
if "show_live_voter_count" not in st.session_state:
    st.session_state.show_live_voter_count = (
        saved["show_live_voter_count"]
        if saved and "show_live_voter_count" in saved
        else True
    )
if "custom_message" not in st.session_state:
    st.session_state.custom_message = (
        saved["custom_message"] if saved and "custom_message" in saved else ""
    )
if saved:
    if "votes" in saved:
        st.session_state.votes = saved["votes"]
    if (
        isinstance(saved.get("contestants", None), list)
        and len(saved.get("contestants", [])) > 0
        and isinstance(saved["contestants"][0], dict)
    ):
        st.session_state.contestants = saved["contestants"]
    if "voted_emails" in saved:
        st.session_state.voted_emails = set(saved["voted_emails"])
    if "allowed_voters" in saved:
        st.session_state.allowed_voters = saved["allowed_voters"]
    if "voter_picks" in saved:
        st.session_state.voter_picks = saved["voter_picks"]
    if "vote_timestamps" in saved:
        st.session_state.vote_timestamps = saved["vote_timestamps"]
    if "vote_changed_users" in saved:
        st.session_state.vote_changed_users = saved["vote_changed_users"]
    if "admin_password" in saved:
        st.session_state.admin_password = saved["admin_password"]
    if "allow_vote_change" in saved:
        st.session_state.allow_vote_change = saved["allow_vote_change"]
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
    if "max_votes" in saved:
        st.session_state.max_votes = saved["max_votes"]
    if "show_live_results" in saved:
        st.session_state.show_live_results = saved["show_live_results"]
    if "show_live_voter_count" in saved:
        st.session_state.show_live_voter_count = saved["show_live_voter_count"]
    if "custom_message" in saved:
        st.session_state.custom_message = saved["custom_message"]
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
                save_setting("voting_open", "True")
        elif now < start_dt:
            if st.session_state.voting_open:
                st.session_state.voting_open = False
                save_setting("voting_open", "False")
        elif now > end_dt:
            if st.session_state.voting_open:
                st.session_state.voting_open = False
                save_setting("voting_open", "False")
            st.session_state.schedule_start = ""
            st.session_state.schedule_end = ""
            save_setting("schedule_start", "")
            save_setting("schedule_end", "")
    except Exception:
        pass
params = st.query_params
current_page = params.get("page", "voting")
if current_page == "voting":
    if st.session_state.get("show_balloons", False):
        st.session_state.show_balloons = False
        st.balloons()
        confetti_css = ""
        colors = [
            "#FF4B4B",
            "#FFD700",
            "#00E5FF",
            "#FF69B4",
            "#7FFF00",
            "#FF8C00",
            "#DA70D6",
            "#ffffff",
        ]
        import random as _random

        for i in range(60):
            c = _random.choice(colors)
            lft = _random.randint(0, 100)
            sz = _random.randint(7, 16)
            dur = round(_random.uniform(2.5, 5.0), 2)
            dly = round(_random.uniform(0.0, 2.0), 2)
            rot = _random.randint(0, 360)
            shape = "50%" if _random.random() > 0.4 else "0"
            confetti_css += (
                f"#vc-piece-{i}{{left:{lft}vw;width:{sz}px;height:{sz}px;"
                f"background:{c};border-radius:{shape};"
                f"animation:vc-fall {dur}s {dly}s ease-in forwards;}}"
            )
        st.markdown(
            f"""
<style>
#vc-overlay{{
  position:fixed;top:0;left:0;width:100vw;height:100vh;
  z-index:2147483647;pointer-events:none;overflow:hidden;
  animation:vc-bg-fade 0.5s ease 5.5s forwards;
}}
#vc-bg{{
  position:absolute;top:0;left:0;width:100%;height:100%;
  background:rgba(0,0,0,0.68);
}}
#vc-msg{{
  position:absolute;top:50%;left:50%;
  transform:translate(-50%,-50%);
  text-align:center;
  animation:vc-pop 0.65s cubic-bezier(0.34,1.56,0.64,1) both;
}}
.vc-piece{{position:absolute;top:-20px;opacity:0.9;}}
@keyframes vc-fall{{
  0%{{transform:translateY(0) rotate(0deg);opacity:1;}}
  100%{{transform:translateY(105vh) rotate(720deg);opacity:0;}}
}}
@keyframes vc-pop{{
  0%{{transform:translate(-50%,-50%) scale(0);opacity:0;}}
  60%{{transform:translate(-50%,-50%) scale(1.12);}}
  100%{{transform:translate(-50%,-50%) scale(1);opacity:1;}}
}}
@keyframes vc-bg-fade{{to{{opacity:0;}}}}
{confetti_css}
</style>
<div id="vc-overlay">
  <div id="vc-bg"></div>
  <div id="vc-msg">
    <div style="font-size:68px;line-height:1;">🎉</div>
    <div style="font-family:Arial Black,Impact,sans-serif;font-size:52px;font-weight:900;
                color:#fff;letter-spacing:3px;margin:10px 0 6px;
                text-shadow:0 0 30px gold,0 0 60px rgba(255,100,100,0.9);">
      Vote Confirmed!
    </div>
    <div style="font-family:Arial,sans-serif;font-size:20px;color:#FFD700;
                letter-spacing:2px;font-weight:500;">
      Thank you for voting! ✨
    </div>
  </div>
  {''.join(f'<div id="vc-piece-{i}" class="vc-piece"></div>' for i in range(60))}
</div>
""",
            unsafe_allow_html=True,
        )
    contestants = st.session_state.contestants
    contestant_labels = [get_contestant_label(c) for c in contestants]
    st.markdown(
        '<div style="text-align:center;"><a href="?page=voting" target="_self" style="cursor:pointer;"><img src="https://images.ctfassets.net/8bbwomjfix8m/55AePSl50ZnwVBce2lROSW/ff063dcfbec1eb176c59e2179eef57e2/idp-logo.svg" width="180" style="margin-bottom:10px;"></a></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="title">{st.session_state.app_title.replace(chr(10), "<br>")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="subtitle">{st.session_state.app_subtitle.replace(chr(10), "<br>")}</div>',
        unsafe_allow_html=True,
    )
    voting_allowed = st.session_state.voting_open
    if not voting_allowed:
        voting_closed_banner_widget()
    elif not st.session_state.voter_logged_in:
        schedule_watcher_widget()
        if len(st.session_state.allowed_voters) == 0:
            st.warning("Voting is not open yet. Please check back later.")
        else:
            login_email = st.text_input("📧 Enter Official Email")
            if st.button("Continue"):
                if not login_email.strip():
                    st.warning("Please enter official Email!")
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
                        st.error(
                            "❌ Your Email not found in the voter list. Contact Admin."
                        )
    else:
        voter_interaction_widget()
    if (
        st.session_state.voter_logged_in
        and st.session_state.voter_email in st.session_state.voted_emails
    ):
        voter_live_panel_widget()
elif current_page == "admin":
    st.markdown('<div class="title">🔐 Admin Panel</div>', unsafe_allow_html=True)
    st.markdown("---")
    if not st.session_state.admin_logged_in:
        pwd = st.text_input("Enter Admin Password", type="password")
        if st.button("🔒 Login"):
            if pwd == st.session_state.admin_password:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Wrong password!")
    else:
        admin_stats_widget()
        st.markdown("---")
        st.markdown("**🔄 Control Panel**")
        v1, v2, r1, r2 = st.columns([1, 1, 1, 1])
        with v1:
            if st.session_state.voting_open:
                if st.button("🟢 Open | Close?", use_container_width=True):
                    st.session_state.voting_open = False
                    save_setting("voting_open", "False")
                    st.rerun()
            else:
                if st.button("🔴 Closed | Open?", use_container_width=True):
                    st.session_state.voting_open = True
                    save_setting("voting_open", "True")
                    st.rerun()
        with v2:
            if st.session_state.allow_vote_change:
                if st.button("✏️ Edit ON | OFF?", use_container_width=True):
                    st.session_state.allow_vote_change = False
                    save_setting("allow_vote_change", "False")
                    st.rerun()
            else:
                if st.button("✏️ Edit OFF | ON?", use_container_width=True):
                    st.session_state.allow_vote_change = True
                    save_setting("allow_vote_change", "True")
                    st.rerun()
        with r1:
            if "show_reset_votes_pwd" not in st.session_state:
                st.session_state.show_reset_votes_pwd = False
            if st.button("Reset Votes", use_container_width=True):
                st.session_state.show_reset_votes_pwd = True
            if st.session_state.show_reset_votes_pwd:
                reset_votes_pwd = st.text_input(
                    "Admin Password", type="password", key="reset_votes_pwd_inline"
                )
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Reset", key="confirm_reset_votes_btn_inline"):
                        if reset_votes_pwd != st.session_state.admin_password:
                            st.error("❌ Incorrect admin password!")
                        else:
                            st.session_state.votes = {
                                get_contestant_label(c): 0
                                for c in st.session_state.contestants
                            }
                            st.session_state.voted_emails = set()
                            st.session_state.voter_picks = {}
                            st.session_state.vote_timestamps = {}
                            st.session_state.vote_changed_users = {}
                            st.session_state.show_live_results = False
                            st.session_state.show_live_voter_count = False
                            clear_live_votes_db()
                            save_data()
                            st.session_state.show_reset_votes_pwd = False
                            st.session_state.admin_logged_in = False
                            st.rerun()
                with col2:
                    if st.button("Cancel", key="cancel_reset_votes_btn_inline"):
                        st.session_state.show_reset_votes_pwd = False
                        st.rerun()
        with r2:
            if "show_reset_all_pwd" not in st.session_state:
                st.session_state.show_reset_all_pwd = False
            if st.button("Reset All", use_container_width=True):
                st.session_state.show_reset_all_pwd = True
            if st.session_state.show_reset_all_pwd:
                reset_all_pwd = st.text_input(
                    "Admin Password", type="password", key="reset_all_pwd_inline"
                )
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Reset All", key="confirm_reset_all_btn_inline"):
                        if reset_all_pwd != st.session_state.admin_password:
                            st.error("❌ Incorrect admin password!")
                        else:
                            st.session_state.votes = {
                                get_contestant_label(c): 0
                                for c in st.session_state.contestants
                            }
                            st.session_state.voted_emails = set()
                            st.session_state.voter_picks = {}
                            st.session_state.vote_timestamps = {}
                            st.session_state.contestants = []
                            st.session_state.allowed_voters = []
                            st.session_state.schedule_start = ""
                            st.session_state.schedule_end = ""
                            clear_live_votes_db()
                            save_data()
                            st.session_state.show_reset_all_pwd = False
                            st.session_state.admin_logged_in = False
                            st.rerun()
                with col2:
                    if st.button("Cancel", key="cancel_reset_all_btn_inline"):
                        st.session_state.show_reset_all_pwd = False
                        st.rerun()
        st.markdown("---")

        def save_advanced_settings():
            st.session_state.custom_message = st.session_state.admin_custom_msg
            st.session_state.max_votes = st.session_state.admin_max_votes
            st.session_state.show_live_results = st.session_state.admin_show_live
            st.session_state.show_live_voter_count = (
                st.session_state.admin_show_voter_count
            )
            save_setting("custom_message", st.session_state.custom_message)
            save_setting("max_votes", str(st.session_state.max_votes))
            save_setting("show_live_results", str(st.session_state.show_live_results))
            save_setting(
                "show_live_voter_count", str(st.session_state.show_live_voter_count)
            )

        with st.expander("⚙️ Advanced Settings", expanded=False):
            st.text_input(
                "Custom Announcement (Shows on Voting Page)",
                value=st.session_state.custom_message,
                key="admin_custom_msg",
                on_change=save_advanced_settings,
            )
            st.caption("Leave empty to show no message.")
            st.number_input(
                "Max Votes Per Person",
                min_value=1,
                max_value=20,
                value=st.session_state.max_votes,
                step=1,
                key="admin_max_votes",
                on_change=save_advanced_settings,
            )
            st.checkbox(
                "👁️ Show Live Results on Voting Page",
                value=st.session_state.show_live_results,
                key="admin_show_live",
                on_change=save_advanced_settings,
            )
            st.checkbox(
                "🔢 Show Live Voter Count on Voter Dashboard",
                value=st.session_state.show_live_voter_count,
                key="admin_show_voter_count",
                on_change=save_advanced_settings,
            )
        with st.expander("✏️ Page Title & Subtitle", expanded=False):
            tc1, tc2 = st.columns(2)

            def update_title():
                st.session_state.app_title = st.session_state.edit_title
                save_setting("app_title", st.session_state.app_title)

            def update_subtitle():
                st.session_state.app_subtitle = st.session_state.edit_subtitle
                save_setting("app_subtitle", st.session_state.app_subtitle)

            with tc1:
                st.text_area(
                    "Title",
                    value=st.session_state.app_title,
                    key="edit_title",
                    on_change=update_title,
                    height=100,
                )
            with tc2:
                st.text_area(
                    "Subtitle",
                    value=st.session_state.app_subtitle,
                    key="edit_subtitle",
                    on_change=update_subtitle,
                    height=100,
                )
        with st.expander("📂 Upload CSV Files", expanded=False):
            col_voter, col_contestant = st.columns(2)
            with col_voter:
                st.markdown("**📄 Voter List**")
                st.caption("Columns: `Name`, `Email`")
                uploaded_file = st.file_uploader(
                    "Upload Voter CSV", type=["csv"], label_visibility="collapsed"
                )
                if uploaded_file is not None:
                    try:
                        df = pd.read_csv(
                            uploaded_file,
                            sep=None,
                            engine="python",
                            encoding="utf-8-sig",
                        )
                        df.columns = df.columns.str.strip().str.replace(
                            r"\s+", " ", regex=True
                        )
                        col_map = {col.lower(): col for col in df.columns}
                        name_col = col_map.get("name", None)
                        email_col = col_map.get("email", None)
                        if name_col and email_col:
                            voter_df = (
                                df[[name_col, email_col]]
                                .dropna()
                                .rename(columns={name_col: "Name", email_col: "Email"})
                            )
                            st.session_state.allowed_voters = voter_df.to_dict(
                                "records"
                            )
                            save_data()
                            st.success(
                                f"✅ {len(st.session_state.allowed_voters)} voters loaded"
                            )
                        else:
                            st.error(
                                f"❌ Need 'Name' & 'Email' columns! Found: {list(df.columns)}"
                            )
                    except Exception as e:
                        st.error(f"Error: {e}")
            with col_contestant:
                st.markdown("**🎭 Contestants**")
                st.caption("Columns: `Number`, `Name`, `Photo`(URL)")
                contestants_csv = st.file_uploader(
                    "Upload Contestants CSV",
                    type=["csv"],
                    key="contestants_csv",
                    label_visibility="collapsed",
                )
                if contestants_csv is not None:
                    try:
                        df = pd.read_csv(
                            contestants_csv,
                            sep=None,
                            engine="python",
                            encoding="utf-8-sig",
                        )
                        df.columns = df.columns.str.strip().str.replace(
                            r"\s+", " ", regex=True
                        )
                        col_map = {col.lower(): col for col in df.columns}
                        num_col = col_map.get("number", None)
                        name_col = col_map.get("name", None)
                        photo_col = col_map.get("photo", None)
                        if num_col:
                            df["Number"] = df[num_col].astype(str).str.strip()
                            df["Name"] = (
                                df[name_col].astype(str).str.strip() if name_col else ""
                            )
                            df["Photo"] = (
                                df[photo_col].astype(str).str.strip()
                                if photo_col
                                else ""
                            )
                            df = df.fillna("")
                            df["Name"] = df["Name"].replace("nan", "")
                            df["Photo"] = df["Photo"].replace("nan", "")
                            contestants_list = df[["Number", "Name", "Photo"]].to_dict(
                                "records"
                            )
                            st.session_state.contestants = contestants_list
                            st.session_state.votes = {
                                get_contestant_label(c): 0 for c in contestants_list
                            }
                            st.session_state.voted_emails = set()
                            save_data()
                            st.success(f"✅ {len(contestants_list)} contestants loaded")
                        else:
                            st.error(
                                f"❌ Need 'Number' column! Found: {list(df.columns)}"
                            )
                    except Exception as e:
                        st.error(f"Error: {e}")
            s1, s2 = st.columns(2)
            with s1:
                if len(st.session_state.allowed_voters) > 0:
                    st.caption(
                        f"👥 {len(st.session_state.allowed_voters)} voters loaded"
                    )
            with s2:
                if len(st.session_state.contestants) > 0:
                    st.caption(
                        f"🎭 {len(st.session_state.contestants)} contestants loaded"
                    )
        with st.expander("📅 Vote Schedule", expanded=False):
            st.caption("Set start & end date/time — voting will auto open/close")
            sc1, sc2 = st.columns(2)
            with sc1:
                start_date = st.date_input(
                    "Start Date", value=date.today(), key="sched_start_date"
                )
                start_time_str = st.text_input(
                    "Start Time (HH:MM)", value="09:00", key="sched_start_time"
                )
            with sc2:
                end_date = st.date_input(
                    "End Date", value=date.today(), key="sched_end_date"
                )
                end_time_str = st.text_input(
                    "End Time (HH:MM)", value="18:00", key="sched_end_time"
                )
            btn1, btn2, _ = st.columns([1, 1, 2])
            with btn1:
                set_sched = st.button("Set", use_container_width=True)
            with btn2:
                clear_sched = st.button("Clear", use_container_width=True)
            if set_sched:
                try:
                    start_time_parsed = datetime.strptime(
                        start_time_str.strip(), "%H:%M"
                    ).time()
                    end_time_parsed = datetime.strptime(
                        end_time_str.strip(), "%H:%M"
                    ).time()
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
                    st.success(
                        f"✅ Scheduled: {start_dt.strftime('%d %b %Y, %I:%M %p')} — {end_dt.strftime('%d %b %Y, %I:%M %p')}"
                    )
                    st.rerun()
            if st.session_state.schedule_start and st.session_state.schedule_end:
                try:
                    s = datetime.fromisoformat(st.session_state.schedule_start)
                    e = datetime.fromisoformat(st.session_state.schedule_end)
                    st.caption(
                        f"📆 Current: {s.strftime('%d %b %Y, %I:%M %p')} — {e.strftime('%d %b %Y, %I:%M %p')}"
                    )
                except Exception:
                    pass
            if clear_sched:
                st.session_state.schedule_start = ""
                st.session_state.schedule_end = ""
                save_data()
                st.success("Schedule cleared!")
                st.rerun()
        with st.expander("🔑 Change Admin Password", expanded=False):
            pc1, pc2, pc3 = st.columns(3)
            with pc1:
                cur_pwd = st.text_input(
                    "Current Password", type="password", key="cur_pwd"
                )
            with pc2:
                new_pwd = st.text_input("New Password", type="password", key="new_pwd")
            with pc3:
                confirm_pwd = st.text_input(
                    "Confirm New Password", type="password", key="confirm_pwd"
                )
            if st.button("🔒 Update Password", use_container_width=False):
                if not cur_pwd or not new_pwd or not confirm_pwd:
                    st.warning("⚠️ Please fill all fields.")
                elif cur_pwd != st.session_state.admin_password:
                    st.error("❌ Current password is incorrect!")
                elif new_pwd != confirm_pwd:
                    st.error("❌ New passwords do not match!")
                elif len(new_pwd) < 6:
                    st.warning("⚠️ Password must be at least 6 characters.")
                else:
                    st.session_state.admin_password = new_pwd
                    save_data()
                    st.success("✅ Password updated successfully!")
        if st.button("🔒 Logout", key="logout_bottom"):
            st.session_state.admin_logged_in = False
            st.rerun()
st.markdown(
    """
<hr>
<div style='text-align:center; font-size:14px; color:#4a4a4a; line-height:1.6;'>
Developed By: <b>Kartik Singh</b><br>
Hosted & Managed By: <b>Ajay Bhave</b><br>
© 2026 All Rights Reserved
</div>
""",
    unsafe_allow_html=True,
)
