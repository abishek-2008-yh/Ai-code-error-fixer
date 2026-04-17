from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import ast
import re
import os
import subprocess
import tempfile
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI(title="AI Code Auto Fixer Core")

# --- DATA MODELS ---
class CodePayload(BaseModel):
    source_code: str
    language: str      
    api_key: str = ""

class ChatPayload(BaseModel):
    user_message: str
    original_code: str
    fixed_code: str
    api_key: str = ""

# --- CORE LOGIC ENGINES (Python Only) ---
def check_syntax(code_string):
    try:
        ast.parse(code_string)
        return True, "SYS.AST // SYNTAX VERIFIED.", None
    except SyntaxError as e:
        return False, f"SYS.AST // FATAL FRACTURE AT LINE {e.lineno} - {e.msg.upper()}", e.lineno
    except Exception as e:
        return False, f"SYS.AST // UNKNOWN ANOMALY - {str(e).upper()}", None

def check_quality(code_string):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
        temp_file.write(code_string)
        temp_file_path = temp_file.name
    try:
        result = subprocess.run(['flake8', temp_file_path], capture_output=True, text=True)
        if not result.stdout.strip():
            return True, "SYS.FLAKE8 // PEP-8 PROTOCOL COMPLIANT."
        else:
            return False, result.stdout.replace(temp_file_path, "LINE ")
    except Exception:
        return False, "SYS.FLAKE8 // NODE OFFLINE."
    finally:
        os.remove(temp_file_path)

def parse_ai_response(response_text):
    parts = response_text.split("### EXPLANATION")
    if len(parts) == 2:
        code_part = parts[0].replace("### FIXED CODE", "").strip()
        code_part = re.sub(r"^```[a-zA-Z]*\n|^```\n|\n```$", "", code_part, flags=re.MULTILINE).strip()
        explanation_part = parts[1].strip()
        return code_part, explanation_part
    return response_text, "DATA CORRUPTION IN AI RESPONSE PARSING."

# --- API ENDPOINTS ---
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/fix_code")
async def process_code(payload: CodePayload):
    source_code = payload.source_code
    language = payload.language 
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise HTTPException(status_code=401, detail="UPLINK OFFLINE: Groq API Key required in .env file.")

    diagnostics_msg = ""
    error_context = ""
    error_line_number = None

    if language.lower() == "python":
        is_valid, syntax_result, error_line_number = check_syntax(source_code)
        if not is_valid:
            error_context = f"AST Crash: {syntax_result}"
            diagnostics_msg = syntax_result
        else:
            is_clean, quality_result = check_quality(source_code)
            if not is_clean:
                error_context = f"Flake8 Style warnings:\n{quality_result}"
                diagnostics_msg = "SYS.FLAKE8 // STYLE WARNINGS DETECTED."
            else:
                error_context = "No errors detected. Optimize and add comments."
                diagnostics_msg = "SYS.CORE // MATRIX OPTIMIZED."
    else:
        error_context = f"Analyze this {language} code for syntax errors, bugs, and optimization opportunities."
        diagnostics_msg = f"SYS.LLM // DEEP SCANNING {language.upper()} PAYLOAD..."

    try:
        client = Groq(api_key=api_key)
        prompt = f"""
        You are an elite {language} coding assistant operating in a secure environment.
        Context: {error_context}
        
        Broken Payload:
        ```{language.lower()}
        {source_code}
        ```
        Format your response EXACTLY like this:
        ### FIXED CODE
        [Corrected {language} code here]
        ### EXPLANATION
        [Brief, technical explanation of the fix]
        """
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant", 
        )
        ai_response = chat_completion.choices[0].message.content
        fixed_code, explanation = parse_ai_response(ai_response)
        
        return {
            "success": True,
            "original_code": source_code,
            "fixed_code": fixed_code,
            "explanation": explanation,
            "error_line": error_line_number,
            "diagnostics": diagnostics_msg
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API BREACH: {str(e).upper()}")

@app.post("/api/chat")
async def chat_with_ai(payload: ChatPayload):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=401, detail="UPLINK OFFLINE: Groq API Key required.")

    try:
        client = Groq(api_key=api_key)
        prompt = f"""
        You are an elite AI coding tutor. We are discussing a piece of code you just fixed.
        Original Broken Code:
        ```
        {payload.original_code}
        ```
        Fixed Code:
        ```
        {payload.fixed_code}
        ```
        The user asks: "{payload.user_message}"
        Respond clearly, technically, and concisely. Keep it under 4 sentences.
        """
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant", 
        )
        return {"response": chat_completion.choices[0].message.content}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"COMMUNICATION FAILURE: {str(e).upper()}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
