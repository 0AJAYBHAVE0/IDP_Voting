
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date, time
from streamlit_autorefresh import st_autorefresh
from cryptography.fernet import Fernet

# --- Mega integration ---
try:
    from mega import Mega
except ImportError:
    Mega = None

def get_mega():
    if Mega is None:
        raise ImportError("mega.py is not installed. Run 'pip install mega.py'")
    email = st.secrets["MEGA_EMAIL"]
    password = st.secrets["MEGA_PASSWORD"]
    mega = Mega()
    m = mega.login(email, password)
    return m

def upload_to_mega(local_path, remote_name):
    m = get_mega()
    m.upload(local_path, dest_filename=remote_name)

def download_from_mega(remote_name, local_path):
    m = get_mega()
    files = m.get_files()
    for file_id, file_info in files.items():
        if file_info['a']['n'] == remote_name:
            m.download(file_info, dest_filename=local_path)
            break

KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voting_data.key")
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voting_data.json")

def get_or_create_key():
    """Get encryption key from file, or create it if not exists."""
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    return key

def encrypt_data(data: str) -> bytes:
    key = get_or_create_key()
    f = Fernet(key)
    return f.encrypt(data.encode("utf-8"))

def decrypt_data(token: bytes) -> str:
    key = get_or_create_key()
    f = Fernet(key)
    return f.decrypt(token).decode("utf-8")


def load_data():
    """Load all data from encrypted JSON file"""
    # Download latest files from Mega before loading
    try:
        download_from_mega("voting_data.json", DATA_FILE)
        download_from_mega("voting_data.key", KEY_FILE)
    except Exception as e:
        # If download fails, continue with local files if present
        pass
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            encrypted = f.read()
        try:
            decrypted = decrypt_data(encrypted)
            data = json.loads(decrypted)
            # Convert vote_changed_users to set if present
            if "vote_changed_users" in data:
                data["vote_changed_users"] = set(data["vote_changed_users"])
            return data
        except Exception:
            return None
    return None

def save_data():
    """Save all data to encrypted JSON file"""
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
        "admin_password": st.session_state.admin_password,
        "allow_vote_change": st.session_state.allow_vote_change,
        "max_votes": st.session_state.max_votes,
        "show_live_results": st.session_state.show_live_results,
        "custom_message": st.session_state.custom_message,
        "vote_changed_users": list(st.session_state.vote_changed_users),
    }
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    encrypted = encrypt_data(json_str)
    with open(DATA_FILE, "wb") as f:
        f.write(encrypted)
    # Upload files to Mega after saving
    try:
        upload_to_mega(DATA_FILE, "voting_data.json")
        upload_to_mega(KEY_FILE, "voting_data.key")
    except Exception as e:
        st.warning(f"Could not upload to Mega: {e}")


def get_contestant_label(c):
    """Get display label for a contestant dict"""
    num = str(c.get("Number", ""))
    name = c.get("Name", "")
    if name:
        return f"#{num} - {name}"
    return f"#{num}"


st.set_page_config(
    page_title="IDP Got Talent Show - Voting",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
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
if "vote_changed_users" not in st.session_state:
    if saved and "vote_changed_users" in saved:
        st.session_state.vote_changed_users = set(saved["vote_changed_users"])
    else:
        st.session_state.vote_changed_users = set()
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
                save_data()
        elif now < start_dt:
            if st.session_state.voting_open:
                st.session_state.voting_open = False
                save_data()
        elif now > end_dt:
            if st.session_state.voting_open:
                st.session_state.voting_open = False
            st.session_state.schedule_start = ""
            st.session_state.schedule_end = ""
            save_data()
    except:
        pass
params = st.query_params
current_page = params.get("page", "voting")
if current_page == "voting":
    contestants = st.session_state.contestants
    contestant_labels = [get_contestant_label(c) for c in contestants]
    st.markdown(
        '<div style="text-align:center;"><img src="https://images.ctfassets.net/8bbwomjfix8m/55AePSl50ZnwVBce2lROSW/ff063dcfbec1eb176c59e2179eef57e2/idp-logo.svg" width="180" style="margin-bottom:10px;"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="title">{st.session_state.app_title}</div>', unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="subtitle">{st.session_state.app_subtitle}</div>',
        unsafe_allow_html=True,
    )
    voting_allowed = st.session_state.voting_open
    if not voting_allowed:
        if st.session_state.schedule_start and st.session_state.schedule_end:
            try:
                s_dt = datetime.fromisoformat(st.session_state.schedule_start)
                e_dt = datetime.fromisoformat(st.session_state.schedule_end)
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
            except:
                st.warning("⏸️ Voting is currently closed. Please check back later.")
        else:
            st.warning("⏸️ Voting is currently closed. Please check back later.")
    elif not st.session_state.voter_logged_in:
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
        st.success(f"✅ Welcome, **{st.session_state.voter_name}**!")
        already_voted = st.session_state.voter_email in st.session_state.voted_emails
        vote_changed_users = st.session_state.vote_changed_users
        can_edit_vote = (
            st.session_state.allow_vote_change
            and st.session_state.voter_email not in vote_changed_users
        )
        if already_voted and not st.session_state.allow_vote_change:
            my_picks = st.session_state.voter_picks.get(
                st.session_state.voter_email, []
            )
            if my_picks:
                st.success(
                    f"🎉 Thanks {st.session_state.voter_name}! You voted for: {', '.join(my_picks)}"
                )
            else:
                st.info("✅ You have already voted. Thank you!")
        elif already_voted and st.session_state.allow_vote_change and st.session_state.voter_email in vote_changed_users:
            my_picks = st.session_state.voter_picks.get(
                st.session_state.voter_email, []
            )
            st.success(
                f"✏️ You have already changed your vote once. Your final vote: {', '.join(my_picks)}"
            )
        elif len(contestants) == 0:
            st.info("No contestants added yet.")
        else:
            if already_voted and can_edit_vote:
                my_picks = st.session_state.voter_picks.get(
                    st.session_state.voter_email, []
                )
                st.info(
                    f"✏️ Vote edit is enabled. Your current vote: **{', '.join(my_picks)}**. You can change it below. (You can only change your vote once.)"
                )
            if st.session_state.custom_message:
                st.info(st.session_state.custom_message, icon="📢")
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
                f"<p style='font-size:20px; font-weight:600; margin-bottom:4px;'>🗳️ Select your Top {st.session_state.max_votes} performers</p>",
                unsafe_allow_html=True,
            )
            default_picks = []
            if already_voted and can_edit_vote:
                prev = st.session_state.voter_picks.get(
                    st.session_state.voter_email, []
                )
                default_picks = [p for p in prev if p in contestant_labels]
            selected = st.multiselect(
                "Choose your favourites:",
                options=contestant_labels,
                default=default_picks,
                key="vote_select",
            )
            btn_label = "✅ Update Vote" if already_voted else "✅ Submit"
            if st.button(btn_label):
                if len(selected) < st.session_state.max_votes:
                    st.warning(f"Please select exactly {st.session_state.max_votes} performers!")
                elif len(selected) > st.session_state.max_votes:
                    st.error(
                        f"You can vote for maximum {st.session_state.max_votes} performers!"
                    )
                else:
                    if already_voted and can_edit_vote:
                        old_picks = st.session_state.voter_picks.get(
                            st.session_state.voter_email, []
                        )
                        for old_pick in old_picks:
                            if (
                                old_pick in st.session_state.votes
                                and st.session_state.votes[old_pick] > 0
                            ):
                                st.session_state.votes[old_pick] -= 1
                        # Mark this user as having changed their vote once
                        st.session_state.vote_changed_users.add(st.session_state.voter_email)
                    for pick in selected:
                        st.session_state.votes[pick] = (
                            st.session_state.votes.get(pick, 0) + 1
                        )
                    st.session_state.voted_emails.add(st.session_state.voter_email)
                    st.session_state.voter_picks[st.session_state.voter_email] = (
                        selected
                    )
                    st.session_state.vote_timestamps[st.session_state.voter_email] = (
                        datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
                    )
                    save_data()
                    st.rerun()
    if (
        st.session_state.voter_logged_in
        and st.session_state.voter_email in st.session_state.voted_emails
        and st.session_state.show_live_results
    ):
        st.markdown("---")
        st.markdown(
            '## Live Results <span class="live-badge">● LIVE</span>',
            unsafe_allow_html=True,
        )
        total_votes = sum(st.session_state.votes.values())
        if total_votes == 0:
            st.info("No votes yet.")
        else:
            sorted_contestants = sorted(
                contestants,
                key=lambda c: st.session_state.votes.get(get_contestant_label(c), 0),
                reverse=True,
            )
            sorted_labels = [get_contestant_label(c) for c in sorted_contestants]
            sorted_counts = [
                st.session_state.votes.get(lbl, 0) for lbl in sorted_labels
            ]
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
                st.markdown(podium_html, unsafe_allow_html=True)
            st.markdown("")
            st.markdown("### Top 5 Scoreboard")
            # Only show contestants with at least 1 vote, up to 5 max
            voted_contestants = [(lbl, cnt) for lbl, cnt in zip(sorted_labels, sorted_counts) if cnt > 0]
            top5_voted = voted_contestants[:5]
            max_count = max([cnt for _, cnt in top5_voted]) if top5_voted else 1
            rank_icons = {0: "🥇", 1: "🥈", 2: "🥉", 3: "🥉", 4: "🥉"}
            for i, (lbl, cnt) in enumerate(top5_voted):
                pct = int((cnt / max_count) * 100) if max_count > 0 else 0
                pct_total = int((cnt / total_votes) * 100) if total_votes > 0 else 0
                icon = rank_icons.get(i, f"#{i+1}")
                bar_html = f"""
                <div class="results-bar-container">
                    <div class="results-bar-header">
                        <span class="results-bar-name">{icon} {lbl}</span>
                        <span class="results-bar-count">{cnt} votes ({pct_total}%)</span>
                    </div>
                    <div class="results-bar-track">
                        <div class="results-bar-fill" style="width: {pct}%;"></div>
                    </div>
                </div>"""
                st.markdown(bar_html, unsafe_allow_html=True)
            st.markdown(
                f"<p style='text-align:center; color:#888; margin-top:16px;'>🗳️ Total Votes Cast: <b>{total_votes}</b></p>",
                unsafe_allow_html=True,
            )
    if st.session_state.voter_logged_in:
        st_autorefresh(interval=5000, limit=None, key="live_refresh")
    if st.session_state.schedule_start and st.session_state.schedule_end:
        st_autorefresh(interval=10000, limit=None, key="schedule_refresh")
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
        if st.session_state.voting_open:
            stats_badge = '<span class="live-badge">● LIVE</span>'
        else:
            stats_badge = '<span style="display:inline-block;background:#888;color:white;padding:3px 12px;border-radius:20px;font-size:13px;font-weight:600;margin-left:10px;">● CLOSED</span>'
        st.markdown(
            f"### 📊 Voting Stats {stats_badge}",
            unsafe_allow_html=True,
        )
        total_voted = len(st.session_state.voted_emails)
        total_voters = len(st.session_state.allowed_voters)
        st.caption(f"🗳️ {total_voted} / {total_voters} voters have voted")
        if total_voted > 0:
            voter_name_map = {}
            for v in st.session_state.allowed_voters:
                voter_name_map[v["Email"].strip().lower()] = v["Name"].strip()
            admin_contestants = st.session_state.contestants
            if admin_contestants:
                admin_total = sum(st.session_state.votes.values())
                sorted_c = sorted(
                    admin_contestants,
                    key=lambda c: st.session_state.votes.get(
                        get_contestant_label(c), 0
                    ),
                    reverse=True,
                )
                sorted_lbls = [get_contestant_label(c) for c in sorted_c]
                sorted_cnts = [st.session_state.votes.get(l, 0) for l in sorted_lbls]
                podium_order = [1, 0, 2]
                medal_emoji = ["🥇", "🥈", "🥉"]
                podium_colors = [
                    "linear-gradient(135deg,#FFD700,#FFA500)",
                    "linear-gradient(135deg,#C0C0C0,#A8A8A8)",
                    "linear-gradient(135deg,#CD7F32,#A0522D)",
                ]
                podium_heights = ["70px", "70px", "70px"]
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
                        height = podium_heights[i] if top3 == 3 else "70px"
                        podium_html += f"""
                        <div style="text-align:center;border-radius:10px 10px 0 0;padding:8px 6px 6px;min-width:80px;height:{height};background:{color};box-shadow:0 2px 10px rgba(0,0,0,0.15);display:flex;flex-direction:column;justify-content:flex-end;align-items:center;">
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
            for email in st.session_state.voted_emails:
                name = voter_name_map.get(email, email)
                picks = st.session_state.voter_picks.get(email, [])
                voted_time = st.session_state.vote_timestamps.get(email, "—")
                for pick in picks:
                    stats_rows.append(
                        {
                            "Voter": name,
                            "Email": email,
                            "Voted For": pick,
                            "Time": voted_time,
                        }
                    )
            stats_rows.sort(key=lambda r: r["Time"], reverse=True)
            stats_df = pd.DataFrame(stats_rows)
            st.dataframe(
                stats_df, use_container_width=True, hide_index=True, height=200
            )
            csv_data = stats_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Export Results to CSV",
                data=csv_data,
                file_name=f"IDP_Voting_Results_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )
        else:
            st.info("No votes yet.")
        st.markdown("---")
        st.markdown("**🔄 Control Panel**")
        v1, v2, r1, r2 = st.columns([1, 1, 1, 1])
        with v1:
            if st.session_state.voting_open:
                if st.button("🟢 Open | Close?", use_container_width=True):
                    st.session_state.voting_open = False
                    save_data()
                    st.rerun()
            else:
                if st.button("🔴 Closed | Open?", use_container_width=True):
                    st.session_state.voting_open = True
                    save_data()
                    st.rerun()
        with v2:
            if st.session_state.allow_vote_change:
                if st.button("✏️ Edit ON | OFF?", use_container_width=True):
                    st.session_state.allow_vote_change = False
                    save_data()
                    st.rerun()
            else:
                if st.button("✏️ Edit OFF | ON?", use_container_width=True):
                    st.session_state.allow_vote_change = True
                    save_data()
                    st.rerun()
        # --- Inline password for Reset Votes ---
        with r1:
            if 'show_reset_votes_pwd' not in st.session_state:
                st.session_state.show_reset_votes_pwd = False
            if st.button("Reset Votes", use_container_width=True):
                st.session_state.show_reset_votes_pwd = True
            if st.session_state.show_reset_votes_pwd:
                reset_votes_pwd = st.text_input("Admin Password", type="password", key="reset_votes_pwd_inline")
                col1, col2 = st.columns([1,1])
                with col1:
                    if st.button("Reset", key="confirm_reset_votes_btn_inline"):
                        if reset_votes_pwd != st.session_state.admin_password:
                            st.error("❌ Incorrect admin password!")
                        else:
                            st.session_state.votes = {
                                get_contestant_label(c): 0 for c in st.session_state.contestants
                            }
                            st.session_state.voted_emails = set()
                            st.session_state.voter_picks = {}
                            st.session_state.vote_timestamps = {}
                            save_data()
                            st.success("All votes reset!")
                            st.session_state.show_reset_votes_pwd = False
                            st.rerun()
                with col2:
                    if st.button("Cancel", key="cancel_reset_votes_btn_inline"):
                        st.session_state.show_reset_votes_pwd = False
                        st.rerun()
        # --- Inline password for Reset All ---
        with r2:
            if 'show_reset_all_pwd' not in st.session_state:
                st.session_state.show_reset_all_pwd = False
            if st.button("Reset All", use_container_width=True):
                st.session_state.show_reset_all_pwd = True
            if st.session_state.show_reset_all_pwd:
                reset_all_pwd = st.text_input("Admin Password", type="password", key="reset_all_pwd_inline")
                col1, col2 = st.columns([1,1])
                with col1:
                    if st.button("Reset All", key="confirm_reset_all_btn_inline"):
                        if reset_all_pwd != st.session_state.admin_password:
                            st.error("❌ Incorrect admin password!")
                        else:
                            st.session_state.votes = {
                                get_contestant_label(c): 0 for c in st.session_state.contestants
                            }
                            st.session_state.voted_emails = set()
                            st.session_state.voter_picks = {}
                            st.session_state.vote_timestamps = {}
                            st.session_state.contestants = []
                            st.session_state.allowed_voters = []
                            st.session_state.schedule_start = ""
                            st.session_state.schedule_end = ""
                            save_data()
                            st.success("Everything reset!")
                            st.session_state.show_reset_all_pwd = False
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
            save_data()

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
        with st.expander("✏️ Page Title & Subtitle", expanded=False):
            tc1, tc2 = st.columns(2)
            def update_title():
                st.session_state.app_title = st.session_state.edit_title
                save_data()
            def update_subtitle():
                st.session_state.app_subtitle = st.session_state.edit_subtitle
                save_data()
            with tc1:
                st.text_input(
                    "Title",
                    value=st.session_state.app_title,
                    key="edit_title",
                    on_change=update_title,
                )
            with tc2:
                st.text_input(
                    "Subtitle",
                    value=st.session_state.app_subtitle,
                    key="edit_subtitle",
                    on_change=update_subtitle,
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
                except:
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
        st_autorefresh(interval=5000, limit=None, key="admin_live_refresh")
        if st.button("🔒 Logout", key="logout_bottom"):
            st.session_state.admin_logged_in = False
            st.rerun()
