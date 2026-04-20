import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import calendar
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import io
from supabase import create_client, Client

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background:#fff !important; border-right:1px solid #f0f0f0; }
[data-testid="stSidebarUserContent"] { padding: 0 8px !important; }
[data-testid="stSidebarUserContent"] > div:first-child { margin-top: 0 !important; padding-top: 0 !important; }
section[data-testid="stSidebar"] > div { padding-top: 0.5rem !important; }

.profile-card {
    background: linear-gradient(135deg, #e94560 0%, #c73652 100%);
    border-radius: 16px; padding: 20px 16px;
    margin: 0 0 8px; text-align: center; border: none;
}
.profile-avatar { font-size: 44px; margin-bottom: 8px; display: block; }
.profile-name { font-size: 16px; font-weight: 700; color: #fff; margin: 0; }
.profile-sub  { font-size: 12px; color: rgba(255,255,255,0.75); margin: 3px 0 12px; }
.profile-stats { display: flex; gap: 6px; }
.pstat {
    flex:1; background: rgba(255,255,255,0.18);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 10px; padding: 6px 4px;
    text-align: center; font-size: 11px;
    color: rgba(255,255,255,0.85);
}
.pstat b { display:block; font-size:13px; font-weight:700; color:#fff; }

[data-testid="stSidebar"] .stButton > button {
    background: #fff !important; border: 1.5px solid #e94560 !important;
    color: #e94560 !important; font-weight: 600 !important;
    border-radius: 12px !important; width: 100% !important;
    padding: 12px !important; font-size: 14px !important;
}
[data-testid="stSidebar"] .stButton > button:hover { background: #fff5f6 !important; }

[data-testid="stMetric"] {
    background:#fff; border:1px solid #f0f0f0;
    border-radius:12px; padding:14px 18px !important;
}
[data-testid="stMetricValue"] { font-size:1.4rem !important; font-weight:700 !important; }
[data-testid="stMetricLabel"] { font-size:12px !important; color:#888 !important; }

div[data-testid="column"] .stButton button {
    height:72px !important; border-radius:12px !important;
    font-size:12px !important; font-weight:600 !important;
    border:1.5px solid #e8e8e8 !important;
    background:#fff !important; color:#333 !important;
    white-space:pre-line !important; transition:all 0.15s !important;
}
div[data-testid="column"] .stButton button:hover {
    border-color:#e94560 !important; background:#fff5f6 !important;
    transform:translateY(-1px);
}
.stProgress > div > div { background-color:#e94560 !important; border-radius:10px; }
.block-container { padding-top:1.2rem; }
</style>
""", unsafe_allow_html=True)

# ── Config ────────────────────────────────────────────────────────────────────
USERS = {
    "mayur": {"password": "mayur123", "display": "Mayur", "avatar": "👨‍💻", "currency": "₹", "role": "Admin"},
    "mahi":  {"password": "mahi123",  "display": "Mahi",  "avatar": "👩‍💼", "currency": "₹", "role": "Member"},
    "admin": {"password": "admin123", "display": "Admin", "avatar": "⚙️",   "currency": "₹", "role": "Super Admin"},
}

CATEGORIES  = ["Food","Travel","Medicine","Home-Worker","Shopping","Utilities","Maintanance","Entertainment","Other"]
CAT_ICONS   = {"Food":"🍔","Travel":"✈️","Medicine":"💊","Home-Worker":"👷","Shopping":"🛒",
               "Utilities":"💡","Maintanance":"🔧","Entertainment":"🎬","Other":"📦"}
CAT_COLORS  = {"Food":"#378ADD","Travel":"#1D9E75","Medicine":"#E24B4A","Home-Worker":"#BA7517",
               "Shopping":"#D4537E","Utilities":"#534AB7","Maintanance":"#D85A30",
               "Entertainment":"#639922","Other":"#888780"}
INCOME_SOURCES = ["Salary","Freelance","Rent Income","Business","Investment","Gift","Other"]
INCOME_ICONS   = {"Salary":"💼","Freelance":"💻","Rent Income":"🏠","Business":"🏢",
                  "Investment":"📈","Gift":"🎁","Other":"💰"}

# ── Session defaults ──────────────────────────────────────────────────────────
for k, v in [('logged', False), ('username', None), ('page', 'dashboard'),
             ('prefill_cat', None), ('prefill_src', None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Login ─────────────────────────────────────────────────────────────────────
if not st.session_state.logged:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("""
        <div style='text-align:center;padding:32px 0 20px'>
          <div style='font-size:52px'>💰</div>
          <h2 style='margin:8px 0 4px;color:#1a1a2e'>Expense Tracker</h2>
          <p style='color:#888;font-size:14px;margin:0'>Smart personal finance</p>
        </div>
        """, unsafe_allow_html=True)
        username = st.text_input("Username", placeholder="e.g. mayur").strip().lower()
        password = st.text_input("Password", type='password')
        if st.button("Sign In →", use_container_width=True, type="primary"):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged   = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid username or password")
    st.stop()

cu   = st.session_state.username
info = USERS[cu]
SYM  = info["currency"]

# ── Supabase connection ───────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# ── Database functions ────────────────────────────────────────────────────────
def load_df():
    res = supabase.table("expenses")\
        .select("*").eq("username", cu)\
        .order("date", desc=True).execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame(
        columns=["id","username","date","category","amount","note","recurring"])
    if not df.empty:
        df['date']   = pd.to_datetime(df['date'], errors='coerce')
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    return df

def load_income_df():
    res = supabase.table("income")\
        .select("*").eq("username", cu)\
        .order("date", desc=True).execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame(
        columns=["id","username","date","source","amount","note","recurring"])
    if not df.empty:
        df['date']   = pd.to_datetime(df['date'], errors='coerce')
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    return df

def save_expense(d, cat, amt, note, rec=0):
    supabase.table("expenses").insert({
        "username": cu, "date": str(d), "category": cat,
        "amount": float(amt), "note": note, "recurring": rec
    }).execute()

def save_income(d, src, amt, note, rec=0):
    supabase.table("income").insert({
        "username": cu, "date": str(d), "source": src,
        "amount": float(amt), "note": note, "recurring": rec
    }).execute()

def update_expense(eid, d, cat, amt, note):
    supabase.table("expenses").update({
        "date": str(d), "category": cat,
        "amount": float(amt), "note": note
    }).eq("id", eid).eq("username", cu).execute()

def delete_row(table, eid):
    supabase.table(table).delete()\
        .eq("id", eid).eq("username", cu).execute()

def load_budgets():
    res = supabase.table("budgets")\
        .select("category, monthly_limit")\
        .eq("username", cu).execute()
    return {r['category']: r['monthly_limit'] for r in res.data}

def save_budget(cat, lim):
    existing = supabase.table("budgets")\
        .select("id").eq("username", cu).eq("category", cat).execute()
    if existing.data:
        supabase.table("budgets").update({
            "monthly_limit": float(lim)
        }).eq("username", cu).eq("category", cat).execute()
    else:
        supabase.table("budgets").insert({
            "username": cu, "category": cat, "monthly_limit": float(lim)
        }).execute()

def insert_from_df(udf):
    rows = []
    for _, row in udf.iterrows():
        rows.append({
            "username": cu,
            "date":     str(row.get('Date', '')),
            "category": str(row.get('Category', '')),
            "amount":   float(row.get('Amount', 0)),
            "note":     str(row.get('Note', ''))
        })
    if rows:
        supabase.table("expenses").insert(rows).execute()

def apply_recurring():
    today = date.today()
    m = today.strftime("%Y-%m")

    # Recurring expenses
    rec_exp = supabase.table("expenses")\
        .select("category, amount, note")\
        .eq("username", cu).eq("recurring", 1).execute()
    for row in rec_exp.data:
        exists = supabase.table("expenses")\
            .select("id").eq("username", cu)\
            .eq("category", row['category'])\
            .eq("amount", row['amount'])\
            .eq("recurring", 1)\
            .like("date", f"{m}%").execute()
        if not exists.data:
            supabase.table("expenses").insert({
                "username": cu, "date": str(today),
                "category": row['category'], "amount": row['amount'],
                "note": row['note'], "recurring": 1
            }).execute()

    # Recurring income
    rec_inc = supabase.table("income")\
        .select("source, amount, note")\
        .eq("username", cu).eq("recurring", 1).execute()
    for row in rec_inc.data:
        exists = supabase.table("income")\
            .select("id").eq("username", cu)\
            .eq("source", row['source'])\
            .eq("amount", row['amount'])\
            .eq("recurring", 1)\
            .like("date", f"{m}%").execute()
        if not exists.data:
            supabase.table("income").insert({
                "username": cu, "date": str(today),
                "source": row['source'], "amount": row['amount'],
                "note": row['note'], "recurring": 1
            }).execute()

# ── PDF Generator ─────────────────────────────────────────────────────────────
def generate_expense_pdf(data_df, username, currency_sym):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []
    title_style = ParagraphStyle('title', fontSize=18, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#e94560'), spaceAfter=4)
    sub_style   = ParagraphStyle('sub', fontSize=10, fontName='Helvetica',
                                  textColor=colors.HexColor('#888888'), spaceAfter=12)
    elements.append(Paragraph("Expense Report", title_style))
    elements.append(Paragraph(
        f"User: @{username}  |  Generated: {date.today().strftime('%d %b %Y')}  |  "
        f"Total Records: {len(data_df)}  |  Total: {currency_sym}{data_df['amount'].sum():,.2f}",
        sub_style
    ))
    elements.append(Spacer(1, 0.3*cm))

    table_data = [['#', 'Date', 'Category', 'Amount', 'Note', 'Recurring']]
    for i, (_, row) in enumerate(data_df.iterrows(), 1):
        table_data.append([
            str(i),
            pd.to_datetime(row['date']).strftime('%d %b %Y') if pd.notna(row['date']) else '',
            str(row.get('category', '')),
            f"{currency_sym}{float(row.get('amount', 0)):,.2f}",
            str(row.get('note', ''))[:40] + ('...' if len(str(row.get('note',''))) > 40 else ''),
            'Yes' if row.get('recurring', 0) else 'No'
        ])
    table_data.append(['', '', 'TOTAL', f"{currency_sym}{data_df['amount'].sum():,.2f}", '', ''])

    col_widths = [1*cm, 2.8*cm, 3.5*cm, 2.8*cm, 5.5*cm, 2*cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#e94560')),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  9),
        ('ALIGN',         (0, 0), (-1, 0),  'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  8),
        ('TOPPADDING',    (0, 0), (-1, 0),  8),
        ('ROWBACKGROUNDS',(0, 1), (-1, -2), [colors.white, colors.HexColor('#fff5f6')]),
        ('FONTNAME',      (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -2), 8),
        ('ALIGN',         (0, 1), (-1, -1), 'CENTER'),
        ('ALIGN',         (4, 1), (4, -1),  'LEFT'),
        ('TOPPADDING',    (0, 1), (-1, -2), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -2), 6),
        ('TEXTCOLOR',     (0, 1), (-1, -2), colors.HexColor('#333333')),
        ('BACKGROUND',    (0, -1), (-1, -1), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR',     (0, -1), (-1, -1), colors.white),
        ('FONTNAME',      (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, -1), (-1, -1), 9),
        ('TOPPADDING',    (0, -1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#eeeeee')),
        ('LINEBELOW',     (0, 0), (-1, 0),  1.5, colors.HexColor('#c73652')),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ── Apply recurring & load data ───────────────────────────────────────────────
apply_recurring()
df        = load_df()
income_df = load_income_df()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
from streamlit_option_menu import option_menu

with st.sidebar:
    total_exp = df['amount'].sum() if not df.empty else 0
    total_inc = income_df['amount'].sum() if not income_df.empty else 0
    balance   = total_inc - total_exp

    st.markdown(f"""
    <div class="profile-card">
      <span class="profile-avatar">{info['avatar']}</span>
      <p class="profile-name">{info['display']}</p>
      <p class="profile-sub">@{cu} · {info['role']}</p>
      <div class="profile-stats">
        <div class="pstat"><b>{len(df)}</b>entries</div>
        <div class="pstat"><b>{SYM}{total_exp/1000:.1f}k</b>spent</div>
        <div class="pstat"><b>{'🟢' if balance>=0 else '🔴'}</b>balance</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    PAGE_KEYS = ["dashboard", "add", "income", "recurring", "import", "profile"]
    cur_index = PAGE_KEYS.index(st.session_state.page) if st.session_state.page in PAGE_KEYS else 0

    selected = option_menu(
        menu_title=None,
        options=["Dashboard", "Add Expense", "Income & Credits", "Recurring", "Import CSV", "Profile"],
        icons=["bar-chart-fill", "plus-lg", "cash-coin", "arrow-repeat", "folder2-open", "person-fill"],
        default_index=cur_index,
        styles={
            "container":        {"padding": "0", "background-color": "#ffffff", "margin": "0"},
            "icon":             {"color": "#888", "font-size": "16px"},
            "nav-link":         {"font-size": "14px", "font-weight": "500", "color": "#333",
                                 "padding": "12px 16px", "border-radius": "10px",
                                 "margin": "2px 0", "background-color": "transparent"},
            "nav-link-selected":{"background-color": "#e94560", "color": "#ffffff",
                                 "font-weight": "700", "border-radius": "10px"},
        }
    )

    label_to_key = {
        "Dashboard": "dashboard", "Add Expense": "add",
        "Income & Credits": "income", "Recurring": "recurring",
        "Import CSV": "import", "Profile": "profile",
    }
    if label_to_key[selected] != st.session_state.page:
        st.session_state.page = label_to_key[selected]
        st.rerun()

    st.markdown("---")
    if st.button("🚪  Logout", key="logout_btn", use_container_width=True):
        st.session_state.logged   = False
        st.session_state.username = None
        st.rerun()

page = st.session_state.page

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
if page == "dashboard":
    today = date.today()
    st.title("📊 Dashboard")
    st.caption(f"Welcome back, {info['display']}!")

    period = st.selectbox("Period", ["This Month","Last Month","Last 3 Months","This Year","All Time"])
    if period == "This Month":
        start, end = today.replace(day=1), today
    elif period == "Last Month":
        first = today.replace(day=1); end = first - timedelta(days=1); start = end.replace(day=1)
    elif period == "Last 3 Months":
        start, end = (today - timedelta(days=90)), today
    elif period == "This Year":
        start, end = today.replace(month=1, day=1), today
    else:
        start = df['date'].min().date() if not df.empty else today; end = today

    filt = df[(df['date'].dt.date >= start) & (df['date'].dt.date <= end)] if not df.empty else pd.DataFrame()
    finc = income_df[(income_df['date'].dt.date >= start) & (income_df['date'].dt.date <= end)] if not income_df.empty else pd.DataFrame()

    total_s = filt['amount'].sum() if not filt.empty else 0
    total_i = finc['amount'].sum() if not finc.empty else 0
    net     = total_i - total_s

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("💸 Total Spent",  f"{SYM}{total_s:,.0f}")
    k2.metric("💵 Total Income", f"{SYM}{total_i:,.0f}")
    k3.metric("🏦 Net Balance",  f"{SYM}{net:,.0f}")
    k4.metric("🧾 Transactions", len(filt) if not filt.empty else 0)
    if not filt.empty:
        top = filt.groupby('category')['amount'].sum().idxmax()
        k5.metric("🏆 Top Category", f"{CAT_ICONS.get(top,'')} {top}")
    else:
        k5.metric("🏆 Top Category", "—")

    st.divider()

    if not filt.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Spending by category")
            cat_df = filt.groupby('category')['amount'].sum().reset_index()
            cat_df['label'] = cat_df['category'].apply(lambda x: f"{CAT_ICONS.get(x,'')} {x}")
            fig = px.pie(cat_df, values='amount', names='label', hole=0.45,
                         color='category', color_discrete_map=CAT_COLORS)
            fig.update_traces(textposition='outside', textinfo='percent+label')
            fig.update_layout(showlegend=False, margin=dict(t=10,b=10,l=0,r=0), height=280)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("Income vs Expenses")
            de = filt.groupby(filt['date'].dt.date)['amount'].sum().reset_index()
            di = finc.groupby(finc['date'].dt.date)['amount'].sum().reset_index() if not finc.empty else pd.DataFrame(columns=['date','amount'])
            de.columns = ['date','Expenses']; di.columns = ['date','Income']
            merged = pd.merge(de, di, on='date', how='outer').fillna(0).sort_values('date')
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=merged['date'], y=merged.get('Income',0), name='Income', marker_color='#1D9E75'))
            fig2.add_trace(go.Bar(x=merged['date'], y=merged['Expenses'], name='Expenses', marker_color='#e94560'))
            fig2.update_layout(barmode='group', margin=dict(t=10,b=10,l=0,r=0), height=280,
                               legend=dict(orientation='h', y=1.1))
            st.plotly_chart(fig2, use_container_width=True)

        c3, c4 = st.columns(2)
        with c3:
            st.subheader("Category bar")
            bar_df = filt.groupby('category')['amount'].sum().reset_index().sort_values('amount')
            bar_df['label'] = bar_df['category'].apply(lambda x: f"{CAT_ICONS.get(x,'')} {x}")
            fig3 = px.bar(bar_df, x='amount', y='label', orientation='h',
                          color='category', color_discrete_map=CAT_COLORS, text_auto='.0f',
                          labels={'amount': f'Amount ({SYM})', 'label': ''})
            fig3.update_layout(showlegend=False, margin=dict(t=10,b=10,l=0,r=0), height=280)
            st.plotly_chart(fig3, use_container_width=True)
        with c4:
            st.subheader("Daily trend")
            daily = filt.groupby(filt['date'].dt.date)['amount'].sum().reset_index()
            daily.columns = ['date','amount']
            fig4 = px.area(daily, x='date', y='amount',
                           labels={'amount': f'Amount ({SYM})', 'date': ''},
                           color_discrete_sequence=['#e94560'])
            fig4.update_layout(margin=dict(t=10,b=10,l=0,r=0), height=280)
            st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("No expense data for this period.")

    st.divider()
    st.subheader("📅 Spending heatmap (this month)")
    today_dt     = pd.Timestamp(today)
    month_start  = today_dt.replace(day=1)
    month_filt   = df[(df['date'] >= month_start) & (df['date'] <= today_dt)]
    daily_totals = month_filt.groupby(month_filt['date'].dt.day)['amount'].sum()
    _, num_days  = calendar.monthrange(today.year, today.month)
    first_weekday = calendar.monthrange(today.year, today.month)[0]

    cols_cal = st.columns(7)
    for i, h in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
        cols_cal[i].markdown(f"<p style='text-align:center;font-size:12px;color:gray'>{h}</p>", unsafe_allow_html=True)

    max_amt   = daily_totals.max() if not daily_totals.empty else 1
    week_cols = st.columns(7)
    all_cells = [""] * first_weekday + list(range(1, num_days+1))
    for i, d in enumerate(all_cells):
        col_idx = i % 7
        if i % 7 == 0 and i > 0:
            week_cols = st.columns(7)
        if d == "":
            week_cols[col_idx].markdown(" ")
        else:
            amt     = daily_totals.get(d, 0)
            amt_str = f"₹{amt:.0f}" if amt > 0 else ""
            week_cols[col_idx].markdown(
                f"<div style='text-align:center;background:{'#EAF3DE' if amt>0 else '#f5f5f5'};"
                f"border-radius:6px;padding:4px 2px;font-size:12px;margin:1px'>"
                f"<b>{d}</b><br><span style='color:#27500A;font-size:10px'>{amt_str}</span></div>",
                unsafe_allow_html=True
            )

    st.divider()
    tab1, tab2 = st.tabs(["📋 All Expenses", "🎯 Budgets"])

    with tab1:
        if df.empty:
            st.info("No expenses yet. Go to **Add Expense** to get started!")
        else:
            f1, f2, f3 = st.columns([2, 1, 1])
            search = f1.text_input("🔍 Search by note", placeholder="e.g. dinner, rent...")
            cat_f  = f2.selectbox("Category", ["All"] + CATEGORIES, key="cat_filter")
            sort_f = f3.selectbox("Sort", ["Date (newest)","Date (oldest)","Amount (high)","Amount (low)"])

            d1, d2 = st.columns(2)
            dr1 = d1.date_input("From", value=df['date'].min().date(), key="dr1")
            dr2 = d2.date_input("To",   value=df['date'].max().date(), key="dr2")

            filtered = df.copy()
            if search:
                filtered = filtered[filtered['note'].str.contains(search, case=False, na=False)]
            if cat_f != "All":
                filtered = filtered[filtered['category'] == cat_f]
            filtered = filtered[(filtered['date'].dt.date >= dr1) & (filtered['date'].dt.date <= dr2)]
            sc, sa = {"Date (newest)":('date',False),"Date (oldest)":('date',True),
                      "Amount (high)":('amount',False),"Amount (low)":('amount',True)}[sort_f]
            filtered = filtered.sort_values(sc, ascending=sa)

            st.caption(f"**{len(filtered)}** records · Total: **{SYM}{filtered['amount'].sum():,.0f}**")
            st.dataframe(
                filtered.assign(
                    date=filtered['date'].dt.strftime('%d %b %Y'),
                    category=filtered['category'].apply(lambda x: f"{CAT_ICONS.get(x,'')} {x}"),
                    amount=filtered['amount'].apply(lambda x: f"{SYM}{x:,.2f}"),
                    recurring=filtered['recurring'].apply(lambda x: "🔁" if x else "")
                )[['id','date','category','amount','note','recurring']],
                use_container_width=True, hide_index=True,
                column_config={'id':'ID','date':'Date','category':'Category',
                               'amount':'Amount','note':'Note','recurring':''}
            )

            with st.expander("✏️ Edit or delete an expense"):
                edit_id = st.number_input("Enter Expense ID", min_value=1, step=1)
                row = filtered[filtered['id'] == edit_id]
                if not row.empty:
                    r = row.iloc[0]
                    ec1, ec2 = st.columns(2)
                    new_cat  = ec1.selectbox("Category", CATEGORIES,
                                             index=CATEGORIES.index(r['category']) if r['category'] in CATEGORIES else 0,
                                             key="edit_cat")
                    new_amt  = ec2.number_input("Amount", value=float(r['amount']), key="edit_amt")
                    new_date = ec1.date_input("Date", value=r['date'].date(), key="edit_date")
                    new_note = ec2.text_input("Note", value=str(r['note']), key="edit_note")
                    bc1, bc2 = st.columns(2)
                    if bc1.button("💾 Update", use_container_width=True, type="primary"):
                        update_expense(int(edit_id), new_date, new_cat, new_amt, new_note)
                        st.success("Updated!"); st.rerun()
                    if bc2.button("🗑️ Delete", use_container_width=True):
                        delete_row("expenses", int(edit_id))
                        st.success("Deleted!"); st.rerun()
                else:
                    st.caption("Enter a valid ID from the table above.")

            ex1, ex2 = st.columns(2)
            with ex1:
                st.download_button(
                    "⬇️ Export as CSV",
                    data=filtered.assign(date=filtered['date'].dt.strftime('%Y-%m-%d')
                        )[['date','category','amount','note']].to_csv(index=False).encode(),
                    file_name=f"{cu}_expenses.csv", mime="text/csv",
                    use_container_width=True
                )
            with ex2:
                if not filtered.empty:
                    pdf_buf = generate_expense_pdf(filtered, cu, SYM)
                    st.download_button(
                        "📄 Export as PDF",
                        data=pdf_buf,
                        file_name=f"{cu}_expenses_{date.today().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:
                    st.button("📄 Export as PDF", disabled=True, use_container_width=True)

    with tab2:
        budgets    = load_budgets()
        this_m_exp = df[df['date'].dt.to_period('M') == pd.Period(today,'M')] if not df.empty else pd.DataFrame()
        cat_spent  = this_m_exp.groupby('category')['amount'].sum() if not this_m_exp.empty else pd.Series(dtype=float)

        if budgets:
            st.subheader("This month's budget status")
            for cat, limit in budgets.items():
                spent  = cat_spent.get(cat, 0)
                pct    = min((spent / limit * 100) if limit > 0 else 0, 100)
                status = "🔴 Over budget!" if pct >= 100 else "🟠 Almost there" if pct >= 80 else "🟢 On track"
                ca, cb = st.columns([3, 1])
                with ca:
                    st.markdown(f"**{CAT_ICONS.get(cat,'')} {cat}** — {status}")
                    st.progress(pct / 100)
                    st.caption(f"{SYM}{spent:,.0f} of {SYM}{limit:,.0f} · {pct:.0f}% used")
                with cb:
                    rem = limit - spent
                    st.metric("Remaining" if rem >= 0 else "Over by", f"{SYM}{abs(rem):,.0f}")
            st.divider()

        st.subheader("Set / update a budget limit")
        with st.form("budget_form"):
            bc1, bc2 = st.columns(2)
            b_cat   = bc1.selectbox("Category", CATEGORIES)
            b_limit = bc2.number_input(f"Monthly limit ({SYM})", min_value=0.0, step=500.0)
            if st.form_submit_button("💾 Save Budget", use_container_width=True, type="primary"):
                save_budget(b_cat, b_limit)
                st.success(f"✅ {b_cat} budget set to {SYM}{b_limit:,.0f}/month")
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# ADD EXPENSE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "add":
    st.title("➕ Add Expense")
    st.subheader("Quick select")
    cols = st.columns(5)
    row2 = st.columns(4)
    all_cols = cols + row2
    for i, cat in enumerate(CATEGORIES):
        if all_cols[i].button(f"{CAT_ICONS[cat]}\n{cat}", key=f"q_{cat}", use_container_width=True, help=cat):
            st.session_state.prefill_cat = cat
            st.rerun()

    st.divider()
    cat_idx = CATEGORIES.index(st.session_state.prefill_cat) if st.session_state.prefill_cat in CATEGORIES else 0

    with st.form("expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        exp_cat  = c1.selectbox("Category", CATEGORIES, index=cat_idx)
        exp_amt  = c2.number_input(f"Amount ({SYM})", min_value=0.01, step=1.0, format="%.2f")
        exp_date = c1.date_input("Date", value=date.today())
        exp_note = c2.text_input("Description", placeholder="e.g. Lunch, Netflix bill")
        exp_rec  = st.checkbox("🔁 Mark as recurring (auto-adds every month)")
        if st.form_submit_button("💾 Save Expense", use_container_width=True, type="primary"):
            save_expense(exp_date, exp_cat, exp_amt, exp_note, int(exp_rec))
            st.success(f"✅ {CAT_ICONS.get(exp_cat,'')} {SYM}{exp_amt:,.2f} added to **{exp_cat}**!")
            st.session_state.prefill_cat = None
            st.balloons()

# ═══════════════════════════════════════════════════════════════════════════════
# INCOME & CREDITS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "income":
    st.title("💵 Income & Credits")
    today = date.today()

    this_m_inc = income_df[income_df['date'].dt.to_period('M') == pd.Period(today,'M')] if not income_df.empty else pd.DataFrame()
    this_m_exp = df[df['date'].dt.to_period('M') == pd.Period(today,'M')] if not df.empty else pd.DataFrame()
    ti    = this_m_inc['amount'].sum() if not this_m_inc.empty else 0
    te    = this_m_exp['amount'].sum() if not this_m_exp.empty else 0
    net_m = ti - te

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("This Month Income",   f"{SYM}{ti:,.0f}")
    k2.metric("This Month Expenses", f"{SYM}{te:,.0f}")
    k3.metric("Net This Month",      f"{SYM}{net_m:,.0f}", f"{'▲' if net_m>=0 else '▼'}")
    k4.metric("All-Time Income",     f"{SYM}{income_df['amount'].sum():,.0f}" if not income_df.empty else f"{SYM}0")

    st.divider()
    tab1, tab2 = st.tabs(["📊 Income Records", "➕ Add Income"])

    with tab1:
        if income_df.empty:
            st.info("No income records yet. Add your first entry in the Add Income tab.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("By source")
                src_df = income_df.groupby('source')['amount'].sum().reset_index()
                src_df['label'] = src_df['source'].apply(lambda x: f"{INCOME_ICONS.get(x,'💰')} {x}")
                fig = px.pie(src_df, values='amount', names='label', hole=0.5)
                fig.update_layout(showlegend=False, margin=dict(t=10,b=10,l=0,r=0), height=260)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.subheader("Monthly trend")
                income_df['month'] = income_df['date'].dt.to_period('M').astype(str)
                monthly = income_df.groupby('month')['amount'].sum().reset_index()
                fig2 = px.bar(monthly, x='month', y='amount',
                              color_discrete_sequence=['#1D9E75'],
                              labels={'amount': f'Income ({SYM})', 'month': ''})
                fig2.update_layout(margin=dict(t=10,b=10,l=0,r=0), height=260)
                st.plotly_chart(fig2, use_container_width=True)

            disp = income_df.copy()
            disp['date']      = disp['date'].dt.strftime('%d %b %Y')
            disp['source']    = disp['source'].apply(lambda x: f"{INCOME_ICONS.get(x,'💰')} {x}")
            disp['amount']    = disp['amount'].apply(lambda x: f"+ {SYM}{x:,.2f}")
            disp['recurring'] = disp['recurring'].apply(lambda x: "🔁" if x else "")
            st.dataframe(disp[['id','date','source','amount','note','recurring']],
                         use_container_width=True, hide_index=True)

            with st.expander("🗑️ Delete a record"):
                del_id = st.number_input("Income ID", min_value=1, step=1)
                if st.button("Delete", type="primary"):
                    delete_row("income", int(del_id)); st.success("Deleted!"); st.rerun()

            st.download_button("⬇️ Export income CSV",
                data=income_df.assign(date=income_df['date'].dt.strftime('%Y-%m-%d')
                    )[['date','source','amount','note']].to_csv(index=False).encode(),
                file_name=f"{cu}_income.csv", mime="text/csv")

    with tab2:
        st.subheader("Select source")
        src_cols = st.columns(len(INCOME_SOURCES))
        for i, src in enumerate(INCOME_SOURCES):
            if src_cols[i].button(f"{INCOME_ICONS[src]}\n{src}", key=f"is_{src}", use_container_width=True):
                st.session_state.prefill_src = src; st.rerun()
        src_idx = INCOME_SOURCES.index(st.session_state.prefill_src) if st.session_state.prefill_src in INCOME_SOURCES else 0
        with st.form("income_form", clear_on_submit=True):
            ic1, ic2 = st.columns(2)
            inc_src  = ic1.selectbox("Source", INCOME_SOURCES, index=src_idx)
            inc_amt  = ic2.number_input(f"Amount ({SYM})", min_value=0.01, step=100.0, format="%.2f")
            inc_date = ic1.date_input("Date", value=date.today())
            inc_note = ic2.text_input("Description", placeholder="e.g. April salary")
            inc_rec  = st.checkbox("🔁 Recurring monthly income")
            if st.form_submit_button("💾 Save Income", use_container_width=True, type="primary"):
                save_income(inc_date, inc_src, inc_amt, inc_note, int(inc_rec))
                st.success(f"✅ {SYM}{inc_amt:,.2f} from **{inc_src}** saved!")
                st.session_state.prefill_src = None; st.balloons()

# ═══════════════════════════════════════════════════════════════════════════════
# RECURRING
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "recurring":
    st.title("🔁 Recurring Expenses")
    st.info("These are automatically added every month.")

    rec_df = df[df['recurring']==1][['id','category','amount','note']].drop_duplicates(
        subset=['category','amount','note']) if not df.empty else pd.DataFrame()
    if not rec_df.empty:
        disp = rec_df.copy()
        disp['category'] = disp['category'].apply(lambda x: f"{CAT_ICONS.get(x,'')} {x}")
        disp['amount']   = disp['amount'].apply(lambda x: f"{SYM}{x:,.2f}/mo")
        st.dataframe(disp, use_container_width=True, hide_index=True)
        st.metric("Total monthly auto-expense", f"{SYM}{rec_df['amount'].sum():,.0f}")
    else:
        st.info("No recurring expenses yet.")

    st.divider()
    st.subheader("Add recurring expense")
    with st.form("rec_form", clear_on_submit=True):
        rc1, rc2 = st.columns(2)
        r_cat  = rc1.selectbox("Category", CATEGORIES)
        r_amt  = rc2.number_input(f"Monthly amount ({SYM})", min_value=1.0, step=100.0)
        r_note = st.text_input("Description", placeholder="e.g. Netflix, EMI, Gym")
        if st.form_submit_button("➕ Add Recurring", use_container_width=True, type="primary"):
            save_expense(date.today(), r_cat, r_amt, r_note, rec=1)
            st.success("✅ Added!"); st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT CSV
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "import":
    st.title("📂 Import CSV")
    st.info("**Required columns:** Date (YYYY-MM-DD), Category, Amount · Note is optional.")
    sample = pd.DataFrame({'Date':['2026-04-01','2026-04-05'],'Category':['Food','Travel'],
                           'Amount':[350,1200],'Note':['Lunch','Train ticket']})
    st.download_button("⬇️ Download sample CSV", sample.to_csv(index=False).encode(), "sample.csv", "text/csv")
    uploads = st.file_uploader("Upload CSV", type=['csv'], accept_multiple_files=True)
    if uploads:
        up_df = pd.concat([pd.read_csv(f) for f in uploads], ignore_index=True)
        st.subheader("Preview")
        st.dataframe(up_df.head(10), use_container_width=True)
        if st.button(f"✅ Import {len(up_df)} rows", type="primary"):
            insert_from_df(up_df); st.success(f"Imported {len(up_df)} expenses!"); st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "profile":
    st.title("👤 Profile")
    today = date.today()

    total_e = df['amount'].sum()        if not df.empty        else 0
    total_i = income_df['amount'].sum() if not income_df.empty else 0
    net_all = total_i - total_e
    avg_tx  = df['amount'].mean()       if not df.empty        else 0

    cp1, cp2 = st.columns([1, 2.2])
    with cp1:
        st.markdown(f"""
        <div style="background:#f8f9fa;border:1px solid #eee;border-radius:16px;
             padding:24px;text-align:center">
          <div style="font-size:56px">{info['avatar']}</div>
          <p style="font-size:18px;font-weight:700;color:#1a1a2e;margin:6px 0 2px">{info['display']}</p>
          <p style="font-size:13px;color:#888;margin:0">@{cu} · {info['role']}</p>
          <p style="font-size:12px;color:#aaa;margin:8px 0 0">
            Member since {df['date'].min().strftime('%b %Y') if not df.empty else 'N/A'}
          </p>
        </div>
        """, unsafe_allow_html=True)
    with cp2:
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Income",   f"{SYM}{total_i:,.0f}")
        m2.metric("Total Expenses", f"{SYM}{total_e:,.0f}")
        m3.metric("Net Savings",    f"{SYM}{net_all:,.0f}")
        m4, m5, m6 = st.columns(3)
        m4.metric("Transactions",    len(df))
        m5.metric("Avg Transaction", f"{SYM}{avg_tx:,.0f}")
        m6.metric("Income Sources",  len(income_df['source'].unique()) if not income_df.empty else 0)

    if not df.empty:
        st.divider()
        pp1, pp2 = st.columns(2)
        with pp1:
            st.subheader("All-time by category")
            ac = df.groupby('category')['amount'].sum().reset_index().sort_values('amount', ascending=False)
            ac['label'] = ac['category'].apply(lambda x: f"{CAT_ICONS.get(x,'')} {x}")
            fig = px.bar(ac, x='label', y='amount', color='category', color_discrete_map=CAT_COLORS,
                         labels={'amount': f'Total ({SYM})', 'label': ''})
            fig.update_layout(showlegend=False, margin=dict(t=10,b=10,l=0,r=0))
            st.plotly_chart(fig, use_container_width=True)
        with pp2:
            st.subheader("Monthly income vs expenses")
            df['month'] = df['date'].dt.to_period('M').astype(str)
            mo_e = df.groupby('month')['amount'].sum().reset_index()
            mo_e.columns = ['month','Expenses']
            if not income_df.empty:
                income_df['month'] = income_df['date'].dt.to_period('M').astype(str)
                mo_i = income_df.groupby('month')['amount'].sum().reset_index()
                mo_i.columns = ['month','Income']
                mo = pd.merge(mo_e, mo_i, on='month', how='outer').fillna(0).sort_values('month')
            else:
                mo = mo_e
            fig2 = px.line(mo, x='month', y=[c for c in ['Income','Expenses'] if c in mo.columns],
                           markers=True, color_discrete_map={'Income':'#1D9E75','Expenses':'#e94560'},
                           labels={'value': f'Amount ({SYM})', 'month': ''})
            fig2.update_layout(margin=dict(t=10,b=10,l=0,r=0))
            st.plotly_chart(fig2, use_container_width=True)
