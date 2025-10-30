# # # # --- app.py : Chart Summarizer (Groq + Streamlit) ---
# # # import os
# # # import io
# # # import base64
# # # from typing import List, Dict, Any

# # # import streamlit as st
# # # from PIL import Image
# # # from groq import Groq
# # # from dotenv import load_dotenv

# # # # ----------------------------
# # # # Setup & Config
# # # # ----------------------------
# # # load_dotenv()  # optional, loads GROQ_API_KEY from .env if present

# # # st.set_page_config(
# # #     page_title="Chart Summarizer (Groq + Streamlit)",
# # #     page_icon="📊",
# # #     layout="wide",
# # #     initial_sidebar_state="expanded",
# # # )

# # # PRIMARY_TXT = "text-sm text-gray-700"
# # # ACCENT = "#4f46e5"  # Indigo
# # # HELP = "Upload one or more chart IMAGES (PNG/JPG/SVG converted to PNG). The AI will detect chart type and summarize insights."

# # # # Use Groq LLMs:
# # # # - Vision: meta-llama/llama-4-scout-17b-16e-instruct  (fast multimodal)
# # # # - Text:   llama-3.3-70b-versatile                     (for combined/clean summaries)
# # # VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
# # # TEXT_MODEL = "llama-3.3-70b-versatile"

# # # # Init Groq client (expects GROQ_API_KEY in env)
# # # def get_groq() -> Groq:
# # #     api_key = os.getenv("GROQ_DEMO_API_KEY")
# # #     if not api_key:
# # #         st.error("GROQ_DEMO_API_KEY is missing. Set it in your environment or a .env file.")
# # #         st.stop()
# # #     return Groq(api_key=api_key)

# # # client = get_groq()

# # # # ----------------------------
# # # # UI Header
# # # # ----------------------------
# # # st.markdown(
# # #     f"""
# # #     <div style="padding:1rem 0">
# # #       <h1 style="margin:0">📊 Chart Insight Agent</h1>
# # #       <p style="margin:0.25rem 0 0;color:#475569">
# # #         Upload bar/area/box/line charts as images. The agent will read the chart and write a focused summary:
# # #         trends, rankings, outliers, ranges, and key takeaways. Optionally, get an overall cross-chart summary.
# # #       </p>
# # #     </div>
# # #     """,
# # #     unsafe_allow_html=True,
# # # )

# # # with st.sidebar:
# # #     st.subheader("⚙️ Options")
# # #     tone = st.selectbox("Summary tone", ["Crisp bullets", "Short narrative", "Executive brief"], index=0)
# # #     include_limits = st.checkbox("Call out maxima / minima", value=True)
# # #     include_outliers = st.checkbox("Highlight outliers", value=True)
# # #     include_actions = st.checkbox("Add 1–3 actionables", value=True)
# # #     st.markdown("---")
# # #     st.caption("Tip: For best results, upload high-resolution charts with labeled axes/legends.")

# # # # ----------------------------
# # # # Helpers
# # # # ----------------------------
# # # def file_to_base64(file_bytes: bytes, mime: str = "image/png") -> str:
# # #     """Return a data URI for Groq vision input."""
# # #     b64 = base64.b64encode(file_bytes).decode("utf-8")
# # #     return f"data:{mime};base64,{b64}"

# # # VISION_SYSTEM = """You are a data visualization analyst.
# # # Given an image of a chart, you must:
# # # 1) Detect chart type (bar, area, box, line, pie, etc.).
# # # 2) Read labels (axes, legend, categories, units) if visible.
# # # 3) Summarize key insights (trends, rankings, outliers, ranges, comparisons).
# # # 4) Quantify approximately when possible (e.g., “~30% higher”) but avoid fabricating exact numbers if not legible.
# # # 5) Be concise, accurate, and avoid hallucinating values that are not visually supported."""

# # # def vision_user_prompt(user_opts: Dict[str, Any]) -> List[Dict[str, Any]]:
# # #     ask_style = {
# # #         "Crisp bullets": "Return 5–8 crisp bullets.",
# # #         "Short narrative": "Return a short paragraph (4–6 sentences).",
# # #         "Executive brief": "Return an executive brief with 3 bullets: Insight, Risk/Issue, Action.",
# # #     }[user_opts["tone"]]
# # #     extras = []
# # #     if user_opts["include_limits"]:
# # #         extras.append("Call out maxima/minima.")
# # #     if user_opts["include_outliers"]:
# # #         extras.append("Highlight outliers or anomalies.")
# # #     if user_opts["include_actions"]:
# # #         extras.append("End with 1–3 actionable recommendations.")
# # #     extra_text = " ".join(extras)

# # #     text = f"""Analyze this chart image following the rules. {ask_style} {extra_text}
# # # If values are unclear, say “not legible” rather than guessing."""
# # #     return [{"type": "text", "text": text}]

# # # def run_vision_on_image(img_bytes: bytes, mime: str, user_opts: Dict[str, Any]) -> str:
# # #     """Send an image to the Groq vision model and get a textual summary."""
# # #     content = vision_user_prompt(user_opts)
# # #     content.append({"type": "image_url", "image_url": {"url": file_to_base64(img_bytes, mime=mime)}})

# # #     resp = client.chat.completions.create(
# # #         model=VISION_MODEL,
# # #         messages=[
# # #             {"role": "system", "content": VISION_SYSTEM},
# # #             {"role": "user", "content": content},
# # #         ],
# # #         max_completion_tokens=800,
# # #         temperature=0.2,
# # #         stream=False,
# # #     )
# # #     return resp.choices[0].message.content

# # # def combine_summaries(per_chart: List[str]) -> str:
# # #     """Use a text-only model to combine multiple chart summaries into one overview."""
# # #     joined = "\n\n---\n\n".join([f"Chart {i+1}:\n{txt}" for i, txt in enumerate(per_chart)])
# # #     system = "You are a senior data analyst. Write a brief, synthesis summary across multiple charts."
# # #     user = f"""Here are the per-chart summaries:

# # # {joined}

# # # Write a unified overview (5–8 bullets) covering cross-chart patterns, conflicts, and priorities."""
# # #     resp = client.chat.completions.create(
# # #         model=TEXT_MODEL,
# # #         messages=[
# # #             {"role": "system", "content": system},
# # #             {"role": "user", "content": user},
# # #         ],
# # #         temperature=0.2,
# # #         max_completion_tokens=600,
# # #         stream=False,
# # #     )
# # #     return resp.choices[0].message.content

# # # def detect_mime(name: str) -> str:
# # #     name = (name or "").lower()
# # #     if name.endswith(".jpg") or name.endswith(".jpeg"):
# # #         return "image/jpeg"
# # #     if name.endswith(".webp"):
# # #         return "image/webp"
# # #     if name.endswith(".svg"):
# # #         # Convert SVG to PNG in-memory if desired; for now we send as image/svg+xml
# # #         return "image/svg+xml"
# # #     return "image/png"

# # # # ----------------------------
# # # # Main UI
# # # # ----------------------------
# # # st.markdown("### 1) Upload chart images")
# # # uploads = st.file_uploader(
# # #     "Drop images (PNG/JPG/SVG) — multiple files allowed",
# # #     type=["png", "jpg", "jpeg", "webp", "svg"],
# # #     accept_multiple_files=True,
# # #     help=HELP,
# # # )

# # # if uploads:
# # #     user_opts = {
# # #         "tone": tone,
# # #         "include_limits": include_limits,
# # #         "include_outliers": include_outliers,
# # #         "include_actions": include_actions,
# # #     }

# # #     st.markdown("### 2) Preview & analyze")
# # #     cols = st.columns(3)

# # #     per_chart_summaries: List[str] = []

# # #     for idx, up in enumerate(uploads):
# # #         mime = detect_mime(up.name)
# # #         img_bytes = up.read()

# # #         # Preview
# # #         try:
# # #             img = Image.open(io.BytesIO(img_bytes))
# # #             with cols[idx % 3]:
# # #                 st.image(img, caption=f"{up.name}", use_container_width=True)
# # #         except Exception:
# # #             with cols[idx % 3]:
# # #                 st.write(f"📄 {up.name} (preview unavailable)")

# # #         with st.spinner(f"Analyzing {up.name} …"):
# # #             try:
# # #                 summary = run_vision_on_image(img_bytes, mime=mime, user_opts=user_opts)
# # #             except Exception as e:
# # #                 summary = f"⚠️ Error analyzing {up.name}: {e}"
# # #         st.markdown(f"**Summary — {up.name}**")
# # #         st.write(summary)
# # #         st.markdown("---")
# # #         per_chart_summaries.append(summary)

# # #     if len(per_chart_summaries) >= 2:
# # #         st.markdown("### 3) Overall combined summary (all charts)")
# # #         with st.spinner("Synthesizing cross-chart insights …"):
# # #             try:
# # #                 combo = combine_summaries(per_chart_summaries)
# # #                 st.success("Combined summary ready:")
# # #                 st.write(combo)
# # #             except Exception as e:
# # #                 st.error(f"Failed to combine summaries: {e}")

# # # else:
# # #     st.info("Upload 1+ chart images to begin.")

# # # # ----------------------------
# # # # Footer
# # # # ----------------------------
# # # st.markdown(
# # #     f"""
# # #     <div style="margin-top:1rem; font-size:0.9rem; color:#64748b">
# # #       Built with <b>Streamlit</b> and <b>Groq</b> vision models.
# # #     </div>
# # #     """,
# # #     unsafe_allow_html=True,
# # # )

# # # app_insights.py — Chart Insights Only (Groq + Streamlit)


# # #2nd code only user 
# # import os, io, base64
# # from typing import List
# # import streamlit as st
# # from PIL import Image
# # from groq import Groq
# # from dotenv import load_dotenv

# # load_dotenv()

# # st.set_page_config(page_title="Chart Insights (Groq + Streamlit)", page_icon="📊", layout="wide")

# # VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
# # TEXT_MODEL   = "llama-3.3-70b-versatile"

# # def get_groq() -> Groq:
# #     api_key = os.getenv("GROQ_DEMO_API_KEY")
# #     if not api_key:
# #         st.error("GROQ_DEMO_API_KEY is missing. Put it in your environment or a .env file.")
# #         st.stop()
# #     return Groq(api_key=api_key)

# # client = get_groq()

# # def file_to_base64(file_bytes: bytes, mime: str = "image/png") -> str:
# #     b64 = base64.b64encode(file_bytes).decode("utf-8")
# #     return f"data:{mime};base64,{b64}"

# # INSIGHTS_SYSTEM = """
# # You are a senior data analyst.
# # Your task: produce ONLY decision-focused insights from a chart image.

# # Strict formatting and content rules:
# # - Provide 3–5 concise, decision-focused insights in English.
# # - Go straight to insights (trends, contrasts, patterns, inflection points, takeaways).
# # - Do NOT describe the chart type, axes, legends, or methodology unless essential to the insight.
# # - No sections such as “Max/Min/Outliers”.
# # - Each insight must be a self-contained, meaningful sentence that focuses on business impact or strategic relevance.
# # - Format the output as plain text bullet points using a single hyphen (-) followed by a space for each line.
# #   Example:
# #   - Sales grew sharply in Q4 compared to earlier quarters.
# #   - Customer churn declined steadily across all regions.
# # - Do NOT use any Markdown syntax (no *, **, #, >, `, or HTML tags).
# # - Do NOT include numbering, emojis, or extra symbols.
# # - Avoid generic statements (e.g., “data shows an increase”)—focus on interpretation.
# # - Use approximate numbers ONLY if clearly legible; otherwise use comparative terms (“~higher”, “slight decline”).
# # - Never fabricate or assume numeric values that are unreadable.
# # - Output must be plain text only: just bullet points, each starting on a new line.
# # """



# # def vision_prompt(style: str) -> list:
# #     style_map = {
# #         "Key insights (5 bullets)": "Return exactly 5 concise bullet points, each a single sentence.",
# #         "Executive summary (3 bullets)": "Return exactly 3 tight bullets focused on so-what for decision-makers.",
# #         "One-liner takeaway": "Return exactly one sentence capturing the single most important takeaway."
# #     }
# #     return [{
# #         "type": "text",
# #         "text": f"""Analyze this chart image and produce {style_map[style]}
# # Do NOT explain the chart type or structure. Deliver insights only."""
# #     }]

# # def run_vision(img_bytes: bytes, mime: str, style: str) -> str:
# #     content = vision_prompt(style)
# #     content.append({"type": "image_url", "image_url": {"url": file_to_base64(img_bytes, mime=mime)}})
# #     resp = client.chat.completions.create(
# #         model=VISION_MODEL,
# #         messages=[
# #             {"role": "system", "content": INSIGHTS_SYSTEM},
# #             {"role": "user", "content": content},
# #         ],
# #         temperature=0.2,
# #         max_completion_tokens=600,
# #         stream=False,
# #     )
# #     return resp.choices[0].message.content

# # def combine_summaries(per_chart: List[str]) -> str:
# #     joined = "\n\n---\n\n".join([f"Chart {i+1}:\n{txt}" for i, txt in enumerate(per_chart)])
# #     system = "You are a senior analyst. Synthesize multiple chart insights into a single priority-focused brief."
# #     user = f"""Combine these per-chart insights into a unified set of priorities (4–6 bullets), avoiding repetition:

# # {joined}"""
# #     resp = client.chat.completions.create(
# #         model=TEXT_MODEL,
# #         messages=[{"role": "system", "content": system},{"role": "user", "content": user}],
# #         temperature=0.2,
# #         max_completion_tokens=400,
# #         stream=False,
# #     )
# #     return resp.choices[0].message.content

# # def detect_mime(name: str) -> str:
# #     name = (name or "").lower()
# #     if name.endswith((".jpg",".jpeg")): return "image/jpeg"
# #     if name.endswith(".webp"): return "image/webp"
# #     if name.endswith(".svg"): return "image/svg+xml"
# #     return "image/png"

# # # --- UI ---
# # st.markdown("<h2>📊 Chart Insight Agent — Insights Only</h2>", unsafe_allow_html=True)
# # with st.sidebar:
# #     style = st.selectbox("Insight style", ["Key insights (5 bullets)", "Executive summary (3 bullets)", "One-liner takeaway"])
# #     st.caption("Upload one or many chart images. Output = insights only.")

# # uploads = st.file_uploader(
# #     "Drop chart images (PNG/JPG/WEBP/SVG) — multiple allowed",
# #     type=["png","jpg","jpeg","webp","svg"], accept_multiple_files=True,
# #     help="High-resolution images with visible labels produce better insights."
# # )

# # if uploads:
# #     cols = st.columns(3)
# #     per_chart = []
# #     for i, up in enumerate(uploads):
# #         mime = detect_mime(up.name)
# #         img_bytes = up.read()

# #         # Preview
# #         try:
# #             img = Image.open(io.BytesIO(img_bytes))
# #             with cols[i % 3]:
# #                 st.image(img, caption=up.name, use_container_width=True)
# #         except Exception:
# #             with cols[i % 3]:
# #                 st.write(f"📄 {up.name} (preview unavailable)")

# #         with st.spinner(f"Deriving insights: {up.name}"):
# #             try:
# #                 insights = run_vision(img_bytes, mime, style)
# #             except Exception as e:
# #                 insights = f"⚠️ Could not analyze {up.name}: {e}"
# #         st.markdown(f"**Insights — {up.name}**")
# #         st.write(insights)
# #         st.markdown("---")
# #         per_chart.append(insights)

# #     if len(per_chart) > 1:
# #         st.subheader("Overall priorities (all charts)")
# #         with st.spinner("Synthesizing priorities..."):
# #             try:
# #                 combo = combine_summaries(per_chart)
# #                 st.success("Combined insights:")
# #                 st.write(combo)
# #             except Exception as e:
# #                 st.error(f"Failed to combine: {e}")
# # else:
# #     st.info("Upload chart images to get insights.")

# # app.py — Chart Insights (Groq + Streamlit) with Mode Toggle
# import os, io, base64, json
# from typing import List, Dict, Any
# import streamlit as st
# from PIL import Image
# from groq import Groq
# from dotenv import load_dotenv

# load_dotenv()

# st.set_page_config(page_title="Chart Insights (Groq + Streamlit)", page_icon="📊", layout="wide")

# VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
# TEXT_MODEL   = "llama-3.3-70b-versatile"

# # ----------------------------
# # Groq client
# # ----------------------------
# def get_groq() -> Groq:
#     api_key = os.getenv("GROQ_DEMO_API_KEY")
#     if not api_key:
#         st.error("GROQ_DEMO_API_KEY is missing. Put it in your environment or a .env file.")
#         st.stop()
#     return Groq(api_key=api_key)

# client = get_groq()

# # ----------------------------
# # Helpers
# # ----------------------------
# def file_to_base64(file_bytes: bytes, mime: str = "image/png") -> str:
#     b64 = base64.b64encode(file_bytes).decode("utf-8")
#     return f"data:{mime};base64,{b64}"

# def detect_mime(name: str) -> str:
#     name = (name or "").lower()
#     if name.endswith((".jpg", ".jpeg")): return "image/jpeg"
#     if name.endswith(".webp"): return "image/webp"
#     if name.endswith(".svg"): return "image/svg+xml"
#     return "image/png"

# def normalize_bullets(text_block: str) -> str:
#     """
#     Make sure each non-empty line starts with '- ' and remove funky leading symbols.
#     Ensures consistent rendering regardless of model quirks.
#     """
#     lines = [l.strip() for l in text_block.splitlines() if l.strip()]
#     fixed = []
#     for l in lines:
#         # strip any leading bullet characters and re-add "- "
#         l = l.lstrip("•-*–—»· ").strip()
#         if not l.startswith("- "):
#             l = "- " + l
#         fixed.append(l)
#     # If the model returned a single paragraph, split by sentence as a fallback
#     if not fixed:
#         fixed = ["- " + text_block.strip()]
#     return "\n".join(fixed)

# def render_user_bullets(title: str, bullets_text: str):
#     st.markdown(f"**{title}**")
#     st.markdown(normalize_bullets(bullets_text))

# def render_dev_card(name: str, img, info: Dict[str, Any]):
#     with st.container():
#         if img is not None:
#             st.image(img, caption=name, use_container_width=True)
#         st.markdown(f"**Insights — {name}**")
#         # Safe bullets rendered by us from JSON list
#         for i in info.get("insights", [])[:6]:
#             st.markdown(normalize_bullets(i))
#         with st.expander("ℹ️ Chart metadata (developer)"):
#             st.json({
#                 "chart_type": info.get("chart_type"),
#                 "x_axis": info.get("x_axis"),
#                 "y_axis": info.get("y_axis"),
#                 "legible": info.get("legible"),
#                 "notables": info.get("notables"),
#             })

# # ----------------------------
# # Prompts
# # ----------------------------
# USER_SYSTEM = """
# You are a senior data analyst.
# Produce ONLY decision-focused insights that help executives act.

# Rules:
# - Provide 3–5 concise insights in English.
# - Go straight to business meaning (trends, contrasts, inflection points, priorities).
# - Do NOT describe chart type/axes/legend/method unless essential to the insight.
# - No “Max/Min/Outliers” sections.
# - Output as plain text bullet points using a single hyphen and a space for each line, e.g.:
#   - Growth accelerated in Q4 led by Product B.
# - No Markdown symbols (other than the leading '- '), no HTML, no numbering, no emojis.
# - Use approximate numbers only if clearly legible; never fabricate values.
# """

# DEV_SYSTEM = """
# You are a data visualization analyst returning structured outputs for developers.

# Return ONLY a valid JSON object with this exact shape:
# {
#   "chart_type": "<bar|line|area|box|pie|other|null>",
#   "x_axis": {"label": "<string|null>", "units": "<string|null>"},
#   "y_axis": {"label": "<string|null>", "units": "<string|null>"},
#   "legible": true/false,
#   "insights": ["...", "...", "..."],
#   "notables": {
#     "max_item": "<category or null>",
#     "min_item": "<category or null>",
#     "outliers": ["...", "..."]
#   }
# }

# Rules:
# - If labels/units aren’t readable, use null and set "legible": false.
# - Do NOT include keys beyond the schema.
# - No HTML, Markdown, emojis, or numbering inside strings.
# - Insights must be meaningful (business impact), not generic.
# - Never invent precise values; use qualitative terms if unclear.
# - Return compact JSON on a single line.
# """

# # ----------------------------
# # LLM runners
# # ----------------------------
# def run_vision_user(img_bytes: bytes, mime: str, style: str) -> str:
#     style_map = {
#         "Key insights (5 bullets)": "Return exactly 5 bullets.",
#         "Executive summary (3 bullets)": "Return exactly 3 bullets.",
#         "One-liner takeaway": "Return exactly 1 bullet."
#     }
#     content = [
#         {"type": "text",
#          "text": f"Analyze this chart image and {style_map[style]} Follow the output rules exactly."},
#         {"type": "image_url", "image_url": {"url": file_to_base64(img_bytes, mime=mime)}}
#     ]
#     resp = client.chat.completions.create(
#         model=VISION_MODEL,
#         messages=[
#             {"role": "system", "content": USER_SYSTEM},
#             {"role": "user", "content": content},
#         ],
#         temperature=0.2,
#         max_completion_tokens=600,
#         stream=False,
#     )
#     return resp.choices[0].message.content.strip()

# def run_vision_dev(img_bytes: bytes, mime: str) -> Dict[str, Any]:
#     content = [
#         {"type": "text", "text": "Analyze this chart image and return JSON exactly per the schema."},
#         {"type": "image_url", "image_url": {"url": file_to_base64(img_bytes, mime=mime)}}
#     ]
#     resp = client.chat.completions.create(
#         model=VISION_MODEL,
#         messages=[
#             {"role": "system", "content": DEV_SYSTEM},
#             {"role": "user", "content": content},
#         ],
#         temperature=0.2,
#         max_completion_tokens=800,
#         stream=False,
#         response_format={"type": "json_object"},
#     )
#     raw = resp.choices[0].message.content.strip()
#     try:
#         data = json.loads(raw)
#     except Exception:
#         data = {
#             "chart_type": None,
#             "x_axis": {"label": None, "units": None},
#             "y_axis": {"label": None, "units": None},
#             "legible": False,
#             "insights": [raw],
#             "notables": {"max_item": None, "min_item": None, "outliers": []}
#         }
#     # basic sanitation of insights strings
#     clean_insights = []
#     for s in data.get("insights", []):
#         if isinstance(s, str) and s.strip():
#             clean_insights.append(s.strip())
#     data["insights"] = clean_insights[:6]
#     return data

# def combine_summaries(per_chart: List[str]) -> str:
#     joined = "\n\n---\n\n".join([f"Chart {i+1}:\n{txt}" for i, txt in enumerate(per_chart)])
#     system = "You are a senior analyst. Synthesize multiple chart insights into a single priority-focused brief."
#     user = f"""Combine these per-chart insights into a unified set of priorities (4–6 bullets), avoiding repetition:

# {joined}"""
#     resp = client.chat.completions.create(
#         model=TEXT_MODEL,
#         messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
#         temperature=0.2,
#         max_completion_tokens=400,
#         stream=False,
#     )
#     return resp.choices[0].message.content.strip()

# # ----------------------------
# # UI
# # ----------------------------
# st.markdown("<h2>📊 Chart Insight Agent</h2>", unsafe_allow_html=True)

# with st.sidebar:
#     st.subheader("⚙️ Options")
#     mode = st.radio("Mode", ["User (Executive)", "Developer (Detailed)"], index=0)
#     style = st.selectbox("Insight style (User mode)", [
#         "Key insights (5 bullets)",
#         "Executive summary (3 bullets)",
#         "One-liner takeaway"
#     ], index=0)
#     st.caption("User mode: only the overall summary. Developer mode: per-chart details + combined.")

# uploads = st.file_uploader(
#     "Drop chart images (PNG/JPG/WEBP/SVG) — multiple allowed",
#     type=["png", "jpg", "jpeg", "webp", "svg"],
#     accept_multiple_files=True,
#     help="High-resolution images with visible labels produce better insights."
# )

# if uploads:
#     cols = st.columns(3)
#     per_chart_texts: List[str] = []      # for User mode overall
#     per_chart_dev_texts: List[str] = []  # for Dev mode overall (from developer insights)

#     for i, up in enumerate(uploads):
#         mime = detect_mime(up.name)
#         img_bytes = up.read()

#         # Try preview
#         try:
#             img = Image.open(io.BytesIO(img_bytes))
#         except Exception:
#             img = None

#         with st.spinner(f"Analyzing: {up.name}"):
#             if mode == "User (Executive)":
#                 # Collect per-chart bullets but don't show them individually
#                 text = run_vision_user(img_bytes, mime, style)
#                 per_chart_texts.append(normalize_bullets(text))
#                 # (Optionally preview the image for context)
#                 if img is not None:
#                     with cols[i % 3]:
#                         st.image(img, caption=up.name, use_container_width=True)
#             else:
#                 # Developer: show detailed card per chart
#                 data = run_vision_dev(img_bytes, mime)
#                 if img is not None:
#                     render_dev_card(up.name, img, data)
#                 else:
#                     st.warning(f"Preview unavailable for {up.name}")
#                 st.markdown("---")
#                 # Build a simple text block from dev insights for the overall combiner
#                 dev_text_block = "\n".join([normalize_bullets(x) for x in data.get("insights", [])])
#                 if dev_text_block.strip():
#                     per_chart_dev_texts.append(dev_text_block)

#     # Overall combined section
#     if mode == "User (Executive)":
#         if len(per_chart_texts) >= 1:
#             st.subheader("Overall summary (all charts)")
#             with st.spinner("Synthesizing executive overview..."):
#                 try:
#                     combo = combine_summaries(per_chart_texts)
#                     render_user_bullets("Executive Overview", combo)
#                 except Exception as e:
#                     st.error(f"Failed to combine summaries: {e}")
#     else:
#         if len(per_chart_dev_texts) >= 2:
#             st.subheader("Overall priorities (all charts)")
#             with st.spinner("Synthesizing developer overview..."):
#                 try:
#                     combo = combine_summaries(per_chart_dev_texts)
#                     render_user_bullets("Synthesis", combo)
#                 except Exception as e:
#                     st.error(f"Failed to synthesize: {e}")
# else:
#     st.info("Upload chart images to begin.")

# app.py — Chart Insight Agent (Groq + Streamlit)
# Modes:
#   • Qualitative (Executive): per-image bullet insights + overall summary (no extra format pickers)
#   • Quantitative (Developer): business-perspective text sections (Insights, Key numbers (approx), Notables) + overall synthesis
# Theme:
#   • Sidebar toggle: Light / Dark (all text styled for contrast in both)

import os, io, base64, re
from typing import List
import streamlit as st
from PIL import Image
from groq import Groq
from dotenv import load_dotenv

# ----------------------------
# Basic setup
# ----------------------------
load_dotenv()
st.set_page_config(page_title="Chart Insights (Groq + Streamlit)", page_icon="📊", layout="wide")

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
TEXT_MODEL   = "llama-3.3-70b-versatile"

THUMB_WIDTH = 240
GRID_COLS   = 4

def get_groq() -> Groq:
    api_key = os.getenv("GROQ_DEMO_API_KEY")
    if not api_key:
        st.error("GROQ_DEMO_API_KEY is missing. Put it in your environment or a .env file.")
        st.stop()
    return Groq(api_key=api_key)

client = get_groq()

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
- Provide 4–6 concise bullets; each must start with "- " and be one sentence.
- Focus on business meaning: trends, contrasts, inflection points, priorities, implications.
- Do NOT describe chart mechanics (type, axes, legend) unless essential to the insight.
- Avoid generic remarks and sections like “Max/Min/Outliers”.
- Use approximate numbers ONLY if clearly legible; never fabricate values.
- No HTML, no emojis, no numbering beyond the leading "- ".
- Output must be plain text only.
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
- <3–6 concise, business-focused bullets. Each line starts with '- ' and is one sentence>

Key numbers (approx):
- <bullets like: '- Metric: ~value unit'> Use only if values are clearly legible. Otherwise skip this section.

Notables:
- <optional bullets for peaks, troughs, outliers, gaps, or segment contrasts. Each line starts with '- '>

Rules:
- Prioritize what helps decisions on growth/revenue, risk/variability, and efficiency/cost.
- No HTML, no emojis, no numbering beyond the leading '- '.
- Never invent precise values; use qualitative phrasing if unclear.
- Keep it compact and readable.
"""

def quant_user_prompt() -> list:
    return [{
        "type": "text",
        "text": ("Analyze this chart and produce the three sections as specified, text only. "
                 "If a section does not apply, omit it. Keep a business perspective.")
    }]

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

# ----------------------------
# UI
# ----------------------------
st.markdown("<h2>📊 Chart Insight Agent</h2>", unsafe_allow_html=True)

with st.sidebar:
    st.subheader("⚙️ Mode & Theme")
    mode = st.radio("Mode", ["Qualitative (Executive)", "Quantitative (Developer)"], index=0)
    theme_choice = st.radio("Theme", ["Light", "Dark"], index=0)
apply_theme(theme_choice)

uploads = st.file_uploader(
    "Drop chart images (PNG/JPG/WEBP/SVG) — multiple allowed",
    type=["png","jpg","jpeg","webp","svg"],
    accept_multiple_files=True,
    help="High-resolution charts with visible labels produce better insights."
)

if uploads:
    cols = st.columns(GRID_COLS)
    per_chart_texts: List[str] = []

    for i, up in enumerate(uploads):
        mime = detect_mime(up.name)
        img_bytes = up.read()

        # Thumbnail preview
        try:
            img = Image.open(io.BytesIO(img_bytes))
            with cols[i % GRID_COLS]:
                st.image(img, caption=up.name, width=THUMB_WIDTH)
        except Exception:
            with cols[i % GRID_COLS]:
                st.write(f"📄 {up.name} (preview unavailable)")

        with st.spinner(f"Analyzing: {up.name}"):
            try:
                if mode == "Qualitative (Executive)":
                    raw = run_qualitative(img_bytes, mime)
                    bullets = normalize_bullets_minmax(raw, min_n=4, max_n=6)
                    st.markdown(f"**Insights — {up.name}**")
                    st.markdown(bullets)
                    st.markdown("---")
                    per_chart_texts.append(bullets)
                else:
                    text = run_quantitative(img_bytes, mime)
                    st.markdown(f"**Details — {up.name}**")
                    st.markdown(text)
                    st.markdown("---")
                    per_chart_texts.append(text)
            except Exception as e:
                st.error(f"Error analyzing {up.name}: {e}")

    # Overall synthesis
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
            except Exception as e:
                st.error(f"Failed to combine summaries: {e}")
else:
    st.info("Upload chart images to begin.")
