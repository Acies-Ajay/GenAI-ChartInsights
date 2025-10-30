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

# Initialize session state
if "history" not in st.session_state:
    st.session_state["history"] = []
if 'chart_data' not in st.session_state:
    st.session_state.chart_data = []
if 'show_qa' not in st.session_state:
    st.session_state.show_qa = {}
if 'qa_active' not in st.session_state:
    st.session_state.qa_active = {}

def get_groq() -> Groq:
    api_key = os.getenv("GROQ_DEMO_API_KEY")
    if not api_key:
        st.error("GROQ_DEMO_API_KEY is missing. Put it in your environment or a .env file.")
        st.stop()
    return Groq(api_key=api_key)

client = get_groq()

# ----------------------------
# Chart Validation Function
# ----------------------------
def is_chart_image(img_bytes: bytes, mime: str) -> tuple[bool, str]:
    """
    Validates if the uploaded image is a chart/graph.
    Returns: (is_valid, error_message)
    """
    try:
        content = [
            {
                "type": "text",
                "text": "Is this image a chart, graph, diagram, or data visualization? Answer with ONLY 'YES' or 'NO'."
            },
            {
                "type": "image_url",
                "image_url": {"url": file_to_base64(img_bytes, mime=mime)}
            }
        ]
        
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an image classifier. Respond with only 'YES' if the image contains a chart, graph, diagram, or data visualization. Respond with 'NO' for photos, screenshots, text documents, or other non-chart images."
                },
                {"role": "user", "content": content}
            ],
            temperature=0.1,
            max_completion_tokens=10,
            stream=False,
        )
        
        answer = resp.choices[0].message.content.strip().upper()
        
        if "YES" in answer:
            return True, ""
        else:
            return False, "Please upload only charts, graphs, or data visualizations."
            
    except Exception as e:
        # If validation fails, allow the image but log the error
        print(f"Validation error: {e}")
        return True, ""

# ----------------------------
# Theme (Light/Dark) — CSS injector
# ----------------------------
def apply_theme(theme):
    if theme == "Light":
        gradient_animation = """
            background: linear-gradient(270deg, #fdfbfb, #ebedee, #d7e1ec, #f5f7fa);
            background-size: 800% 800%;
            animation: gradientShift 15s ease infinite;
        """
        text_color = "#222"
        accent_color = "linear-gradient(90deg, #667eea, #764ba2)"
        button_glow = "rgba(102, 126, 234, 0.5)"
        sidebar_text_color = "#111"
        button_text_color = "#fff"
        button_bg_gradient = "linear-gradient(90deg, #667eea, #764ba2)"
        button_hover_glow = "rgba(102, 126, 234, 0.6)"
        dataframe_text_color = "#222"
        card_text_color = "#222"
        card_bg = "rgba(255, 255, 255, 0.85)"
        upload_bg_color = "rgba(255, 255, 255, 0.4)"
        upload_text_color = "#222"
        upload_border_color = "rgba(100, 100, 100, 0.3)"
    else:  # Dark mode
        gradient_animation = """
            background: linear-gradient(270deg, #0f2027, #203a43, #2c5364, #1c1c1c);
            background-size: 800% 800%;
            animation: gradientShift 18s ease infinite;
        """
        text_color = "#f0f0f0"
        accent_color = "linear-gradient(90deg, #00c6ff, #0072ff)"
        button_glow = "rgba(0, 114, 255, 0.5)"
        sidebar_text_color = "#f0f0f0"
        button_text_color = "#fff"
        button_bg_gradient = "linear-gradient(90deg, #00c6ff, #0072ff)"
        button_hover_glow = "rgba(0, 114, 255, 0.6)"
        dataframe_text_color = "#f0f0f0"
        card_text_color = "#f0f0f0"
        card_bg = "rgba(20, 30, 48, 0.85)"
        upload_bg_color = "rgba(30, 40, 60, 0.6)"
        upload_text_color = "#f0f0f0"
        upload_border_color = "rgba(100, 180, 255, 0.4)"

    st.markdown(
        f"""
        <style>
        /* Animated Gradient Background */
        @keyframes gradientShift {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}

        [data-testid="stAppViewContainer"] {{
            {gradient_animation}
            color: {text_color};
        }}

        /* Force text color inside app */
        [data-testid="stAppViewContainer"] * {{
            color: {text_color} !important;
        }}

        /* Sidebar */
        [data-testid="stSidebar"] {{
            border-radius: 16px;
            padding: 12px 16px;
            background: {card_bg};
            backdrop-filter: blur(10px);
            color: {sidebar_text_color};
        }}
        [data-testid="stSidebar"] * {{
            color: {sidebar_text_color} !important;
        }}

        /* Gradient headings */
        h1, h2, h3 {{
            background: {accent_color};
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        /* Buttons */
        div.stButton > button {{
            background: {button_bg_gradient} !important;
            color: {button_text_color} !important;
            border: none;
            border-radius: 12px;
            padding: 0.6em 1.4em;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 10px {button_glow};
        }}
        div.stButton > button:hover {{
            transform: scale(1.06);
            box-shadow: 0 0 20px {button_hover_glow};
        }}

        /* Card styling */
        .card {{
            background: {card_bg};
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }}

        .card ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}

        .card ul li {{
            line-height: 1.6;
            margin: 8px 0;
        }}

        .chip {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 20px;
            background: rgba(100, 150, 255, 0.2);
            font-size: 0.85rem;
            margin-right: 8px;
        }}

        /* File uploader container */
        [data-testid="stFileUploader"] {{
            background: {upload_bg_color} !important;
            border-radius: 12px;
            padding: 16px !important;
            border: 1px solid {upload_border_color} !important;
        }}

        /* File uploader ALL text elements */
        [data-testid="stFileUploader"] *,
        [data-testid="stFileUploader"] label,
        [data-testid="stFileUploader"] span,
        [data-testid="stFileUploader"] p,
        [data-testid="stFileUploader"] small,
        [data-testid="stFileUploader"] div,
        [data-testid="stFileUploader"] button {{
            color: {upload_text_color} !important;
        }}

        /* File uploader drop area */
        [data-testid="stFileUploader"] section {{
            background: {upload_bg_color} !important;
            border: 2px dashed {upload_border_color} !important;
            border-radius: 10px !important;
        }}

        /* Uploaded file names */
        [data-testid="stFileUploader"] [data-testid="stMarkdownContainer"] *,
        [data-testid="stFileUploader"] .uploadedFileName,
        [data-testid="stFileUploader"] .st-emotion-cache-1v0mbdj,
        section[data-testid="stFileUploader"] small,
        section[data-testid="stFileUploader"] > div > div > div {{
            color: {upload_text_color} !important;
            font-weight: 500 !important;
        }}

        /* File upload button */
        [data-testid="stFileUploader"] button {{
            background: {button_bg_gradient} !important;
            color: {button_text_color} !important;
            border: none !important;
            border-radius: 8px !important;
        }}

        /* Delete button on uploaded files */
        [data-testid="stFileUploader"] button[kind="icon"] {{
            color: {upload_text_color} !important;
        }}

        /* Table color fix */
        [data-testid="stTable"], [data-testid="stTable"] * {{
            color: {dataframe_text_color} !important;
        }}

        /* Text input fields - fix visibility in dark mode */
        input[type="text"], 
        textarea,
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea {{
            color: {text_color} !important;
            background-color: {upload_bg_color} !important;
            border: 1px solid {upload_border_color} !important;
            border-radius: 8px !important;
            padding: 8px 12px !important;
        }}

        /* Placeholder text */
        input::placeholder,
        textarea::placeholder {{
            color: rgba({text_color.replace('#', '')}, 0.5) !important;
            opacity: 0.7 !important;
        }}

        /* Download button styling */
        [data-testid="stDownloadButton"] button,
        [data-testid="stDownloadButton"] button *,
        [data-testid="stDownloadButton"] button p,
        [data-testid="stDownloadButton"] button span,
        [data-testid="stDownloadButton"] button div,
        [data-testid="stDownloadButton"] p,
        [data-testid="stDownloadButton"] span,
        [data-testid="stDownloadButton"] div,
        [data-testid="stDownloadButton"] label,
        button[kind="secondary"],
        button[kind="secondary"] *,
        button[kind="secondary"] p,
        button[kind="secondary"] span {{
            color: {button_text_color} !important;
            background: {button_bg_gradient} !important;
        }}
        
        /* Remove top padding and margin completely */
        .block-container {{
            padding-top: 0 !important;
            margin-top: 0 !important;
        }}
        
        /* Remove header spacing */
        header {{
            background-color: transparent !important;
        }}
        
        [data-testid="stHeader"] {{
            background-color: transparent !important;
            height: 0px !important;
        }}

        button:focus:not(:active) {{
            outline: none;
            box-shadow: 0 0 0 0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

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

# ----------------------------
# IMPROVED PROMPTS
# ----------------------------
QUAL_SYSTEM = """
You are a senior business analyst presenting insights to executives.

CRITICAL RULES:
- Provide ONLY business insights, trends, and strategic implications
- DO NOT mention any numbers, percentages, or metrics
- Focus on: patterns, trends, comparisons, business meaning, strategic takeaways
- Return exactly 4-6 bullet points
- Start each bullet with "- "
- Keep bullets concise and actionable
- Plain text only, no formatting

Example output:
- Sales show strong upward momentum in the digital channel
- Customer retention has become a competitive advantage
- Market share is consolidating among top performers
- Seasonal patterns indicate opportunity for strategic timing
"""

QUANT_SYSTEM = """
You are a data analyst extracting precise metrics from visualizations.

CRITICAL RULES:
- Provide ONLY numbers, metrics, percentages, and quantitative data
- DO NOT provide interpretations, insights, or business meaning
- Extract: exact values, percentages, ratios, counts, measurements
- Return exactly 4-6 bullet points with numerical data
- Start each bullet with "- "
- Be precise with numbers visible in the chart
- Plain text only, no formatting

Example output:
- Total revenue: $2.4M (Q4 2024)
- Growth rate: 23.5% year-over-year
- Top segment: Enterprise at 45% of total
- Customer count: 1,247 active users
- Average transaction: $892
"""

QA_SYSTEM = "Answer questions about the chart concisely from what is visible. Provide specific data points if asked."

def qual_user_prompt():
    return [{"type":"text","text":"Analyze this chart and provide 4-6 business insights. Focus ONLY on trends, patterns, and strategic implications. DO NOT include any numbers or metrics."}]

def quant_user_prompt():
    return [{"type":"text","text":"Extract 4-6 quantitative data points from this chart. Provide ONLY numbers, metrics, and measurements. DO NOT include interpretations or insights."}]

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
# UI - Sidebar
# ----------------------------
with st.sidebar:
    st.subheader("Mode & Theme")
    mode = st.radio("Analysis Mode", ["Qualitative", "Quantitative"], index=0,
                    help="Qualitative: Business insights only (no numbers)\nQuantitative: Numbers and metrics only")
    theme_choice = st.radio("Theme", ["Light", "Dark"], index=0)
    st.divider()
    st.caption("Qualitative: Trends & insights\nQuantitative: Numbers & metrics")

apply_theme(theme_choice)

# ----------------------------
# Title
# ----------------------------
st.markdown('<h2 style="margin-top:0; padding-top:0;">Chart Insight Agent</h2>', unsafe_allow_html=True)

# ----------------------------
# Tabs
# ----------------------------
tab1, tab2 = st.tabs(["Analyze", "History"])

with tab1:
    st.header("Analyze Charts")
    uploads = st.file_uploader("Upload one or more charts to analyze:",
                               type=["png","jpg","jpeg"], accept_multiple_files=True, key="analyze_uploader")

    if uploads:
        st.session_state.chart_data = []
        per_chart_texts: List[str] = []
        valid_uploads = []

        # First, validate all uploaded images
        with st.spinner("Validating uploaded images..."):
            for up in uploads:
                mime = detect_mime(up.name)
                img_bytes = up.read()
                
                is_valid, error_msg = is_chart_image(img_bytes, mime)
                
                if is_valid:
                    valid_uploads.append({
                        'file': up,
                        'name': up.name,
                        'bytes': img_bytes,
                        'mime': mime
                    })
                else:
                    st.error(f"{up.name}: {error_msg}")

        if not valid_uploads:
            st.warning("No valid chart images found. Please upload charts, graphs, or data visualizations.")
        else:
            for i, upload_data in enumerate(valid_uploads):
                up = upload_data['file']
                img_bytes = upload_data['bytes']
                mime = upload_data['mime']
                
                st.session_state.chart_data.append({
                    'name': upload_data['name'],
                    'bytes': img_bytes,
                    'mime': mime,
                    'index': i
                })

                left, right = st.columns([1.05, 1], vertical_alignment="top")

                with left:
                    st.markdown(f"**{upload_data['name']}**")
                    if mime == "image/svg+xml":
                        st.markdown(f'<img src="data:{mime};base64,{base64.b64encode(img_bytes).decode()}" style="width:100%;max-width:560px;border-radius:12px;">', unsafe_allow_html=True)
                    else:
                        try:
                            img = Image.open(io.BytesIO(img_bytes))
                            st.image(img, use_container_width=True)
                        except Exception:
                            st.write(f"{upload_data['name']} (preview unavailable)")

                    qa_key = f"qa_{i}"
                    if st.button("Ask Question", key=f"btn_{i}", type="primary", use_container_width=False):
                        st.session_state.show_qa[qa_key] = not st.session_state.show_qa.get(qa_key, False)
                        st.session_state.qa_active[i] = bool(st.session_state.show_qa[qa_key])
                    
                    if st.session_state.show_qa.get(qa_key, False):
                        question = st.text_input("Your question:", key=f"q_{i}", placeholder="e.g., Which region leads by the end?")
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            ask_btn = st.button("Get Answer", key=f"ask_{i}", type="primary", use_container_width=True)
                        with col2:
                            cancel_btn = st.button("Cancel", key=f"cancel_{i}", use_container_width=True)
                        
                        if cancel_btn:
                            st.session_state.show_qa[qa_key] = False
                            st.session_state.qa_active[i] = False
                            st.rerun()
                        
                        if ask_btn and question:
                            with st.spinner("Analyzing chart..."):
                                try:
                                    answer = ask_chart_question(img_bytes, mime, question)
                                    st.markdown(f"""
                                        <div class="card" style="margin-top: 10px;">
                                            <strong>Answer:</strong><br>
                                            {answer}
                                        </div>
                                    """, unsafe_allow_html=True)
                                except Exception as e:
                                    st.error(f"Error: {e}")
                        st.markdown("---")

                with right:
                    with st.spinner(f"Analyzing: {upload_data['name']}"):
                        try:
                            if mode == "Qualitative":
                                raw = run_qualitative(img_bytes, mime)
                                displayed_text = normalize_bullets_minmax(raw, min_n=4, max_n=6)
                                mode_label = "Business Insights"
                            else:
                                raw = run_quantitative(img_bytes, mime)
                                displayed_text = normalize_bullets_minmax(raw, min_n=4, max_n=6)
                                mode_label = "Data Metrics"

                            per_chart_texts.append(displayed_text)

                            # update history (dedupe by filename)
                            st.session_state["history"] = [h for h in st.session_state["history"] if h["filename"] != upload_data['name']]
                            st.session_state["history"].append({"filename": upload_data['name'],"image": img_bytes,"insights": displayed_text})

                            pts = split_points(displayed_text)
                            html_points = render_points_html(pts) if pts else f"<div>{displayed_text}</div>"
                            
                            st.markdown(f"""
                                <div class="card">
                                    <div>
                                        <span class="chip">{mode_label}</span>
                                        <span class="chip">{upload_data['name']}</span>
                                    </div>
                                    <div style="height:12px;"></div>
                                    {html_points}
                                </div>
                            """, unsafe_allow_html=True)

                            single_pdf = generate_pdf([displayed_text], None)
                            st.download_button(label=f"Download {upload_data['name']} (PDF)", data=single_pdf,
                                               file_name=f"{upload_data['name']}_insights.pdf", mime="application/pdf",
                                                key=f"analyze_download_{i}")
                            st.toast(f"Analyzed {upload_data['name']}", icon="✅")
                        except Exception as e:
                            st.error(f"Error analyzing {upload_data['name']}: {e}")

                st.divider()

            if len(per_chart_texts) >= 1:
                st.subheader("Overall summary (all charts)")
                with st.spinner("Synthesizing cross-chart brief..."):
                    try:
                        combo = combine_summaries(per_chart_texts)
                        combo_bullets = normalize_bullets_minmax(combo, min_n=4, max_n=6)
                        pts = split_points(combo_bullets)
                        html_points = render_points_html(pts)
                        
                        st.markdown(f"""
                            <div class="card">
                                {html_points}
                            </div>
                        """, unsafe_allow_html=True)
                        
                        pdf_buffer = generate_pdf(per_chart_texts, combo_bullets)
                        st.download_button(label="Download Overall content (PDF)", data=pdf_buffer,
                                           file_name="chart_insights_report.pdf", mime="application/pdf",
                                             key="analyze_download_all")
                    except Exception as e:
                        st.error(f"Failed to combine summaries: {e}")
    else:
        st.info("Upload chart images to get started with analysis and Q&A.")

with tab2:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("Previously Analyzed Charts")
    with col2:
        if st.button("Clear History", type="secondary", key="clear_history_btn"):
            st.session_state["history"] = []
            if "analyze_uploader" in st.session_state:
                del st.session_state["analyze_uploader"]
            st.rerun()

    if not st.session_state["history"]:
        st.info("No charts analyzed yet. Upload charts in the Analyze tab first.")
    else:
        # de-dup by filename (keep last)
        seen = {}
        for item in reversed(st.session_state["history"]):
            if item["filename"] not in seen: seen[item["filename"]] = item
        dedup = list(reversed(list(seen.values())))
        st.session_state["history"] = dedup

        for idx, item in enumerate(dedup):
            left, right = st.columns([1.05, 1], vertical_alignment="top")
            with left:
                st.markdown(f"**{item['filename']}**")
                st.image(item["image"], use_container_width=True)
            with right:
                pts = split_points(item["insights"])
                html_points = render_points_html(pts) if pts else f"<div>{item['insights']}</div>"
                
                st.markdown(f"""
                    <div class="card">
                        <div>
                            <span class="chip">History item</span>
                            <span class="chip">{item['filename']}</span>
                        </div>
                        <div style="height:12px;"></div>
                        {html_points}
                    </div>
                """, unsafe_allow_html=True)