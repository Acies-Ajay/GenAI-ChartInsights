import os, io, base64, re
from typing import List
import streamlit as st
from PIL import Image
from groq import Groq
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from string import Template  # <-- for safe CSS templating

load_dotenv()
st.set_page_config(page_title="Chart Insights (Groq + Streamlit)", page_icon="📊", layout="wide")

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
TEXT_MODEL   = "llama-3.3-70b-versatile"

if "history" not in st.session_state:
    st.session_state["history"] = []

def get_groq() -> Groq:
    api_key = os.getenv("GROQ_DEMO_API_KEY")
    if not api_key:
        st.error("GROQ_DEMO_API_KEY is missing. Put it in your environment or a .env file.")
        st.stop()
    return Groq(api_key=api_key)

client = get_groq()

# --- session state ---
for k, v in {
    'chart_data': [], 'show_qa': {}, 'qa_active': {}
}.items():
    if k not in st.session_state: st.session_state[k] = v

# ----------------------------
# Theme (Light/Dark) — CSS via Template (no f-string braces!)
# ----------------------------
def apply_theme(mode: str):
    if mode == "Dark":
        cfg = dict(
            bg="#0f172a", panel="#0b1224", text="#e6eaf2", subtext="#b6c0d1",
            accent="#60a5fa", border="#22324d", faint="rgba(255,255,255,0.04)",
            ring="0 0 0 3px rgba(96,165,250,0.25)",
            imgshadow="0 12px 32px rgba(0,0,0,0.45)",
            cardshadow="0 12px 28px rgba(2,6,23,0.35)",
            grad1="rgba(96,165,250,0.28)", grad2="rgba(124,58,237,0.22)"
        )
    else:
        cfg = dict(
            bg="#f7f9fc", panel="#ffffff", text="#0f172a", subtext="#475569",
            accent="#1f6feb", border="#e6ebf4", faint="rgba(31,111,235,0.06)",
            ring="0 0 0 3px rgba(31,111,235,0.18)",
            imgshadow="0 12px 32px rgba(31,111,235,0.08)",
            cardshadow="0 10px 24px rgba(31,111,235,0.08)",
            grad1="rgba(31,111,235,0.18)", grad2="rgba(168,85,247,0.12)"
        )

    css = Template("""
    <style>
    html, body, [data-testid="stAppViewContainer"] {
        background: $bg !important; color: $text !important;
    }
    .main .block-container { max-width: 1200px !important; padding-top: .75rem !important; }
    .stMarkdown, .stText, .stCaption, p, li, span, div { color: $text !important; }
    .stCaption, .st-emotion-cache-ue6h4q, .st-emotion-cache-1kyxreq { color: $subtext !important; }
    h1, h2, h3, h4, h5, h6 { color: $text !important; letter-spacing: -0.01em; }
    [data-testid="stSidebar"] { background: $panel !important; color: $text !important; border-right: 1px solid $border; }
    [data-testid="stHeader"] { background: transparent !important; }

    /* Keep underline only for h3 (not the title) */
    h3 { position: relative; padding-bottom: 6px; margin-top: .5rem; }
    h3::after {
        content: ""; position: absolute; left: 0; bottom: 0; width: 120px; height: 3px;
        background: linear-gradient(90deg, $accent, transparent); border-radius: 999px; opacity: .85;
    }

    /* File uploader */
    [data-testid="stFileUploader"] section {
        border: 1px dashed $border; background: $faint; border-radius: 12px;
    }

    /* Buttons + focus */
    .stButton button, [data-testid="stDownloadButton"] button {
        border-radius: 10px !important; border: 1px solid $border !important;
        transition: transform .06s ease, filter .12s ease, box-shadow .12s ease;
        background: $panel;
    }
    .stButton button:focus-visible, [data-testid="stDownloadButton"] button:focus-visible { box-shadow: $ring !important; outline: none !important; }
    .stButton button:hover, [data-testid="stDownloadButton"] button:hover { transform: translateY(-1px); filter: brightness(1.02); }

    /* Images */
    figure img, [data-testid="stImage"] img {
        border-radius: 12px !important; box-shadow: $imgshadow !important; transition: transform .12s ease;
    }
    figure img:hover, [data-testid="stImage"] img:hover { transform: translateY(-2px) scale(1.01); }

    /* Dividers */
    hr, [role="separator"] { border-color: $border !important; opacity: .6; }

    /* Animations + card */
    @keyframes fadeSlideUp { from { opacity:0; transform: translateY(6px);} to {opacity:1; transform: translateY(0);} }
    .card {
        background:$panel; border:1px solid $border; border-radius:14px; padding:16px 18px;
        box-shadow:$cardshadow; transition: box-shadow .15s ease, transform .08s ease, border .12s ease;
        animation: fadeSlideUp .25s ease both; position:relative;
    }
    .card::before {
        content:""; position:absolute; inset:-1px; border-radius:16px; pointer-events:none;
        background: linear-gradient(135deg, $grad1, $grad2); opacity:.45;
        -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
        -webkit-mask-composite: xor; mask-composite: exclude; padding:1px;
    }
    .card:hover { transform: translateY(-1px); }

    .meta-row { display:flex; gap:8px; align-items:center; color:$subtext; font-size:.9rem; flex-wrap: wrap; }
    .chip { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border:1px solid $border;
            border-radius:999px; background:$faint; }

    .card ul { margin:.25rem 0 .75rem 1.15rem; }
    .card ul li { line-height:1.55; margin:.28rem 0; }
    .card ul li::marker { color:$accent; font-size:1.05em; }

    .copywrap { position:relative; }
    .copybtn {
        position:absolute; top:-8px; right:-8px; font-size:12px; padding:4px 8px;
        border-radius:8px; border:1px solid $border; cursor:pointer; background:$panel;
    }
    .copybtn:hover { filter:brightness(1.05); }

    /* Control bar directly under the title, no border */
    .controlbar { display:flex; gap:14px; align-items:center; flex-wrap:wrap; background:transparent; border:none; padding:6px 0; margin-top:.15rem; }
    </style>
    """).substitute(cfg)

    st.markdown(css, unsafe_allow_html=True)

# ----------------------------
# Utilities
# ----------------------------
def file_to_base64(file_bytes: bytes, mime: str = "image/png") -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def detect_mime(name: str) -> str:
    n = (name or "").lower()
    if n.endswith((".jpg", ".jpeg")): return "image/jpeg"
    if n.endswith(".webp"): return "image/webp"
    if n.endswith(".svg"): return "image/svg+xml"
    return "image/png"

def normalize_bullets_minmax(text_block: str, min_n: int = 4, max_n: int = 6) -> str:
    if not text_block: return ""
    lines = [l.strip() for l in text_block.splitlines() if l.strip()]
    if len(lines) < min_n:
        joined = " ".join(lines) if lines else text_block.strip()
        sent = re.split(r"(?<=[.!?])\s+", joined)
        lines = [s.strip() for s in sent if s.strip()]
    lines = lines[:max_n]
    cleaned = []
    for l in lines:
        l = l.lstrip("•-*–—»· ").strip()
        if not l.startswith("- "): l = "- " + l
        cleaned.append(l)
    while len(cleaned) < min_n:
        cleaned.append("- (no further distinct point identified)")
    return "\n".join(cleaned[:max_n])

def split_points(text_block: str) -> List[str]:
    return [line[2:].strip() for line in text_block.splitlines() if line.strip().startswith("- ")]

def render_points_html(points: List[str]) -> str:
    if not points: return ""
    return "<ul>" + "".join(f"<li>{p}</li>" for p in points) + "</ul>"

def copy_button_js(block_id: str) -> str:
    return f"""
    <script>
    function copyPoints_{block_id}(){{
        const el = document.getElementById('{block_id}');
        if(!el) return;
        navigator.clipboard.writeText(el.innerText);
    }}
    </script>
    """

# ----------------------------
# Prompts
# ----------------------------
QUAL_SYSTEM = """
You are a senior data analyst advising business stakeholders.
Provide 3–4 concise bullets (start each with "- "). Focus on business meaning, not chart mechanics.
Use approximate numbers only if clearly legible. Plain text only.
"""
def qual_user_prompt():
    return [{"type":"text","text":"Analyze this chart image and return 4–6 concise, business-focused bullet points."}]

QUANT_SYSTEM = """
You are a data visualization analyst. Return plain text with sections:
Insights: (3–4 bullets)
Key numbers (approx): (only if visible)
Notables: (optional peaks/outliers/gaps)
"""
def quant_user_prompt():
    return [{"type":"text","text":"Analyze this chart and produce the specified sections (text only)."}]

QA_SYSTEM = "Answer questions about the chart concisely from what is visible."

# ----------------------------
# LLM calls
# ----------------------------
def run_qualitative(img_bytes: bytes, mime: str) -> str:
    content = qual_user_prompt()
    content.append({"type":"image_url","image_url":{"url": file_to_base64(img_bytes, mime=mime)}})
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{"role":"system","content":QUAL_SYSTEM},{"role":"user","content":content}],
        temperature=0.2, max_completion_tokens=700, stream=False,
    )
    return resp.choices[0].message.content.strip()

def run_quantitative(img_bytes: bytes, mime: str) -> str:
    content = quant_user_prompt()
    content.append({"type":"image_url","image_url":{"url": file_to_base64(img_bytes, mime=mime)}})
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{"role":"system","content":QUANT_SYSTEM},{"role":"user","content":content}],
        temperature=0.2, max_completion_tokens=900, stream=False,
    )
    return resp.choices[0].message.content.strip()

def ask_chart_question(img_bytes: bytes, mime: str, question: str) -> str:
    content=[{"type":"text","text":question},{"type":"image_url","image_url":{"url": file_to_base64(img_bytes, mime=mime)}}]
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{"role":"system","content":QA_SYSTEM},{"role":"user","content":content}],
        temperature=0.2, max_completion_tokens=400, stream=False,
    )
    return resp.choices[0].message.content

def combine_summaries(per_chart: List[str]) -> str:
    joined = "\n\n---\n\n".join([f"Chart {i+1}:\n{t}" for i, t in enumerate(per_chart)])
    system = "Synthesize multiple chart write-ups into 4–6 crisp bullets (plain text, '- ' start)."
    resp = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":joined}],
        temperature=0.2, max_completion_tokens=450, stream=False,
    )
    return resp.choices[0].message.content.strip()

def generate_pdf(per_chart_texts, overall_summary):
    buffer = io.BytesIO(); c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4; x_margin = 0.75*inch; y = height - 1*inch
    c.setFont("Helvetica-Bold", 16); c.drawString(x_margin, y, "Chart Insights Report"); y -= 0.4*inch
    c.setFont("Helvetica", 11)
    for i, text in enumerate(per_chart_texts):
        if y < 1*inch: c.showPage(); y = height - 1*inch; c.setFont("Helvetica", 11)
        c.setFont("Helvetica-Bold", 12); c.drawString(x_margin, y, f"Chart {i+1} Insights:"); y -= 0.25*inch
        c.setFont("Helvetica", 10)
        for line in text.split("\n"):
            for wl in simpleSplit(line, "Helvetica", 10, width - 2*x_margin):
                if y < 1*inch: c.showPage(); y = height - 1*inch; c.setFont("Helvetica", 10)
                c.drawString(x_margin, y, wl); y -= 0.18*inch
        y -= 0.3*inch
    if overall_summary:
        if y < 1.5*inch: c.showPage(); y = height - 1*inch
        c.setFont("Helvetica-Bold", 12); c.drawString(x_margin, y, "Overall Summary:"); y -= 0.25*inch
        c.setFont("Helvetica", 10)
        for line in overall_summary.split("\n"):
            for wl in simpleSplit(line, "Helvetica", 10, width - 2*x_margin):
                if y < 1*inch: c.showPage(); y = height - 1*inch; c.setFont("Helvetica", 10)
                c.drawString(x_margin, y, wl); y -= 0.18*inch
    c.save(); buffer.seek(0); return buffer

# ----------------------------
# Title + Control Bar (under title, no divider)
# ----------------------------
st.markdown('<h2>📊 Chart Insight Agent</h2>', unsafe_allow_html=True)
with st.container():
    st.markdown('<div class="controlbar">', unsafe_allow_html=True)
    c1, c2, _ = st.columns([2, 2, 6])
    with c1:
        mode = st.selectbox("Mode", ["Qualitative (Executive)", "Quantitative (Developer)"], index=0,
                            help="Qualitative: exec takeaways. Quantitative: structured details.")
    with c2:
        theme_choice = st.selectbox("Theme", ["Light ☀️", "Dark 🌙"], index=0, help="Switch app theme")
    st.markdown('</div>', unsafe_allow_html=True)

apply_theme("Dark" if "Dark" in theme_choice else "Light")

# --- Tabs ---
tab1, tab2 = st.tabs(["🧠 Analyze", "🕓 History"])

with tab1:
    st.header("Analyze Charts")
    uploads = st.file_uploader("Upload one or more charts to analyze:",
                               type=["png","jpg","jpeg"], accept_multiple_files=True, key="analyze_uploader")

    if uploads:
        st.session_state.chart_data = []; per_chart_texts: List[str] = []

        for i, up in enumerate(uploads):
            mime = detect_mime(up.name); img_bytes = up.read()
            st.session_state.chart_data.append({'name': up.name,'bytes': img_bytes,'mime': mime,'index': i})

            left, right = st.columns([1.05, 1], vertical_alignment="top")

            with left:
                st.markdown(f"**{up.name}**")
                if mime == "image/svg+xml":
                    st.markdown(f'<img src="data:{mime};base64,{base64.b64encode(img_bytes).decode()}" style="width:100%;max-width:560px;border-radius:12px;">', unsafe_allow_html=True)
                else:
                    try:
                        img = Image.open(io.BytesIO(img_bytes))
                        st.image(img, use_container_width=True)
                    except Exception:
                        st.write(f"📄 {up.name} (preview unavailable)")

                qa_key = f"qa_{i}"
                row1, _ = st.columns([1, 3])
                with row1:
                    qa_toggle = st.button("Ask Question", key=f"btn_{i}", use_container_width=True)
                if qa_toggle:
                    st.session_state.show_qa[qa_key] = not st.session_state.show_qa.get(qa_key, False)
                    st.session_state.qa_active[i] = bool(st.session_state.show_qa[qa_key])
                if st.session_state.show_qa.get(qa_key, False):
                    question = st.text_input("Your question:", key=f"q_{i}", placeholder="e.g., Which region leads by the end?")
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        ask_btn = st.button("Get Answer", key=f"ask_{i}", type="primary", use_container_width=True)
                    with col2:
                        if st.button("Cancel", key=f"cancel_{i}", use_container_width=True):
                            st.session_state.show_qa[qa_key] = False; st.session_state.qa_active[i] = False; st.rerun()
                    if ask_btn and question:
                        with st.spinner("Analyzing chart..."):
                            try:
                                st.write(ask_chart_question(img_bytes, mime, question))
                            except Exception as e:
                                st.error(f"Error: {e}")
                    st.markdown("---")

            with right:
                with st.spinner(f"Analyzing: {up.name}"):
                    try:
                        if mode == "Qualitative (Executive)":
                            raw = run_qualitative(img_bytes, mime)
                            displayed_text = normalize_bullets_minmax(raw, min_n=4, max_n=6)
                        else:
                            displayed_text = run_quantitative(img_bytes, mime)

                        per_chart_texts.append(displayed_text)

                        # update history (dedupe by filename)
                        st.session_state["history"] = [h for h in st.session_state["history"] if h["filename"] != up.name]
                        st.session_state["history"].append({"filename": up.name,"image": img_bytes,"insights": displayed_text})

                        pts = split_points(displayed_text)
                        html_points = render_points_html(pts) if pts else f"<div>{displayed_text}</div>"
                        block_id = f"blk_{i}"
                        st.markdown(copy_button_js(block_id), unsafe_allow_html=True)
                        st.markdown(f"""
                            <div class="copywrap">
                                <button class="copybtn" onclick="copyPoints_{block_id}()">Copy</button>
                                <div class="card" id="{block_id}">
                                    <div class="meta-row">
                                        <span class="chip">🧠 {mode}</span>
                                        <span class="chip">🖼 {up.name}</span>
                                    </div>
                                    <div style="height:8px;"></div>
                                    {html_points}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

                        single_pdf = generate_pdf([displayed_text], None)
                        st.download_button(label=f"📥 Download {up.name} (PDF)", data=single_pdf,
                                           file_name=f"{up.name}_insights.pdf", mime="application/pdf",
                                           use_container_width=True, key=f"analyze_download_{i}")
                        st.toast(f"Analyzed {up.name}", icon="✅")
                    except Exception as e:
                        st.error(f"Error analyzing {up.name}: {e}")

            st.divider()

        if len(per_chart_texts) >= 1:
            st.subheader("Overall summary (all charts)")
            with st.spinner("Synthesizing cross-chart brief..."):
                try:
                    combo = combine_summaries(per_chart_texts)
                    combo_bullets = normalize_bullets_minmax(combo, min_n=4, max_n=6)
                    pts = split_points(combo_bullets); html_points = render_points_html(pts)
                    block_id = "overall_points"; st.markdown(copy_button_js(block_id), unsafe_allow_html=True)
                    st.markdown(f"""
                        <div class="copywrap">
                            <button class="copybtn" onclick="copyPoints_{block_id}()">Copy</button>
                            <div class="card" id="{block_id}">
                                {html_points}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    pdf_buffer = generate_pdf(per_chart_texts, combo_bullets)
                    st.download_button(label="📥 Download Overall content (PDF)", data=pdf_buffer,
                                       file_name="chart_insights_report.pdf", mime="application/pdf",
                                       use_container_width=True, key="analyze_download_all")
                except Exception as e:
                    st.error(f"Failed to combine summaries: {e}")
    else:
        st.info("📤 Upload chart images to get started with analysis and Q&A.")

with tab2:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("Previously Analyzed Charts")
    with col2:
        if st.button("🗑️ Clear History", type="secondary", use_container_width=True, key="clear_history_btn"):
            st.session_state["history"] = []
            # Clear the uploader to prevent re-analysis on rerun
            if "analyze_uploader" in st.session_state:
                del st.session_state["analyze_uploader"]
            st.rerun()

    if not st.session_state["history"]:
        st.info("No charts analyzed yet. Upload charts in the **Analyze** tab first.")
    else:
        # de-dup by filename (keep last)
        seen = {}
        for item in reversed(st.session_state["history"]):
            if item["filename"] not in seen: seen[item["filename"]] = item
        dedup = list(reversed(list(seen.values()))); st.session_state["history"] = dedup

        for idx, item in enumerate(dedup):
            left, right = st.columns([1.05, 1], vertical_alignment="top")
            with left:
                st.markdown(f"**{item['filename']}**")
                st.image(item["image"], use_container_width=True)
            with right:
                pts = split_points(item["insights"])
                html_points = render_points_html(pts) if pts else f"<div>{item['insights']}</div>"
                block_id = f"hist_{idx}"; st.markdown(copy_button_js(block_id), unsafe_allow_html=True)
                st.markdown(f"""
                    <div class="copywrap">
                        <button class="copybtn" onclick="copyPoints_{block_id}()">Copy</button>
                        <div class="card" id="{block_id}">
                            <div class="meta-row">
                                <span class="chip">🗂 History item</span>
                                <span class="chip">🖼 {item['filename']}</span>
                            </div>
                            <div style="height:8px;"></div>
                            {html_points}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                single_pdf = generate_pdf([item["insights"]], None)
                st.download_button(label=f"📥 Download {item['filename']} (PDF)", data=single_pdf,
                                   file_name=f"{item['filename']}_insights.pdf", mime="application/pdf",
                                   use_container_width=True, key=f"download_{item['filename']}")
            st.divider()

        all_texts = [it["insights"] for it in st.session_state["history"]]
        combined_pdf = generate_pdf(all_texts, None)
        st.download_button(label="📦 Download All (PDF)", data=combined_pdf,
                           file_name="all_chart_insights.pdf", mime="application/pdf",
                           use_container_width=True, key="history_download_all")