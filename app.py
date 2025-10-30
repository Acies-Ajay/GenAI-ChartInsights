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

load_dotenv()
st.set_page_config(page_title="Chart Insights (Groq + Streamlit)", page_icon="📊", layout="wide")

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
TEXT_MODEL   = "llama-3.3-70b-versatile"

THUMB_WIDTH = 240
GRID_COLS   = 4

if "history" not in st.session_state:
    st.session_state["history"] = []

def get_groq() -> Groq:
    api_key = os.getenv("GROQ_DEMO_API_KEY")
    if not api_key:
        st.error("GROQ_DEMO_API_KEY is missing. Put it in your environment or a .env file.")
        st.stop()
    return Groq(api_key=api_key)

client = get_groq()

# Initialize session state
if 'chart_data' not in st.session_state:
    st.session_state.chart_data = []
if 'show_qa' not in st.session_state:
    st.session_state.show_qa = {}
if 'qa_active' not in st.session_state:
    st.session_state.qa_active = {}

# ----------------------------
# Theme (Light/Dark) — CSS injector
# ----------------------------
def apply_theme(mode: str):
    if mode == "Dark":
        bg = "#0f172a"      # slate-900
        panel = "#111827"   # gray-900
        text = "#e5e7eb"    # gray-200
        subtext = "#cbd5e1" # slate-300
        accent = "#60a5fa"  # blue-400
        border = "#334155"  # slate-700
    else:
        bg = "#ffffff"
        panel = "#ffffff"
        text = "#111827"    # gray-900
        subtext = "#374151" # gray-700
        accent = "#1f6feb"  # blue-600
        border = "#e5e7eb"  # gray-200

    st.markdown(
        f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            background: {bg} !important;
            color: {text} !important;
        }}
        .stMarkdown, .stText, .stCaption, p, li, span, div {{
            color: {text} !important;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: {text} !important;
        }}
        [data-testid="stSidebar"] {{
            background: {panel} !important;
            color: {text} !important;
            border-right: 1px solid {border};
        }}
        [data-testid="stHeader"] {{
            background: transparent !important;
        }}
        .st-emotion-cache-1y4p8pa, .st-emotion-cache-ue6h4q, .st-emotion-cache-1kyxreq {{
            color: {subtext} !important;
        }}
        /* Cards / containers */
        .st-emotion-cache-16idsys, .st-emotion-cache-13k62yr, .st-emotion-cache-1r6slb0 {{
            background: {panel} !important;
            color: {text} !important;
            border: 1px solid {border} !important;
            border-radius: 12px !important;
        }}
        /* Links */
        a, a:visited {{ color: {accent} !important; }}
        /* Code blocks (just in case) */
        pre, code {{ color: {text} !important; }}
        </style>
        """,
        unsafe_allow_html=True
    )

# ----------------------------
# Utilities
# ----------------------------
def file_to_base64(file_bytes: bytes, mime: str = "image/png") -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def detect_mime(name: str) -> str:
    name = (name or "").lower()
    if name.endswith((".jpg",".jpeg")): return "image/jpeg"
    if name.endswith(".webp"): return "image/webp"
    if name.endswith(".svg"): return "image/svg+xml"
    return "image/png"

def normalize_bullets_minmax(text_block: str, min_n: int = 4, max_n: int = 6) -> str:
    """
    Produce between min_n and max_n bullet lines starting with "- ".
    If too few lines, split by sentences; if too many, truncate.
    """
    if not text_block:
        return ""
    # split by lines first
    lines = [l.strip() for l in text_block.splitlines() if l.strip()]
    if len(lines) < min_n:
        joined = " ".join(lines) if lines else text_block.strip()
        sent = re.split(r"(?<=[.!?])\s+", joined)
        lines = [s.strip() for s in sent if s.strip()]
    # trim to range
    lines = lines[:max_n]
    # ensure "- " prefix
    cleaned = []
    for l in lines:
        l = l.lstrip("•-*–—»· ").strip()
        if not l.startswith("- "):
            l = "- " + l
        cleaned.append(l)
    # still too few? pad harmlessly
    while len(cleaned) < min_n:
        cleaned.append("- (no further distinct insight identified)")
    return "\n".join(cleaned[:max_n])

# ----------------------------
# Prompts (business perspective)
# ----------------------------
# Qualitative (Executive): bullets only (no options UI)
QUAL_SYSTEM = """
You are a senior data analyst advising business stakeholders.
Your task: produce decision-focused insights from a chart image in a business perspective.

Strict rules:
Provide 3–4 concise bullets; each must start with "- " and be one sentence.
Focus on business meaning: trends, contrasts, inflection points, priorities, implications.
Do NOT describe chart mechanics (type, axes, legend) unless essential to the insight.
Avoid generic remarks and sections like "Max/Min/Outliers".
Use approximate numbers ONLY if clearly legible; never fabricate values.
No HTML, no emojis, no numbering beyond the leading "- ".
Output must be plain text only.
"""

def qual_user_prompt() -> list:
    return [{
        "type": "text",
        "text": ("Analyze this chart image and return 4–6 concise, business-focused bullet points. "
                 "Avoid chart mechanics; emphasize impact, priorities, and actionable interpretation.")
    }]

# Quantitative (Developer): text-only sections, baked-in business perspective (no lens picker)
QUANT_SYSTEM = """
You are a data visualization analyst producing business-ready text about a chart image.
Return plain text only, with the following sections (omit a section if not applicable):

Insights:
<3–4 concise, business-focused bullets. Each line starts with '- ' and is one sentence>

Key numbers (approx):
<bullets like: '- Metric: ~value unit'> Use only if values are clearly legible. Otherwise skip this section.

Notables:
<optional bullets for peaks, troughs, outliers, gaps, or segment contrasts. Each line starts with '- '>

Rules:
Prioritize what helps decisions on growth/revenue, risk/variability, and efficiency/cost.
No HTML, no emojis, no numbering beyond the leading '- '.
Never invent precise values; use qualitative phrasing if unclear.
Keep it compact and readable.
"""

def quant_user_prompt() -> list:
    return [{
        "type": "text",
        "text": ("Analyze this chart and produce the three sections as specified, text only. "
                 "If a section does not apply, omit it. Keep a business perspective.")
    }]

# Q&A System Prompt
QA_SYSTEM = """
You are a data analyst assistant. Answer the user's question about the chart image clearly and concisely.
- Provide direct, factual answers based on what you can see in the chart.
- If numbers are clearly visible, use them. Otherwise, use comparative terms.
- Keep responses focused and to-the-point.
- If you cannot answer the question based on the chart, say so clearly.
"""

# ----------------------------
# LLM calls
# ----------------------------
def run_qualitative(img_bytes: bytes, mime: str) -> str:
    content = qual_user_prompt()
    content.append({"type": "image_url", "image_url": {"url": file_to_base64(img_bytes, mime=mime)}})
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": QUAL_SYSTEM},
            {"role": "user", "content": content},
        ],
        temperature=0.2,
        max_completion_tokens=700,
        stream=False,
    )
    return resp.choices[0].message.content.strip()

def run_quantitative(img_bytes: bytes, mime: str) -> str:
    content = quant_user_prompt()
    content.append({"type": "image_url", "image_url": {"url": file_to_base64(img_bytes, mime=mime)}})
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": QUANT_SYSTEM},
            {"role": "user", "content": content},
        ],
        temperature=0.2,
        max_completion_tokens=900,
        stream=False,
    )
    return resp.choices[0].message.content.strip()

def ask_chart_question(img_bytes: bytes, mime: str, question: str) -> str:
    """Answer a specific question about a chart image"""
    content = [
        {"type": "text", "text": question},
        {"type": "image_url", "image_url": {"url": file_to_base64(img_bytes, mime=mime)}}
    ]
    resp = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": QA_SYSTEM},
            {"role": "user", "content": content},
        ],
        temperature=0.2,
        max_completion_tokens=400,
        stream=False,
    )
    return resp.choices[0].message.content

def combine_summaries(per_chart: List[str]) -> str:
    joined = "\n\n---\n\n".join([f"Chart {i+1}:\n{txt}" for i, txt in enumerate(per_chart)])
    system = (
        "You are a senior analyst. Synthesize multiple chart write-ups into a single, priority-focused brief "
        "for business leaders. Respond as 4–6 crisp bullets (plain text, each line starting with '- ')."
    )
    user = f"""Combine these per-chart texts into a unified set of priorities (avoid repetition, surface conflicts, note risks/opportunities):

{joined}"""
    resp = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.2,
        max_completion_tokens=450,
        stream=False,
    )
    return resp.choices[0].message.content.strip()

def generate_pdf(per_chart_texts, overall_summary):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    x_margin = 0.75 * inch
    y = height - 1 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawString(x_margin, y, "Chart Insights Report")
    y -= 0.4 * inch

    c.setFont("Helvetica", 11)
    for i, text in enumerate(per_chart_texts):
        if y < 1 * inch:
            c.showPage()
            y = height - 1 * inch
            c.setFont("Helvetica", 11)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x_margin, y, f"Chart {i+1} Insights:")
        y -= 0.25 * inch

        c.setFont("Helvetica", 10)
        for line in text.split("\n"):
            wrapped_lines = simpleSplit(line, "Helvetica", 10, width - 2*x_margin)
            for wl in wrapped_lines:
                if y < 1 * inch:
                    c.showPage()
                    y = height - 1 * inch
                    c.setFont("Helvetica", 10)
                c.drawString(x_margin, y, wl)
                y -= 0.18 * inch
        y -= 0.3 * inch

    # Add overall summary
    if overall_summary:
        if y < 1.5 * inch:
            c.showPage()
            y = height - 1 * inch
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x_margin, y, "Overall Summary:")
        y -= 0.25 * inch
        c.setFont("Helvetica", 10)
        for line in overall_summary.split("\n"):
            wrapped_lines = simpleSplit(line, "Helvetica", 10, width - 2*x_margin)
            for wl in wrapped_lines:
                if y < 1 * inch:
                    c.showPage()
                    y = height - 1 * inch
                    c.setFont("Helvetica", 10)
                c.drawString(x_margin, y, wl)
                y -= 0.18 * inch

    c.save()
    buffer.seek(0)
    return buffer



# ----------------------------
# UI
# ----------------------------
st.markdown("<h2>📊 Chart Insight Agent — Insights & Q&A</h2>", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("⚙️ Mode & Theme")
    mode = st.radio("Mode", ["Qualitative (Executive)", "Quantitative (Developer)"], index=0)
    theme_choice = st.radio("Theme", ["Light", "Dark"], index=0)
    st.caption("Upload chart images to get automatic insights and ask custom questions.")

apply_theme(theme_choice)


# --- Tabs ---
tab1, tab2 = st.tabs(["🧠 Analyze", "🕓 History"])

with tab1:
    st.header("Analyze Charts")
    uploads = st.file_uploader(
        "Upload one or more charts to analyze:",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="analyze_uploader"
    )
    
    # Process uploads only in Analyze tab
    if uploads:
        # Clear and store chart data in session state
        st.session_state.chart_data = []
        
        cols = st.columns(GRID_COLS)
        per_chart_texts: List[str] = []

        for i, up in enumerate(uploads):
            mime = detect_mime(up.name)
            img_bytes = up.read()
            
            # Store for Q&A later
            st.session_state.chart_data.append({
                'name': up.name,
                'bytes': img_bytes,
                'mime': mime,
                'index': i
            })

            # Thumbnail preview - handle SVG differently
            with cols[i % GRID_COLS]:
                if mime == "image/svg+xml":
                    st.markdown(f'<img src="data:{mime};base64,{base64.b64encode(img_bytes).decode()}" width="{THUMB_WIDTH}">', unsafe_allow_html=True)
                    st.caption(up.name)
                else:
                    try:
                        img = Image.open(io.BytesIO(img_bytes))
                        st.image(img, caption=up.name, width=THUMB_WIDTH)
                    except Exception:
                        st.write(f"📄 {up.name} (preview unavailable)")

            # Chart name header with Ask Question button
            header_col1, header_col2 = st.columns([3, 1])
            with header_col1:
                if mode == "Qualitative (Executive)":
                    st.markdown(f"**Insights — {up.name}**")
                else:
                    st.markdown(f"**Details — {up.name}**")
            with header_col2:
                qa_key = f"qa_{i}"
                if st.button("🤔 Ask Question", key=f"btn_{i}", use_container_width=True):
                    st.session_state.show_qa[qa_key] = not st.session_state.show_qa.get(qa_key, False)
                    # Mark that Q&A is active for this chart
                    if st.session_state.show_qa[qa_key]:
                        st.session_state.qa_active[i] = True
                    else:
                        st.session_state.qa_active[i] = False
            
            # Q&A input section (appears when button clicked)
            if st.session_state.show_qa.get(qa_key, False):
                with st.container():
                    st.markdown("---")
                    question = st.text_input(
                        "Your question:",
                        key=f"q_{i}",
                        placeholder="e.g., What's the trend? Which performed best? Any outliers?"
                    )
                    
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        ask_btn = st.button("Get Answer", key=f"ask_{i}", type="primary")
                    with col2:
                        if st.button("Cancel", key=f"cancel_{i}"):
                            st.session_state.show_qa[qa_key] = False
                            st.session_state.qa_active[i] = False
                            st.rerun()
                    
                    if ask_btn and question:
                        with st.spinner("Analyzing chart..."):
                            try:
                                answer = ask_chart_question(img_bytes, mime, question)
                                st.success("**Answer:**")
                                st.write(answer)
                            except Exception as e:
                                st.error(f"Error: {e}")
                    
                    st.markdown("---")
            
            # Only show automatic insights if Q&A is NOT active for this chart
            if not st.session_state.qa_active.get(i, False):
                with st.spinner(f"Analyzing: {up.name}"):
                    try:
                        if mode == "Qualitative (Executive)":
                            raw = run_qualitative(img_bytes, mime)
                            bullets = normalize_bullets_minmax(raw, min_n=4, max_n=6)
                            st.markdown(bullets)
                            displayed_text = bullets
                        else:
                            text = run_quantitative(img_bytes, mime)
                            st.markdown(text)
                            displayed_text = text
                        per_chart_texts.append(displayed_text)

                        # --- Save to session_state for History tab ---
                        if "history" not in st.session_state:
                            st.session_state["history"] = []

                        # Remove any existing entry with the same filename first
                        st.session_state["history"] = [
                            h for h in st.session_state["history"] 
                            if h["filename"] != up.name
                        ]
                        
                        # Add the new entry
                        st.session_state["history"].append({
                            "filename": up.name,
                            "image": img_bytes,
                            "insights": displayed_text,
                        })

                        # --- 🧾 Individual PDF Download for this chart ---
                        single_pdf = generate_pdf([displayed_text], None)
                        st.download_button(
                            label=f"📥 Download {up.name} Insights (PDF)",
                            data=single_pdf,
                            file_name=f"{up.name}_insights.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"analyze_download_{i}" 
                        )

                    except Exception as e:
                        st.error(f"Error analyzing {up.name}: {e}")

        # Overall synthesis - only if we have chart texts (i.e., no Q&A active)
        if len(per_chart_texts) >= 1:
            if mode == "Qualitative (Executive)":
                st.subheader("Overall summary (all charts)")
            else:
                st.subheader("Overall priorities (all charts)")
            with st.spinner("Synthesizing cross-chart brief..."):
                try:
                    combo = combine_summaries(per_chart_texts)
                    # Ensure bullets & contrast in both themes
                    combo_bullets = normalize_bullets_minmax(combo, min_n=4, max_n=6)
                    st.markdown(combo_bullets)
                    

                    # ---- PDF Download Section ----
                    pdf_buffer = generate_pdf(per_chart_texts, combo_bullets)
                    st.download_button(
                        label="📥 Download Overall content as PDF",
                        data=pdf_buffer,
                        file_name="chart_insights_report.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="analyze_download_all"
                    )

                except Exception as e:
                    st.error(f"Failed to combine summaries: {e}")
    else:
        st.info("📤 Upload chart images to get started with insights and Q&A.")

with tab2:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("Previously Analyzed Charts")
    with col2:
        if st.button("🗑️ Clear History", type="secondary", use_container_width=True):
            st.session_state["history"] = []
            st.rerun()

    if "history" not in st.session_state or len(st.session_state["history"]) == 0:
        st.info("No charts analyzed yet. Upload charts in the **Analyze** tab first.")
    else:
        # Auto-deduplicate history based on filename (keep only the last occurrence)
        seen = {}
        for item in reversed(st.session_state["history"]):
            if item["filename"] not in seen:
                seen[item["filename"]] = item
        
        # Update history with deduplicated list
        deduplicated_history = list(reversed(list(seen.values())))
        st.session_state["history"] = deduplicated_history
        
        # Display history items (read-only, no analysis)
        for item in deduplicated_history:
            st.markdown(f"### 🖼️ {item['filename']}")
            st.image(item["image"])
            st.markdown(item["insights"])

            # --- Individual PDF download ---
            single_pdf = generate_pdf([item["insights"]], None)
            st.download_button(
                label=f"📥 Download {item['filename']} Insights (PDF)",
                data=single_pdf,
                file_name=f"{item['filename']}_insights.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"download_{item['filename']}"
            )
            st.divider()

        # --- Combined PDF for all history ---
        all_texts = [item["insights"] for item in st.session_state["history"]]
        combined_pdf = generate_pdf(all_texts, None)
        st.download_button(
            label="📦 Download All Insights (PDF)",
            data=combined_pdf,
            file_name="all_chart_insights.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="history_download_all"
        )