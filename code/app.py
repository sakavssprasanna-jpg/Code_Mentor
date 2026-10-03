import os
import sys
from threading import Thread

# Ensure application directory is in sys.path for local package imports on any deployment platform
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import streamlit as st
import torch
import io
import traceback
import ast
import time
import hashlib
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer

# 1. Set page config first
st.set_page_config(
    page_title="High-Perf Code Mentor AI",
    page_icon="⚡",
    layout="wide",
)

# 2. Inject CSS Theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stTextArea textarea {
        font-family: 'JetBrains Mono', 'Courier New', Courier, monospace !important;
        font-size: 14px !important;
        background-color: #0e1117 !important;
        color: #c9d1d9 !important;
        border: 1px solid #30363d !important;
        border-radius: 6px !important;
        line-height: 1.5 !important;
    }
    
    .app-header {
        margin-bottom: 1.5rem;
        border-bottom: 1px solid #21262d;
        padding-bottom: 1rem;
    }
    
    .app-title {
        font-size: 2rem;
        font-weight: 700;
        color: #58a6ff;
        letter-spacing: -0.5px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .app-subtitle {
        color: #8b949e;
        font-size: 0.95rem;
        margin-top: 0.2rem;
    }
    
    .stButton>button {
        font-family: 'Inter', sans-serif !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border: 1px solid #30363d !important;
        background-color: #21262d !important;
        color: #c9d1d9 !important;
        height: 45px !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .stButton>button:hover {
        border-color: #8b949e !important;
        background-color: #30363d !important;
        color: #f0f6fc !important;
    }
    
    /* Highlight the run button */
    div[data-testid="column"]:nth-of-type(1) .stButton>button {
        background-color: #238636 !important;
        color: #ffffff !important;
        border: 1px solid #2ea44f !important;
    }
    
    div[data-testid="column"]:nth-of-type(1) .stButton>button:hover {
        background-color: #2ea44f !important;
        border-color: #3fb950 !important;
    }
    
    .output-box {
        background-color: #0d1117;
        padding: 1rem;
        border-radius: 6px;
        border-left: 4px solid #2ea44f;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        white-space: pre-wrap;
        color: #c9d1d9;
        border-top: 1px solid #30363d;
        border-right: 1px solid #30363d;
        border-bottom: 1px solid #30363d;
        margin-top: 0.5rem;
    }
    
    .error-box {
        background-color: #2d191e;
        padding: 1rem;
        border-radius: 6px;
        border-left: 4px solid #f85149;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        white-space: pre-wrap;
        color: #ff7b72;
        border-top: 1px solid #482329;
        border-right: 1px solid #482329;
        border-bottom: 1px solid #482329;
        margin-top: 0.5rem;
    }
    
    .fix-box {
        background-color: #13231b;
        padding: 1.2rem;
        border-radius: 6px;
        border-left: 4px solid #3fb950;
        color: #c9d1d9;
        font-size: 14px;
        line-height: 1.6;
        border-top: 1px solid #213d2f;
        border-right: 1px solid #213d2f;
        border-bottom: 1px solid #213d2f;
        margin-top: 0.5rem;
    }
    
    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
    }
    
    .badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    
    .badge-blue { background-color: #122e51; color: #58a6ff; border: 1px solid #21518f; }
    .badge-green { background-color: #132e1b; color: #56d364; border: 1px solid #21572d; }
    .badge-purple { background-color: #281a38; color: #bc8cff; border: 1px solid #4c326b; }
    .badge-gray { background-color: #21262d; color: #8b949e; border: 1px solid #30363d; }
    .badge-orange { background-color: #2b1f13; color: #f0883e; border: 1px solid #4d3822; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
    <div class="app-title">⚡ Code Mentor AI</div>
    <div class="app-subtitle">High-Performance Hybrid Static-AI Coding Assistant</div>
</div>
""", unsafe_allow_html=True)

# 3. Model Configuration & Selection in Sidebar
MODELS = {
    "Qwen 2.5 Coder 0.5B (Fastest - CPU Recommended)": "Qwen/Qwen2.5-Coder-0.5B-Instruct",
    "DeepSeek Coder 1.3B (Default - Medium)": "deepseek-ai/deepseek-coder-1.3b-instruct",
    "Qwen 2.5 Coder 1.5B (High Accuracy)": "Qwen/Qwen2.5-Coder-1.5B-Instruct"
}

st.sidebar.header("⚙️ AI Backend Settings")
selected_model_label = st.sidebar.selectbox(
    "AI Model",
    options=list(MODELS.keys()),
    index=0 # Default to Qwen 0.5B since CPU only is available, runs in seconds!
)
MODEL_NAME = MODELS[selected_model_label]

mode_toggle = st.sidebar.radio("Optimization Mode", ["Fast Mode (Default)", "Detailed Mode"])
is_fast_mode = "Fast" in mode_toggle

# Adjust parameters based on mode
MAX_TOKENS = 150 if is_fast_mode else 500
TEMPERATURE = 0.0 if is_fast_mode else 0.3 # 0.0 is deterministic and faster

# Cached Model & Tokenizer Loader
@st.cache_resource(show_spinner=False)
def get_model_and_tokenizer(model_name: str):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        
    if device == "cuda":
        torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    else:
        torch_dtype = torch.float32
        
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            attn_implementation="sdpa"
        ).to(device)
    except Exception:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True
        ).to(device)
        
    model.eval()
    return model, tokenizer, device

# Handle model loading with UI feedback only when a new model loads
model, tokenizer, device = None, None, "cpu"
static_only_mode = False

try:
    if "loaded_models" not in st.session_state:
        st.session_state.loaded_models = set()
        
    if MODEL_NAME not in st.session_state.loaded_models:
        with st.sidebar:
            with st.spinner(f"Loading {MODEL_NAME.split('/')[-1]}..."):
                model, tokenizer, device = get_model_and_tokenizer(MODEL_NAME)
                st.session_state.loaded_models.add(MODEL_NAME)
    else:
        model, tokenizer, device = get_model_and_tokenizer(MODEL_NAME)
except Exception as e:
    st.sidebar.error(f"Failed to load local model: {str(e)}")
    st.sidebar.warning("Falling back to Static Analysis Mode. AI features will be disabled.")
    static_only_mode = True

# 4. State Initializations
if "response_cache" not in st.session_state:
    st.session_state.response_cache = {}
if "last_action" not in st.session_state:
    st.session_state.last_action = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

# Set default code if code_input is not in session_state yet
if "code_input" not in st.session_state:
    st.session_state.code_input = "# Paste your Python code here...\n\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n"
if "program_input" not in st.session_state:
    st.session_state.program_input = ""

if "visualizer_active" not in st.session_state:
    st.session_state.visualizer_active = False
if "visualizer_snapshots" not in st.session_state:
    st.session_state.visualizer_snapshots = []
if "visualizer_source_lines" not in st.session_state:
    st.session_state.visualizer_source_lines = []
if "visualizer_current_step" not in st.session_state:
    st.session_state.visualizer_current_step = 1
if "visualizer_is_playing" not in st.session_state:
    st.session_state.visualizer_is_playing = False
if "visualizer_speed" not in st.session_state:
    st.session_state.visualizer_speed = 1.0
if "visualizer_exec_time" not in st.session_state:
    st.session_state.visualizer_exec_time = 0.0

# Helper to generate cache keys
def get_cache_key(code: str, action: str, mode: str, model_name: str):
    combined = f"{code}_{action}_{mode}_{model_name}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

# 5. Local Code Execution (Safe and Timeout protected)
def execute_python_code(code: str, user_inputs: str = ""):
    """Executes Python code safely, returns (output, error_message, error_line)"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = sys.stdout = io.StringIO()
    redirected_error = sys.stderr = io.StringIO()
    
    error_msg = None
    error_line = None
    
    input_iterator = iter(user_inputs.splitlines())
    def custom_input(prompt=""):
        if prompt:
            redirected_output.write(str(prompt))
        try:
            return next(input_iterator)
        except StopIteration:
            raise EOFError("EOF when reading a line (no more input provided)")
            
    exec_globals = {"__builtins__": __builtins__, "input": custom_input}
    
    start_time = time.time()
    timeout_seconds = 3.0
    
    def trace_calls(frame, event, arg):
        if time.time() - start_time > timeout_seconds:
            raise TimeoutError(f"Execution exceeded the {timeout_seconds} seconds limit.")
        return trace_calls
        
    sys.settrace(trace_calls)
    try:
        exec(code, exec_globals)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb = traceback.extract_tb(exc_traceback)
        
        if isinstance(e, SyntaxError):
            error_line = e.lineno
        else:
            for frame in reversed(tb):
                if frame.filename == "<string>":
                    error_line = frame.lineno
                    break
        
        error_msg = f"{exc_type.__name__}: {str(e)}"
        
    finally:
        sys.settrace(None)
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
    output = redirected_output.getvalue() + redirected_error.getvalue()
    return output.strip(), error_msg, error_line

# 6. Static Syntax Validation
def validate_syntax(code: str):
    """Statically checks Python code for syntax errors. Returns (is_valid, error_msg, line_no)"""
    try:
        ast.parse(code)
        compile(code, "<string>", "exec")
        return True, None, None
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg}", e.lineno
    except Exception as e:
        return False, f"Error: {str(e)}", None

# 7. AST-based Complexity Analyzer
class ComplexityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.loop_depth = 0
        self.max_loop_depth = 0
        self.sequential_loops = 0
        self.has_recursion = False
        self.has_sorting = False
        self.has_dict_set_lookup = False
        self.has_binary_search = False
        self.has_allocations = False
        self.current_function = None
        self.called_functions = []

    def visit_FunctionDef(self, node):
        old_func = self.current_function
        self.current_function = node.name
        
        # Check recursion
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call):
                if isinstance(subnode.func, ast.Name) and subnode.func.id == node.name:
                    self.has_recursion = True
                    
        self.generic_visit(node)
        self.current_function = old_func

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name == "sorted":
                self.has_sorting = True
            elif func_name in ("list", "dict", "set"):
                self.has_allocations = True
            self.called_functions.append(func_name)
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name == "sort":
                self.has_sorting = True
            elif attr_name in ("append", "insert", "extend", "add", "update", "copy"):
                self.has_allocations = True
            if isinstance(node.func.value, ast.Name):
                self.called_functions.append(f"{node.func.value.id}.{attr_name}")
        self.generic_visit(node)

    def visit_For(self, node):
        self.loop_depth += 1
        if self.loop_depth == 1:
            self.sequential_loops += 1
        self.max_loop_depth = max(self.max_loop_depth, self.loop_depth)
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_While(self, node):
        self.loop_depth += 1
        if self.loop_depth == 1:
            self.sequential_loops += 1
        self.max_loop_depth = max(self.max_loop_depth, self.loop_depth)
        
        # Check binary search updates
        has_division = False
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.BinOp):
                if isinstance(subnode.op, (ast.FloorDiv, ast.Div, ast.RShift)):
                    if isinstance(subnode.right, ast.Constant) and subnode.right.value == 2:
                        has_division = True
                    elif isinstance(subnode.right, ast.Constant) and subnode.right.value == 1 and isinstance(subnode.op, ast.RShift):
                        has_division = True
        if has_division:
            self.has_binary_search = True
            
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_Compare(self, node):
        for op in node.ops:
            if isinstance(op, (ast.In, ast.NotIn)):
                self.has_dict_set_lookup = True
        self.generic_visit(node)

    def visit_Subscript(self, node):
        self.has_dict_set_lookup = True
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self.has_allocations = True
        self.generic_visit(node)

    def visit_DictComp(self, node):
        self.has_allocations = True
        self.generic_visit(node)

    def visit_SetComp(self, node):
        self.has_allocations = True
        self.generic_visit(node)

def analyze_complexity_statically(code: str):
    try:
        tree = ast.parse(code)
    except Exception:
        return None

    visitor = ComplexityVisitor()
    visitor.visit(tree)

    if visitor.has_recursion:
        return None  # Let LLM handle it

    time_complexity = "O(1)"
    space_complexity = "O(1)"
    explanation = ""

    if visitor.has_binary_search:
        if visitor.max_loop_depth == 1:
            time_complexity = "O(log N)"
            space_complexity = "O(1)"
            explanation = "Binary search pattern detected. The search space is repeatedly halved in a loop, running in O(log N) logarithmic time."
            return time_complexity, space_complexity, explanation
        else:
            return None

    if visitor.has_sorting:
        if visitor.max_loop_depth == 0:
            time_complexity = "O(N log N)"
            space_complexity = "O(N)"
            explanation = "Sorting operation detected with no loops. Python's Timsort algorithm dominates execution time with O(N log N) time and O(N) space."
            return time_complexity, space_complexity, explanation
        else:
            return None

    if visitor.max_loop_depth == 0:
        if visitor.has_dict_set_lookup:
            time_complexity = "O(1) average"
            explanation = "No loops detected. Dictionary/set lookup operations run in average constant time O(1)."
        else:
            time_complexity = "O(1)"
            explanation = "No loops or recursion detected. All operations execute sequentially in O(1) constant time."
    elif visitor.max_loop_depth == 1:
        time_complexity = "O(N)"
        if visitor.sequential_loops > 1:
            explanation = f"Detected {visitor.sequential_loops} sequential loops at the same nesting level. Since they execute one after another, the time complexity is O(N)."
        else:
            explanation = "Detected a single loop running N times. The operations inside execute in linear time O(N)."
    elif visitor.max_loop_depth == 2:
        time_complexity = "O(N^2)"
        explanation = "Detected nested loops (2 deep). The inner loop runs N times for each iteration of the outer loop, running in quadratic time O(N^2)."
    else:
        time_complexity = f"O(N^{visitor.max_loop_depth})"
        explanation = f"Detected nested loops ({visitor.max_loop_depth} levels deep). The nested iterations scale as O(N^{visitor.max_loop_depth})."

    if visitor.has_allocations:
        space_complexity = "O(N)"
        explanation += " Space complexity is O(N) due to memory allocations (e.g. list/dictionary comprehension, append, or insertion)."
    else:
        space_complexity = "O(1)"
        explanation += " Space complexity is O(1) auxiliary space as no additional collections are allocated in memory."

    return time_complexity, space_complexity, explanation

# 8. Prompt Generator
def get_instruction_for_mode(action: str, code_length: int, is_fast_mode: bool, error_context: dict = None) -> str:
    """Return an optimized prompt template based on task context."""
    if action == "Explain Code":
        if is_fast_mode:
            return "Summarize the following Python code in 3 short, high-level bullet points. Be extremely concise."
        return "Explain the following Python code in 5-6 clear bullet points."
            
    elif action == "Fix Errors":
        err_msg = error_context.get("message", "Unknown error")
        err_line = error_context.get("line", "Unknown")
        return f"The Python code failed at line {err_line} with error: {err_msg}. Show the corrected code block and briefly explain the fix in 1 sentence."

    elif action == "Analyze Complexity":
        if is_fast_mode:
            return "Identify the Time and Space complexity (Big-O) of this Python code. Output only the complexity notations."
        return "Analyze the Time and Space complexity (Big-O) of the following Python code. Explain in 2 sentences."
        
    elif action == "Optimize Code":
        if is_fast_mode:
            return "Optimize the following Python code. Return the optimized code block and 2 bullet points of changes."
        return "Optimize the following Python code. Provide the optimized code block and explain the performance improvements in 3 bullet points."
        
    return "Analyze the code."

# 9. Streaming Generator
def generate_response_stream(model, tokenizer, device, prompt_text: str, max_tokens: int, temperature: float):
    """Streams token generations using TextIteratorStreamer in a background thread."""
    prompt_text += "\n\nInstructions: Be extremely concise. Return only the required code or bullet points. Avoid any introductory or concluding conversational filler."
    
    messages = [
        {"role": "user", "content": prompt_text}
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    
    do_sample = temperature > 0.0
    generation_kwargs = dict(
        inputs,
        streamer=streamer,
        max_new_tokens=max_tokens,
        temperature=temperature if do_sample else None,
        do_sample=do_sample,
        pad_token_id=tokenizer.eos_token_id,
    )
    
    def run_generation_thread():
        try:
            with torch.inference_mode():
                model.generate(**generation_kwargs)
        except Exception:
            pass

    thread = Thread(target=run_generation_thread)
    thread.start()
    
    for new_text in streamer:
        yield new_text

# 10. Centralized Results Renderer
def render_result(action: str, result: dict):
    st.subheader(f"Result: {action}")
    
    # Render badges
    badges = []
    
    # Model Badge
    if static_only_mode:
        badges.append("<span class='badge badge-gray'>🤖 Static Only</span>")
    else:
        badges.append(f"<span class='badge badge-purple'>🤖 {selected_model_label.split(' ')[0]}</span>")
        
    # Device Badge
    device_name = "CUDA" if not static_only_mode and device == "cuda" else "CPU"
    badges.append(f"<span class='badge badge-gray'>💻 {device_name}</span>")
    
    # Elapsed Time Badge
    if "elapsed" in result:
        badges.append(f"<span class='badge badge-blue'>⏱️ {result['elapsed']:.3f}s</span>")
        
    # Cached status Badge
    if result.get("cached"):
        badges.append("<span class='badge badge-green'>🚀 Cached</span>")
    elif result.get("type") in ("run_code", "static_complexity", "fix_errors_success_static"):
        badges.append("<span class='badge badge-green'>⚡ Instant Analysis</span>")
    else:
        badges.append("<span class='badge badge-gray'>⚡ Real-time</span>")
        
    # Complexity badges
    if result.get("type") == "static_complexity":
        time_c = result.get("time_c", "")
        if "O(1)" in time_c:
            badges.append(f"<span class='badge badge-green'>🎯 Time: {time_c}</span>")
        elif "O(log" in time_c or "O(N)" in time_c:
            badges.append(f"<span class='badge badge-blue'>🎯 Time: {time_c}</span>")
        else:
            badges.append(f"<span class='badge badge-orange'>🎯 Time: {time_c}</span>")
            
        space_c = result.get("space_c", "")
        if "O(1)" in space_c:
            badges.append(f"<span class='badge badge-green'>📦 Space: {space_c}</span>")
        else:
            badges.append(f"<span class='badge badge-orange'>📦 Space: {space_c}</span>")
            
    st.markdown(f"<div class='badge-row'>{' '.join(badges)}</div>", unsafe_allow_html=True)
    
    res_type = result.get("type")
    
    if res_type == "run_code":
        output = result.get("output", "")
        error_msg = result.get("error_msg")
        error_line = result.get("error_line")
        
        if error_msg:
            st.markdown(f"**Error detected at line {error_line}:**")
            lines = st.session_state.code_input.split('\n')
            if error_line and 1 <= error_line <= len(lines):
                err_snippet = lines[error_line - 1]
                st.markdown(f"<div class='error-box'>Line {error_line}: {err_snippet}<br><br>{error_msg}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='error-box'>{error_msg}</div>", unsafe_allow_html=True)
            if output:
                st.markdown(f"**Standard Output:**<div class='output-box'>{output}</div>", unsafe_allow_html=True)
        else:
            if output:
                st.markdown(f"<div class='output-box'>{output}</div>", unsafe_allow_html=True)
            else:
                st.success("Code executed successfully (No output).")
                
    elif res_type == "fix_errors_success":
        st.success(result.get("content", ""))
        
    elif res_type == "fix_errors_failed":
        st.markdown(f"<div class='error-box'><b>Detected:</b> {result.get('error_msg')} at line {result.get('error_line')}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='fix-box'><b>Suggested Fix:</b><br><br>{result.get('explanation')}</div>", unsafe_allow_html=True)
        
    elif res_type == "static_complexity":
        st.markdown(f"### Explanation:\n{result.get('explanation')}")
        
    elif res_type == "markdown":
        st.markdown(result.get("content", ""))
        
    elif res_type == "warning":
        st.warning(result.get("message", ""))
        
    elif res_type == "error":
        st.error(result.get("message", ""))

# 11. Split-screen Layout / Visualizer Layout
if st.session_state.get("visualizer_active", False):
    import importlib
    import visualizer.renderer
    importlib.reload(visualizer.renderer)
    visualizer.renderer.show_visualizer_ui()
    st.stop()

col_editor, col_results = st.columns([1.1, 0.9])

with col_editor:
    st.markdown("### 📝 Code Workspace")
    code_input = st.text_area(
        "Code Input",
        height=320, 
        placeholder="# Paste your Python code here...",
        label_visibility="collapsed",
        key="code_input"
    )
    
    program_input = st.text_area(
        "Program Input (stdin)",
        height=100,
        placeholder="Enter program input here...\nEach value on a new line.",
        key="program_input"
    )
    
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    btn_cols = st.columns(6)
    
    # Set pending actions based on button clicks
    if btn_cols[0].button("▶️ Run", use_container_width=True):
        st.session_state.pending_action = "Run Code"
        st.session_state.last_action = "Run Code"
        
    if btn_cols[1].button("🧠 Explain", use_container_width=True):
        st.session_state.pending_action = "Explain Code"
        st.session_state.last_action = "Explain Code"
        
    if btn_cols[2].button("🛠️ Fix", use_container_width=True):
        st.session_state.pending_action = "Fix Errors"
        st.session_state.last_action = "Fix Errors"
        
    if btn_cols[3].button("⏱️ Complex", use_container_width=True):
        st.session_state.pending_action = "Analyze Complexity"
        st.session_state.last_action = "Analyze Complexity"
        
    if btn_cols[4].button("⚡ Optimize", use_container_width=True):
        st.session_state.pending_action = "Optimize Code"
        st.session_state.last_action = "Optimize Code"

    if btn_cols[5].button("🎬 Visualize", use_container_width=True):
        st.session_state.pending_action = "Visualize Code"
        st.session_state.last_action = "Visualize Code"

# 12. Results Panel (Deferred execution and rendering)
with col_results:
    st.markdown("### 🖥️ Result & Console Output")
    
    if st.session_state.pending_action:
        action = st.session_state.pending_action
        st.session_state.pending_action = None # Clear it immediately
        
        if not code_input.strip():
            result_obj = {"type": "warning", "message": "⚠️ Please write some code in the workspace first."}
            st.session_state.last_result = result_obj
            render_result(action, result_obj)
        else:
            # RUN CODE (Local only, instant)
            if action == "Run Code":
                with st.spinner("Running locally..."):
                    start_time = time.time()
                    output, error_msg, error_line = execute_python_code(code_input, program_input)
                    elapsed = time.time() - start_time
                    result_obj = {
                        "type": "run_code",
                        "output": output,
                        "error_msg": error_msg,
                        "error_line": error_line,
                        "elapsed": elapsed
                    }
                    st.session_state.last_result = result_obj
                    render_result(action, result_obj)
            
            elif action == "Visualize Code":
                is_syntax_valid, syntax_error_msg, syntax_line = validate_syntax(code_input)
                if not is_syntax_valid:
                    result_obj = {
                        "type": "run_code",
                        "output": "",
                        "error_msg": syntax_error_msg,
                        "error_line": syntax_line,
                        "elapsed": 0.0
                    }
                    st.session_state.last_result = result_obj
                    render_result(action, result_obj)
                else:
                    with st.spinner("Preparing visualization..."):
                        from visualizer.tracer import ExecutionTracer
                        start_time = time.time()
                        tracer = ExecutionTracer(code_input, program_input)
                        snapshots = tracer.run()
                        elapsed = time.time() - start_time
                        
                        st.session_state.visualizer_snapshots = snapshots
                        st.session_state.visualizer_source_lines = code_input.splitlines()
                        st.session_state.visualizer_current_step = 1
                        st.session_state.visualizer_is_playing = False
                        st.session_state.visualizer_exec_time = elapsed
                        st.session_state.visualizer_active = True
                        st.rerun()
            
            # EXPLAIN CODE (Cached or local LLM)
            elif action == "Explain Code":
                cache_key = get_cache_key(code_input, "Explain Code", mode_toggle, MODEL_NAME)
                if cache_key in st.session_state.response_cache:
                    result_obj = st.session_state.response_cache[cache_key]
                    result_obj["cached"] = True
                    st.session_state.last_result = result_obj
                    render_result(action, result_obj)
                else:
                    if static_only_mode or model is None:
                        result_obj = {"type": "error", "message": "AI model loading failed. Cannot generate explanation."}
                        st.session_state.last_result = result_obj
                        render_result(action, result_obj)
                    else:
                        start_time = time.time()
                        prompt_text = get_instruction_for_mode("Explain Code", len(code_input), is_fast_mode)
                        prompt_text += f"\n\nCode to analyze:\n```python\n{code_input[:3000]}\n```"
                        
                        st.subheader(f"Result: {action}")
                        status_placeholder = st.info("🧠 Generating explanation...")
                        placeholder = st.empty()
                        
                        response_chunks = []
                        try:
                            for chunk in generate_response_stream(model, tokenizer, device, prompt_text, MAX_TOKENS, TEMPERATURE):
                                status_placeholder.empty()
                                response_chunks.append(chunk)
                                placeholder.markdown("".join(response_chunks) + "▌")
                            
                            full_response = "".join(response_chunks)
                            placeholder.markdown(full_response)
                            elapsed = time.time() - start_time
                            
                            result_obj = {
                                "type": "markdown",
                                "content": full_response,
                                "elapsed": elapsed
                            }
                            st.session_state.response_cache[cache_key] = result_obj
                            st.session_state.last_result = result_obj
                            st.caption(f"⏱️ Generated in {elapsed:.3f} seconds.")
                        except Exception as e:
                            st.error(f"LLM Error: {str(e)}")
            
            # FIX ERRORS (Local verification + LLM only when required)
            elif action == "Fix Errors":
                cache_key = get_cache_key(code_input, "Fix Errors", mode_toggle, MODEL_NAME)
                if cache_key in st.session_state.response_cache:
                    result_obj = st.session_state.response_cache[cache_key]
                    result_obj["cached"] = True
                    st.session_state.last_result = result_obj
                    render_result(action, result_obj)
                else:
                    start_time = time.time()
                    
                    # Step 1: Check syntax
                    is_syntax_valid, syntax_error_msg, syntax_line = validate_syntax(code_input)
                    
                    if not is_syntax_valid:
                        lines = code_input.split('\n')
                        err_snippet = lines[syntax_line - 1] if syntax_line and 1 <= syntax_line <= len(lines) else code_input[:200]
                        st.subheader(f"Result: {action}")
                        st.markdown(f"<div class='error-box'><b>Syntax Error:</b> {syntax_error_msg} at line {syntax_line}</div>", unsafe_allow_html=True)
                        
                        if static_only_mode or model is None:
                            st.warning("Static-only mode: Cannot generate deep error corrections.")
                        else:
                            prompt_text = get_instruction_for_mode("Fix Errors", len(code_input), is_fast_mode, {"message": syntax_error_msg, "line": syntax_line})
                            prompt_text += f"\n\nCode causing error:\n```python\n{err_snippet}\n```"
                            
                            status_placeholder = st.info("Asking AI for a fast syntax fix...")
                            placeholder = st.empty()
                            
                            response_chunks = []
                            try:
                                for chunk in generate_response_stream(model, tokenizer, device, prompt_text, MAX_TOKENS, TEMPERATURE):
                                    status_placeholder.empty()
                                    response_chunks.append(chunk)
                                    placeholder.markdown(f"<div class='fix-box'><b>Suggested Fix:</b><br><br>{''.join(response_chunks)}▌</div>", unsafe_allow_html=True)
                                
                                full_explanation = "".join(response_chunks)
                                placeholder.markdown(f"<div class='fix-box'><b>Suggested Fix:</b><br><br>{full_explanation}</div>", unsafe_allow_html=True)
                                elapsed = time.time() - start_time
                                
                                result_obj = {
                                    "type": "fix_errors_failed",
                                    "error_msg": syntax_error_msg,
                                    "error_line": syntax_line,
                                    "explanation": full_explanation,
                                    "elapsed": elapsed
                                }
                                st.session_state.response_cache[cache_key] = result_obj
                                st.session_state.last_result = result_obj
                                st.caption(f"⏱️ Fix generated in {elapsed:.3f} seconds.")
                            except Exception as e:
                                st.error(f"LLM Error: {str(e)}")
                    else:
                        # Step 2: Check runtime error
                        output, error_msg, error_line = execute_python_code(code_input, program_input)
                        if not error_msg:
                            elapsed = time.time() - start_time
                            st.subheader(f"Result: {action}")
                            st.success("No syntax or runtime errors detected by local Python environment! 🎉")
                            
                            result_obj = {
                                "type": "fix_errors_success",
                                "content": "No syntax or runtime errors detected by local Python environment! 🎉",
                                "elapsed": elapsed
                            }
                            st.session_state.response_cache[cache_key] = result_obj
                            st.session_state.last_result = result_obj
                            st.caption(f"⏱️ Local scan completed in {elapsed:.3f} seconds.")
                            
                            # Give option to do deep logical check
                            if not static_only_mode and model is not None:
                                st.markdown("---")
                                st.markdown("##### 🔍 Deep Logical AI verification")
                                if st.button("Perform Deep Logic Scan"):
                                    st.session_state.pending_action = "Run Logical Fix Scan"
                                    st.rerun()
                        else:
                            lines = code_input.split('\n')
                            err_snippet = lines[error_line - 1] if error_line and 1 <= error_line <= len(lines) else code_input[:200]
                            st.subheader(f"Result: {action}")
                            st.markdown(f"<div class='error-box'><b>Runtime Error:</b> {error_msg} at line {error_line}</div>", unsafe_allow_html=True)
                            
                            if static_only_mode or model is None:
                                st.warning("Static-only mode: Cannot generate deep error corrections.")
                            else:
                                prompt_text = get_instruction_for_mode("Fix Errors", len(code_input), is_fast_mode, {"message": error_msg, "line": error_line})
                                prompt_text += f"\n\nCode causing error:\n```python\n{err_snippet}\n```"
                                
                                status_placeholder = st.info("Asking AI for a fast runtime fix...")
                                placeholder = st.empty()
                                
                                response_chunks = []
                                try:
                                    for chunk in generate_response_stream(model, tokenizer, device, prompt_text, MAX_TOKENS, TEMPERATURE):
                                        status_placeholder.empty()
                                        response_chunks.append(chunk)
                                        placeholder.markdown(f"<div class='fix-box'><b>Suggested Fix:</b><br><br>{''.join(response_chunks)}▌</div>", unsafe_allow_html=True)
                                    
                                    full_explanation = "".join(response_chunks)
                                    placeholder.markdown(f"<div class='fix-box'><b>Suggested Fix:</b><br><br>{full_explanation}</div>", unsafe_allow_html=True)
                                    elapsed = time.time() - start_time
                                    
                                    result_obj = {
                                        "type": "fix_errors_failed",
                                        "error_msg": error_msg,
                                        "error_line": error_line,
                                        "explanation": full_explanation,
                                        "elapsed": elapsed
                                    }
                                    st.session_state.response_cache[cache_key] = result_obj
                                    st.session_state.last_result = result_obj
                                    st.caption(f"⏱️ Fix generated in {elapsed:.3f} seconds.")
                                except Exception as e:
                                    st.error(f"LLM Error: {str(e)}")
            
            # DEEP LOGIC SCAN
            elif action == "Run Logical Fix Scan":
                st.subheader("Result: AI Logical Verification")
                start_time = time.time()
                prompt_text = "Verify if the following Python code contains any logical bugs. Keep the analysis short. If the logic looks correct, state so briefly. Code:\n"
                prompt_text += f"```python\n{code_input[:3000]}\n```"
                
                status_placeholder = st.info("Scanning logic...")
                placeholder = st.empty()
                
                response_chunks = []
                try:
                    for chunk in generate_response_stream(model, tokenizer, device, prompt_text, MAX_TOKENS, TEMPERATURE):
                        status_placeholder.empty()
                        response_chunks.append(chunk)
                        placeholder.markdown("".join(response_chunks) + "▌")
                    
                    full_response = "".join(response_chunks)
                    placeholder.markdown(full_response)
                    elapsed = time.time() - start_time
                    
                    result_obj = {
                        "type": "markdown",
                        "content": full_response,
                        "elapsed": elapsed
                    }
                    st.session_state.last_result = result_obj
                    st.caption(f"⏱️ Logic scan completed in {elapsed:.3f} seconds.")
                except Exception as e:
                    st.error(f"LLM Error: {str(e)}")

            # ANALYZE COMPLEXITY (Static-first with LLM fallback)
            elif action == "Analyze Complexity":
                cache_key = get_cache_key(code_input, "Analyze Complexity", mode_toggle, MODEL_NAME)
                if cache_key in st.session_state.response_cache:
                    result_obj = st.session_state.response_cache[cache_key]
                    result_obj["cached"] = True
                    st.session_state.last_result = result_obj
                    render_result(action, result_obj)
                else:
                    start_time = time.time()
                    static_res = analyze_complexity_statically(code_input)
                    
                    if static_res is not None:
                        time_c, space_c, explanation = static_res
                        elapsed = time.time() - start_time
                        result_obj = {
                            "type": "static_complexity",
                            "time_c": time_c,
                            "space_c": space_c,
                            "explanation": explanation,
                            "elapsed": elapsed
                        }
                        st.session_state.response_cache[cache_key] = result_obj
                        st.session_state.last_result = result_obj
                        render_result(action, result_obj)
                    else:
                        # Fallback to local LLM
                        if static_only_mode or model is None:
                            result_obj = {"type": "error", "message": "Static complexity check failed, and local AI model is not loaded."}
                            st.session_state.last_result = result_obj
                            render_result(action, result_obj)
                        else:
                            prompt_text = get_instruction_for_mode("Analyze Complexity", len(code_input), is_fast_mode)
                            prompt_text += f"\n\nCode to analyze:\n```python\n{code_input[:3000]}\n```"
                            
                            st.subheader(f"Result: {action}")
                            status_placeholder = st.info("Analyzing complexity via local LLM...")
                            placeholder = st.empty()
                            
                            response_chunks = []
                            try:
                                for chunk in generate_response_stream(model, tokenizer, device, prompt_text, MAX_TOKENS, TEMPERATURE):
                                    status_placeholder.empty()
                                    response_chunks.append(chunk)
                                    placeholder.markdown("".join(response_chunks) + "▌")
                                
                                full_response = "".join(response_chunks)
                                placeholder.markdown(full_response)
                                elapsed = time.time() - start_time
                                
                                result_obj = {
                                    "type": "markdown",
                                    "content": full_response,
                                    "elapsed": elapsed
                                }
                                st.session_state.response_cache[cache_key] = result_obj
                                st.session_state.last_result = result_obj
                                st.caption(f"⏱️ Complexity analysis completed in {elapsed:.3f} seconds.")
                            except Exception as e:
                                st.error(f"LLM Error: {str(e)}")

            # OPTIMIZE CODE
            elif action == "Optimize Code":
                cache_key = get_cache_key(code_input, "Optimize Code", mode_toggle, MODEL_NAME)
                if cache_key in st.session_state.response_cache:
                    result_obj = st.session_state.response_cache[cache_key]
                    result_obj["cached"] = True
                    st.session_state.last_result = result_obj
                    render_result(action, result_obj)
                else:
                    if static_only_mode or model is None:
                        result_obj = {"type": "error", "message": "AI model loading failed. Cannot optimize code."}
                        st.session_state.last_result = result_obj
                        render_result(action, result_obj)
                    else:
                        start_time = time.time()
                        prompt_text = get_instruction_for_mode("Optimize Code", len(code_input), is_fast_mode)
                        prompt_text += f"\n\nCode to optimize:\n```python\n{code_input[:3000]}\n```"
                        
                        st.subheader(f"Result: {action}")
                        status_placeholder = st.info("Optimizing code...")
                        placeholder = st.empty()
                        
                        response_chunks = []
                        try:
                            for chunk in generate_response_stream(model, tokenizer, device, prompt_text, MAX_TOKENS, TEMPERATURE):
                                status_placeholder.empty()
                                response_chunks.append(chunk)
                                placeholder.markdown("".join(response_chunks) + "▌")
                            
                            full_response = "".join(response_chunks)
                            placeholder.markdown(full_response)
                            elapsed = time.time() - start_time
                            
                            result_obj = {
                                "type": "markdown",
                                "content": full_response,
                                "elapsed": elapsed
                            }
                            st.session_state.response_cache[cache_key] = result_obj
                            st.session_state.last_result = result_obj
                            st.caption(f"⏱️ Optimization completed in {elapsed:.3f} seconds.")
                        except Exception as e:
                            st.error(f"LLM Error: {str(e)}")
    else:
        # Show last saved result or default instructions
        if st.session_state.last_action and st.session_state.last_result:
            render_result(st.session_state.last_action, st.session_state.last_result)
        else:
            st.info("👈 Write code and click any action on the left to start.")
            st.markdown("""
            ### Tips for Near-Instant Response Times:
            - **Fast Mode (Default):** Prompts are optimized to get short and deterministic outputs.
            - **Static Analysis:** Runs instantly (Time complexity, syntax/runtime validation) without loading or invoking the local LLM.
            - **Model Choice:** Use **Qwen 2.5 Coder 0.5B** on CPU for maximum speed.
            - **Aggressive Caching:** Running the same operation on the same code will resolve instantly.
            """)
