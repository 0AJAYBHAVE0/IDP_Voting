import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timezone
import os
import pytz

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="IDP GOT TALENT", page_icon="🎤", layout="wide")

# ---------------- CSS ----------------
st.markdown("""
<style>
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}
a[href*="github"] {display:none !important;}

html, body, .stApp {
    background:#0a0a0a;
    color:white;
    font-family:Segoe UI;
}

.block-container {max-width:1100px;}

.header {
    padding:20px;
    border-radius:18px;
    text-align:center;
    margin-bottom:25px;
}

@keyframes glow {
    0% { text-shadow: 0 0 5px #ff003c; }
    50% { text-shadow: 0 0 20px #ff003c; }
    100% { text-shadow: 0 0 5px #ff003c; }
}
.animated-title {animation: glow 2s infinite alternate;}

.credit {
    position: fixed;
    bottom: 12px;
    width: 100%;
    text-align: center;
    font-size: 13px;
    color:#ccc;
}
.credit span { color:#ff003c; font-weight:600; }

.podium {
    background:#151515;
    padding:15px;
    border-radius:12px;
    text-align:center;
}

@keyframes winnerPulse {
  0% { box-shadow: 0 0 5px #ff003c; }
  50% { box-shadow: 0 0 30px #ff003c; }
  100% { box-shadow: 0 0 5px #ff003c; }
}

.winner-card{
    background:#1b1b1b;
    padding:25px;
    border-radius:18px;
    text-align:center;
    animation:winnerPulse 2s infinite;
    margin-bottom:20px;
}

.bar-wrap{
    background:#1a1a1a;
    border-radius:12px;
    margin:8px 0;
    padding:6px;
}

.bar{
    height:22px;
    border-radius:10px;
    background:linear-gradient(90deg,#ff003c,#ff6a00);
    box-shadow:0 0 12px #ff003c;
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ----------------
st.markdown("""
<div class='header'>
    <img src="https://images.ctfassets.net/8bbwomjfix8m/55AePSl50ZnwVBce2lROSW/ff063dcfbec1eb176c59e2179eef57e2/idp-logo.svg" width="220" style="display: block; margin: 0 auto;">
    <h1 class='animated-title'>🌟 𝑰𝑫𝑷 𝑮𝑶𝑻 𝑻𝑨𝑳𝑬𝑵𝑻 2026 🌟</h1>
</div>
""", unsafe_allow_html=True)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("idp_votes.db", check_same_thread=False, timeout=30)
c = conn.cursor()
# Improve concurrency for small multi-writer workloads
c.execute("PRAGMA journal_mode=WAL")

c.execute("""
CREATE TABLE IF NOT EXISTS votes(
email TEXT PRIMARY KEY,
voter_name TEXT,
contestant INTEGER,
time TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS settings(
id INTEGER PRIMARY KEY,
voting_open INTEGER
)
""")

c.execute("INSERT OR IGNORE INTO settings(id,voting_open) VALUES(1,1)")
conn.commit()

# Add optional columns for voting window if missing
try:
    c.execute("ALTER TABLE settings ADD COLUMN start_time TEXT")
except Exception:
    pass
try:
    c.execute("ALTER TABLE settings ADD COLUMN end_time TEXT")
except Exception:
    pass
conn.commit()

# Contestants table (number, name, optional image path)
c.execute("""
CREATE TABLE IF NOT EXISTS contestants(
number INTEGER PRIMARY KEY,
name TEXT,
image TEXT
)
""")

# Audit table for tracking changes
c.execute("""
CREATE TABLE IF NOT EXISTS audit(
id INTEGER PRIMARY KEY AUTOINCREMENT,
email TEXT,
old_contestant INTEGER,
new_contestant INTEGER,
action TEXT,
time TEXT
)
""")
conn.commit()

# Admin password comes from environment (override default in production)
ADMIN_PWD = os.environ.get("IDP_ADMIN_PWD", "admin123")

# ---------------- FUNCTIONS ----------------
def is_voting_open():
    c.execute("SELECT voting_open, start_time, end_time FROM settings WHERE id=1")
    row = c.fetchone()
    if not row:
        return False
    voting_flag, start_s, end_s = row
    
    # DEBUG: Show what we're checking
    # st.write(f"DEBUG - voting_flag: {voting_flag}, start_s: {start_s}, end_s: {end_s}")
    
    if voting_flag != 1:
        return False
    
    # If no time window set, just check voting_flag
    if not start_s and not end_s:
        return True
    
    try:
        # Compare times in UTC
        now = datetime.now(timezone.utc)
        # st.write(f"DEBUG - Current time (UTC): {now}")
        
        if start_s:
            try:
                st_dt = datetime.fromisoformat(start_s)
                if st_dt.tzinfo is None:
                    st_dt = st_dt.replace(tzinfo=timezone.utc)
                else:
                    st_dt = st_dt.astimezone(timezone.utc)
                # st.write(f"DEBUG - Start time (UTC): {st_dt}, Now > Start: {now > st_dt}")
                if now < st_dt:
                    return False
            except Exception as e:
                # st.write(f"DEBUG - Error parsing start_s: {e}")
                pass
        
        if end_s:
            try:
                end_dt = datetime.fromisoformat(end_s)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                else:
                    end_dt = end_dt.astimezone(timezone.utc)
                # st.write(f"DEBUG - End time (UTC): {end_dt}, Now < End: {now < end_dt}")
                if now > end_dt:
                    return False
            except Exception as e:
                # st.write(f"DEBUG - Error parsing end_s: {e}")
                pass
        
        return True
    except Exception as e:
        # st.write(f"DEBUG - Unexpected error in is_voting_open: {e}")
        return False

def set_voting(v):
    c.execute("UPDATE settings SET voting_open=?", (v,))
    conn.commit()

def add_vote(email,name,cno):
    try:
        # read previous contestant for audit
        c.execute("SELECT contestant FROM votes WHERE email=?", (email,))
        prev = c.fetchone()
        prev_c = prev[0] if prev else None

        c.execute("""
        INSERT INTO votes(email,voter_name,contestant,time)
        VALUES(?,?,?,?)
        ON CONFLICT(email) DO UPDATE SET
            voter_name=excluded.voter_name,
            contestant=excluded.contestant,
            time=excluded.time
        """, (email, name, cno, datetime.utcnow().isoformat()))

        # write audit record
        c.execute("INSERT INTO audit(email,old_contestant,new_contestant,action,time) VALUES(?,?,?,?,?)",
                  (email, prev_c, cno, 'vote', datetime.utcnow().isoformat()))
        conn.commit()
    except Exception as e:
        print("Error writing vote:", e)
        raise

def format_iso_to_display(s):
    """Convert ISO datetime string to 'DD-MM-YYYY HH:MM A.M/P.M' in local timezone."""
    if s is None:
        return ""
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        try:
            # fallback parse
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f")
        except Exception:
            return s
    # assume UTC if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc).astimezone()
    else:
        dt = dt.astimezone()
    out = dt.strftime("%d-%m-%Y %I:%M %p")
    out = out.replace("AM", "A.M").replace("PM", "P.M")
    return out

def import_contestants_from_df(df):
    # df expected to have 'number' and 'name' columns, optional 'image'
    for _, row in df.iterrows():
        num = int(row['number'])
        name = str(row.get('name', f'Contestant {num}'))
        img = row.get('image', None)
        c.execute("INSERT OR REPLACE INTO contestants(number,name,image) VALUES(?,?,?)", (num, name, img))
    conn.commit()

def load_contestants():
    df = pd.read_sql("SELECT number,name,image FROM contestants ORDER BY number", conn)
    # return list of tuples (number,name,image)
    return df.to_dict(orient='records')

def results():
    return pd.read_sql("SELECT contestant,COUNT(*) Votes FROM votes GROUP BY contestant ORDER BY Votes DESC",conn)

def all_votes():
    # ISO timestamps sort correctly as strings; order most recent first
    return pd.read_sql("SELECT voter_name,email,contestant,time FROM votes ORDER BY time DESC", conn)

def reset_votes():
    # count for audit
    c.execute("SELECT COUNT(*) FROM votes")
    cnt = c.fetchone()[0]
    c.execute("DELETE FROM votes")
    c.execute("INSERT INTO audit(email,old_contestant,new_contestant,action,time) VALUES(?,?,?,?,?)",
              (None, None, None, f'reset_{cnt}', datetime.utcnow().isoformat()))
    conn.commit()

# ---------------- SIDEBAR ----------------
menu = st.sidebar.selectbox("Mode",["Public Voting","Admin Panel"])

# ================= PUBLIC =================
if menu=="Public Voting":

    if not is_voting_open():
        st.warning("Voting Closed")
        st.stop()
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    contestants = load_contestants()
    with st.form("vote_form"):
        name = st.text_input("Your Full Name")
        email = st.text_input("Official Email (@idp.com)")
        if contestants:
            opts = [f"{c['number']} - {c['name']}" for c in contestants]
            sel = st.selectbox("Choose Contestant", opts)
            cont = int(sel.split(" - ")[0])
            # show image if available
            sel_idx = next((i for i,c in enumerate(contestants) if c['number']==cont), None)
            if sel_idx is not None and contestants[sel_idx].get('image') and os.path.exists(contestants[sel_idx]['image']):
                st.image(contestants[sel_idx]['image'], width=240)
        else:
            cont = st.number_input("Contestant Number", 1, 30)
        submitted = st.form_submit_button("Submit Vote")
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get("submitted", False):
        st.warning("You have already voted.")
        st.stop()

    if submitted:

        if not email or not email.lower().endswith("@idp.com"):
            st.error("Please use official @idp.com email")

        elif name.strip() == "":
            st.error("Name required")

        else:
            # check existing vote and show info if found
            c.execute("SELECT contestant, time FROM votes WHERE email=?", (email.lower(),))
            prev = c.fetchone()
            if prev:
                prev_cont, prev_time = prev[0], prev[1]
                try:
                    st.info(f"Previous vote found: Contestant {int(prev_cont)} at {format_iso_to_display(prev_time)} - it will be replaced.")
                except Exception:
                    st.info("Previous vote found - it will be replaced.")
            
            add_vote(email.lower(), name, int(cont))
            st.session_state.submitted = True
            st.success(f"Thanks {name}! Your vote has been recorded.")
            st.balloons()
            st.stop()

# ================= ADMIN =================
if menu=="Admin Panel":

    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = False
    
    if not st.session_state.admin_logged_in:
        pwd = st.text_input("Admin Password",type="password")
        if pwd == ADMIN_PWD and pwd != "":
            st.session_state.admin_logged_in = True
            st.success("Login successful!")
            st.rerun()
        elif pwd != "" and pwd != ADMIN_PWD:
            st.error("Wrong password")

    if st.session_state.admin_logged_in:

        r = results()
        av = all_votes()

        # -------- WINNER --------
        if not r.empty:
            top = r.iloc[0]
            st.markdown(f"""
            <div class='winner-card'>
            <h2>🏆 CURRENT WINNER</h2>
            <h1>Contestant #{int(top['contestant'])}</h1>
            <h3>{top['Votes']} Votes</h3>
            </div>
            """, unsafe_allow_html=True)


        # -------- GLOW BARS --------
        st.subheader("🔥 Live Leaderboard")
        if not r.empty:
            maxv = r["Votes"].max()
            for row in r.itertuples():
                pct = int((row.Votes / maxv) * 100) if maxv > 0 else 0
                st.markdown(f"""
                <div>Contestant {int(row.contestant)} — {row.Votes} votes</div>
                <div class='bar-wrap'>
                    <div class='bar' style='width:{pct}%;'></div>
                </div>
                """, unsafe_allow_html=True)

        # format times for display
        if not av.empty and 'time' in av.columns:
            av['time'] = av['time'].fillna('').astype(str).apply(format_iso_to_display)
        st.markdown("<div class='card'>",unsafe_allow_html=True)
        st.subheader("👥 Individual Votes")
        st.dataframe(av,use_container_width=True)
        st.markdown("</div>",unsafe_allow_html=True)

        # --- Contestant management ---
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("🎭 Contestants")
        conts = load_contestants()
        if conts:
            st.table(pd.DataFrame(conts))
            # export
            dfc = pd.DataFrame(conts)
            csvc = dfc.to_csv(index=False).encode('utf-8')
            jsonc = dfc.to_json(orient='records').encode('utf-8')
            st.download_button("Export Contestants CSV", csvc, "contestants.csv", "text/csv")
            st.download_button("Export Contestants JSON", jsonc, "contestants.json", "application/json")
        else:
            st.info("No contestants configured yet.")

        up = st.file_uploader("Upload contestants CSV (columns: number,name,image)", type=['csv'])
        if up is not None:
            try:
                dfu = pd.read_csv(up)
                import_contestants_from_df(dfu)
                st.success("Contestants imported")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to import: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

        # --- Voting window controls ---
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("⏱ Voting Window")
        # show current settings
        c.execute("SELECT voting_open, start_time, end_time FROM settings WHERE id=1")
        srow = c.fetchone()
        if srow:
            cur_flag, cur_start, cur_end = srow
            st.write(f"Voting Enabled: {bool(cur_flag)}")
            if cur_start:
                st.write(f"Start: {format_iso_to_display(cur_start)}")
            else:
                st.write(f"Start: Not set")
            if cur_end:
                st.write(f"End: {format_iso_to_display(cur_end)}")
            else:
                st.write(f"End: Not set")
        
        # DEBUG: Show voting status
        voting_status = is_voting_open()
        if voting_status:
            st.success(f"✅ **Voting is OPEN** - Current time allows voting")
        else:
            st.error(f"❌ **Voting is CLOSED** - Current time does NOT allow voting")

        st.write("**Set Voting Window**")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("📅 **Start**")
            start_date = st.date_input("Start Date", value=None, key="start_date", format="DD/MM/YYYY")
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                start_h = st.number_input("Hour (1-12)", min_value=1, max_value=12, value=10, key="start_h")
            with c2:
                start_m = st.number_input("Min", min_value=0, max_value=59, value=0, key="start_m")
            with c3:
                start_ampm = st.selectbox("AM/PM", ["A.M", "P.M"], key="start_ampm")
        
        with col2:
            st.write("📅 **End**")
            end_date = st.date_input("End Date", value=None, key="end_date", format="DD/MM/YYYY")
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                end_h = st.number_input("Hour (1-12)", min_value=1, max_value=12, value=6, key="end_h")
            with c2:
                end_m = st.number_input("Min", min_value=0, max_value=59, value=0, key="end_m")
            with c3:
                end_ampm = st.selectbox("AM/PM", ["A.M", "P.M"], key="end_ampm")
        
        if st.button("Set Voting Window", use_container_width=True):
            try:
                start_iso = None
                end_iso = None
                kolkata_tz = pytz.timezone('Asia/Kolkata')
                
                if start_date:
                    # Convert 12-hour to 24-hour format
                    hour_24 = int(start_h) % 12
                    if start_ampm == "P.M":
                        hour_24 += 12
                    start_dt = datetime.combine(start_date, datetime.min.time().replace(hour=hour_24, minute=int(start_m)))
                    start_dt = kolkata_tz.localize(start_dt)
                    start_iso = start_dt.isoformat()
                
                if end_date:
                    # Convert 12-hour to 24-hour format
                    hour_24 = int(end_h) % 12
                    if end_ampm == "P.M":
                        hour_24 += 12
                    end_dt = datetime.combine(end_date, datetime.min.time().replace(hour=hour_24, minute=int(end_m)))
                    end_dt = kolkata_tz.localize(end_dt)
                    end_iso = end_dt.isoformat()
                
                c.execute("UPDATE settings SET start_time=?, end_time=? WHERE id=1", (start_iso, end_iso))
                conn.commit()
                st.success("Voting window updated (UTC+05:30 Asia/Kolkata)")
            except Exception as e:
                st.error(f"Error setting voting window: {e}")
        
        if st.button("🔄 Reset Voting Window", use_container_width=True):
            c.execute("UPDATE settings SET start_time=NULL, end_time=NULL WHERE id=1")
            conn.commit()
            st.success("Voting window reset - timing restrictions cleared")
        
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        
        # Download CSV
        if not av.empty:
            csv = av.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV",csv,"IDP_VOTES.csv","text/csv", use_container_width=True)

        # Close/Open Voting
        col1, col2 = st.columns(2)
        with col1:
            if st.button("❌ Close Voting", use_container_width=True): 
                set_voting(0)
                st.success("Voting closed!")
        with col2:
            if st.button("✅ Open Voting", use_container_width=True): 
                # When opening voting, clear any time restrictions
                c.execute("UPDATE settings SET voting_open=1, start_time=NULL, end_time=NULL WHERE id=1")
                conn.commit()
                st.success("Voting opened! (All time restrictions cleared)")

        # Reset Votes / Refresh Leaderboard
        col3, col4 = st.columns(2)
        with col3:
            if 'confirm_reset' not in st.session_state:
                st.session_state['confirm_reset'] = False
            if st.session_state.get('confirm_reset'):
                if st.button("⚠️ Confirm Reset Votes", use_container_width=True):
                    reset_votes()
                    st.session_state['confirm_reset'] = False
                    st.success("All votes have been reset.")
            else:
                if st.button("🔄 Reset Votes", use_container_width=True):
                    st.session_state['confirm_reset'] = True
        with col4:
            if st.button("📊 Refresh Leaderboard", use_container_width=True):
                st.rerun()
        
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.admin_logged_in = False
            st.rerun()

# ---------------- CREDIT ----------------
st.markdown("<div class='credit'>Built by <span>Kartik Singh</span></div>",unsafe_allow_html=True)
