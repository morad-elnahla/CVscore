import os
import fitz  # PyMuPDF
import json
import re
from groq import Groq
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

app = FastAPI()

# ===============================
# الـ API Key هنا — مش بيتعرضش للـ user
# ===============================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# ===============================
# 1. اسحب النص من الـ PDF
# ===============================
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text.strip()


# ===============================
# 2. الـ Prompt
# ===============================
def build_prompt(cv_text: str, job_title: str) -> str:
    return f"""You are a senior technical recruiter and career coach with 15+ years of experience hiring for top tech companies.

Your task is to critically evaluate the CV below for the role of: "{job_title}"

Be STRICT, HONEST, and SPECIFIC. Do not be generic. Reference actual content from the CV.

CV Content:
\"\"\"
{cv_text}
\"\"\"

Evaluate across these dimensions:
1. Relevance to the target role
2. Technical skills & keywords match
3. Experience quality & impact (use of numbers/metrics)
4. Education & certifications
5. Project quality & real-world applicability
6. CV structure, clarity, and ATS-friendliness

Return ONLY a valid JSON object with NO extra text, NO markdown, NO explanation:
{{
  "score": <integer 0-100, be realistic not generous>,
  "relevance_score": <integer 0-100>,
  "keywords_score": <integer 0-100>,
  "structure_score": <integer 0-100>,
  "summary": "<3 sentences: overall assessment, biggest strength, biggest gap — be specific>",
  "strengths": [
    "<specific strength with reference to CV content>",
    "<specific strength with reference to CV content>",
    "<specific strength with reference to CV content>"
  ],
  "weaknesses": [
    "<specific weakness with actionable context>",
    "<specific weakness with actionable context>",
    "<specific weakness with actionable context>"
  ],
  "suggestions": [
    "<concrete, specific improvement — not generic advice>",
    "<concrete, specific improvement — not generic advice>",
    "<concrete, specific improvement — not generic advice>"
  ],
  "missing_keywords": ["<keyword>", "<keyword>", "<keyword>", "<keyword>", "<keyword>"],
  "verdict": "<Excellent | Good | Needs Work | Poor>"
}}"""


# ===============================
# 3. بعت لـ Groq وارجع النتيجة
# ===============================
def analyze_cv(cv_text: str, job_title: str) -> dict:
    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a strict, expert CV evaluator. You always respond with valid JSON only. No markdown, no extra text."
            },
            {
                "role": "user",
                "content": build_prompt(cv_text, job_title)
            }
        ],
        temperature=0,
        seed=42,
        max_tokens=1500,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


# ===============================
# 4. الـ API Endpoint
# ===============================
@app.post("/analyze")
async def analyze(
    cv_file: UploadFile = File(...),
    job_title: str = Form(...),
):
    try:
        pdf_bytes = await cv_file.read()
        cv_text = extract_text_from_pdf(pdf_bytes)

        if not cv_text:
            return JSONResponse({"error": "Could not extract text from PDF"}, status_code=400)

        result = analyze_cv(cv_text, job_title)
        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ===============================
# 5. الـ Frontend
# ===============================
@app.get("/", response_class=HTMLResponse)
async def home():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)