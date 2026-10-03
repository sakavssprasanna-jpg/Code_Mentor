import streamlit as st
import streamlit.components.v1 as components
import json

def safe_json_dumps(obj):
    """Safely serialize JSON for embedding within script tags."""
    return json.dumps(obj).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

def show_visualizer_ui():
    """Renders the polished Python Execution Visualizer using an interactive client-side iframe."""
    
    if "visualizer_snapshots" not in st.session_state or not st.session_state.visualizer_snapshots:
        st.error("No execution snapshots loaded.")
        if st.button("Back to Workspace"):
            st.session_state.visualizer_active = False
            st.rerun()
        return

    snapshots = st.session_state.visualizer_snapshots
    source_lines = st.session_state.visualizer_source_lines
    exec_time = st.session_state.get("visualizer_exec_time", 0.0)

    # 1. Header and Exit Controls rendered in Streamlit (at the top)
    col_title, col_stop = st.columns([4, 1])
    with col_title:
        st.markdown("""
        <div style="margin-top: 5px;">
            <span style="font-size: 22px; font-weight: 700; color: #58a6ff;">🐍 Python Execution Visualizer</span>
            <span style="font-size: 13px; color: #8b949e; margin-left: 10px;">Step-by-step visual code debugger and execution flow analysis</span>
        </div>
        """, unsafe_allow_html=True)
    with col_stop:
        if st.button("⏹ Stop Visualizer", use_container_width=True):
            st.session_state.visualizer_is_playing = False
            st.session_state.visualizer_active = False
            st.rerun()

    st.markdown("<hr style='margin: 8px 0 12px 0; border-color: #21262d;'>", unsafe_allow_html=True)

    # 2. Serialize snapshots and source code lines safely for the JS application
    steps_json = safe_json_dumps(snapshots)
    code_lines_json = safe_json_dumps(source_lines)

    # 3. HTML/CSS/JS Application String
    visualizer_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Python visualizer Component</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                height: 100%;
                background-color: #0d1117;
                color: #c9d1d9;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                overflow: hidden;
            }}
            .app-container {{
                display: flex;
                flex-direction: column;
                height: 100vh;
                box-sizing: border-box;
                padding: 12px;
                background-color: #0d1117;
            }}
            .main-content {{
                display: flex;
                flex: 1;
                gap: 16px;
                min-height: 0;
                margin-bottom: 12px;
            }}
            .left-panel {{
                flex: 4.5;
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                display: flex;
                flex-direction: column;
                min-height: 0;
            }}
            .right-panel {{
                flex: 5.5;
                display: flex;
                flex-direction: column;
                gap: 12px;
                min-height: 0;
                overflow-y: auto;
                padding-right: 4px;
            }}
            .panel-header {{
                background-color: #161b22;
                border-bottom: 1px solid #30363d;
                padding: 8px 12px;
                font-size: 12.5px;
                font-weight: 600;
                color: #8b949e;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .code-scroll-container {{
                flex: 1;
                overflow-y: auto;
                padding: 12px 0;
                background-color: #090c10;
                position: relative;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
            .code-container {{
                position: relative;
                font-family: 'JetBrains Mono', monospace;
                font-size: 13px;
                line-height: 22px;
            }}
            .code-line {{
                position: relative;
                display: flex;
                align-items: flex-start;
                padding: 0px 8px 0px 24px;
                border-left: 3px solid transparent;
                transition: background-color 0.2s ease, border-left-color 0.2s ease;
            }}
            .code-line.active-line {{
                background-color: rgba(56, 139, 253, 0.15);
                border-left-color: #58a6ff;
            }}
            .line-number {{
                color: #8b949e;
                width: 25px;
                text-align: right;
                margin-right: 14px;
                user-select: none;
                font-size: 12px;
            }}
            .line-content {{
                white-space: pre-wrap;
                color: #c9d1d9;
            }}
            .execution-pointer {{
                position: absolute;
                left: 6px;
                color: #58a6ff;
                font-weight: bold;
                font-size: 11px;
                line-height: 22px;
                transition: top 0.18s cubic-bezier(0.25, 1, 0.5, 1);
                pointer-events: none;
                z-index: 10;
            }}
            
            /* Card Containers */
            .card {{
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 12px;
                position: relative;
                transition: border-color 0.3s ease, box-shadow 0.3s ease;
            }}
            .card-title {{
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                color: #8b949e;
                font-weight: 700;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            
            /* Flash animation on value modification */
            @keyframes flash-green {{
                0% {{ border-color: #3fb950; box-shadow: 0 0 6px rgba(63, 185, 80, 0.3); }}
                100% {{ border-color: #30363d; box-shadow: none; }}
            }}
            .flash-change {{
                animation: flash-green 1.2s ease-out;
            }}
            
            /* Variable layout */
            .variables-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 4px;
            }}
            .var-card {{
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 10px;
                min-width: 130px;
                max-width: 260px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                box-sizing: border-box;
                transition: border-color 0.3s ease;
            }}
            .var-card.flash-change {{
                animation: flash-green 1.2s ease-out;
            }}
            .var-header {{
                display: flex;
                justify-content: space-between;
                font-size: 10px;
                color: #8b949e;
                margin-bottom: 3px;
                align-items: center;
            }}
            .var-name {{
                color: #58a6ff;
                font-weight: 600;
            }}
            .var-scope {{
                background-color: #21262d;
                padding: 1px 4px;
                border-radius: 4px;
                font-size: 9px;
            }}
            .var-type {{
                color: #f0883e;
                font-size: 10px;
                font-weight: 500;
            }}
            .var-value {{
                color: #c9d1d9;
                word-break: break-all;
                font-size: 12px;
            }}
            
            /* Heap structure rendering */
            .list-container {{
                display: flex;
                align-items: flex-start;
                gap: 6px;
                flex-wrap: wrap;
                margin-top: 6px;
            }}
            .list-element-wrapper {{
                display: flex;
                flex-direction: column;
                align-items: center;
                animation: pop-in 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
            }}
            @keyframes pop-in {{
                0% {{ transform: scale(0.75); opacity: 0; }}
                100% {{ transform: scale(1); opacity: 1; }}
            }}
            .list-cell {{
                min-width: 40px;
                height: 40px;
                border: 1px solid #30363d;
                background-color: #0d1117;
                color: #c9d1d9;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 6px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12.5px;
                padding: 0 8px;
                box-sizing: border-box;
                transition: background-color 0.3s ease, border-color 0.3s ease;
            }}
            .list-cell.flash-change {{
                background-color: rgba(56, 139, 253, 0.15);
                border-color: #58a6ff;
            }}
            .list-index {{
                font-size: 10px;
                color: #8b949e;
                margin-top: 3px;
                font-family: 'JetBrains Mono', monospace;
            }}
            
            .dict-table {{
                width: 100%;
                border-collapse: collapse;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                margin-top: 6px;
                background-color: #0d1117;
                border-radius: 6px;
                overflow: hidden;
            }}
            .dict-table th, .dict-table td {{
                border: 1px solid #30363d;
                padding: 6px 12px;
                text-align: left;
            }}
            .dict-table th {{
                background-color: #161b22;
                color: #8b949e;
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
            }}
            .dict-table tr {{
                transition: background-color 0.3s ease;
            }}
            .dict-table tr.changed-row {{
                background-color: rgba(56, 139, 253, 0.12);
            }}
            
            /* Loop and condition widgets */
            .loop-badge {{
                background-color: #1c2638;
                border: 1px solid #2f81f7;
                color: #58a6ff;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                margin-top: 4px;
            }}
            
            .cond-container {{
                background-color: #1c1d21;
                border-left: 4px solid #8b949e;
                border-top: 1px solid #30363d;
                border-right: 1px solid #30363d;
                border-bottom: 1px solid #30363d;
                border-radius: 0 6px 6px 0;
                padding: 8px 12px;
                margin-top: 4px;
            }}
            .cond-container.cond-true {{
                border-left-color: #3fb950;
                background-color: rgba(63, 185, 80, 0.04);
            }}
            .cond-container.cond-false {{
                border-left-color: #f85149;
                background-color: rgba(248, 81, 73, 0.04);
            }}
            .cond-badge {{
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                display: inline-block;
            }}
            .cond-badge.badge-true {{ background-color: rgba(63, 185, 80, 0.2); color: #56d364; }}
            .cond-badge.badge-false {{ background-color: rgba(248, 81, 73, 0.2); color: #ff7b72; }}
            
            /* Call stack */
            .stack-frame {{
                border: 1px solid #30363d;
                background-color: #0d1117;
                border-radius: 6px;
                padding: 8px 12px;
                margin-bottom: 6px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                transition: border-color 0.2s ease, background-color 0.2s ease;
            }}
            .stack-frame.active-frame {{
                border-color: #58a6ff;
                background-color: rgba(56, 139, 253, 0.08);
            }}
            .stack-frame-name {{
                font-weight: 600;
            }}
            
            /* Console output */
            .console-box {{
                background-color: #090c10;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 10px 14px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12.5px;
                color: #c9d1d9;
                white-space: pre-wrap;
                min-height: 48px;
                max-height: 120px;
                overflow-y: auto;
                line-height: 1.5;
            }}
            
            /* Control Footer */
            .control-bar {{
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 10px 14px;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }}
            .control-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 16px;
            }}
            .btn-group {{
                display: flex;
                gap: 6px;
            }}
            .btn {{
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                padding: 6px 12px;
                border-radius: 6px;
                font-family: 'Inter', sans-serif;
                font-size: 12.5px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 4px;
                user-select: none;
            }}
            .btn:hover:not(:disabled) {{
                background-color: #30363d;
                border-color: #8b949e;
            }}
            .btn:disabled {{
                opacity: 0.4;
                cursor: not-allowed;
            }}
            .btn-primary {{
                background-color: #238636;
                border-color: #2ea44f;
                color: white;
            }}
            .btn-primary:hover:not(:disabled) {{
                background-color: #2ea44f;
            }}
            
            /* Slider elements */
            .slider-container {{
                flex: 1;
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 12px;
                color: #8b949e;
                font-family: 'JetBrains Mono', monospace;
            }}
            .timeline-slider {{
                flex: 1;
                accent-color: #58a6ff;
                cursor: pointer;
                height: 5px;
                border-radius: 2px;
            }}
            .speed-slider {{
                width: 100px;
                accent-color: #58a6ff;
                cursor: pointer;
                height: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="app-container">
            <div class="main-content">
                <!-- Left Column: Code Trace -->
                <div class="left-panel">
                    <div class="panel-header">
                        <span>📝 SOURCE CODE</span>
                        <span id="line-indicator" style="font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: #58a6ff;">Line 1</span>
                    </div>
                    <div class="code-scroll-container" id="code-panel-container">
                        <div class="code-container" id="code-container">
                            <!-- Populated dynamically by JS -->
                        </div>
                    </div>
                </div>

                <!-- Right Column: Visual State details -->
                <div class="right-panel">
                    <!-- Error State widget (conditional) -->
                    <div id="error-container" style="display: none;"></div>

                    <!-- Step Explanation -->
                    <div class="card" id="explanation-container">
                        <div class="card-title">💡 WHAT HAPPENED?</div>
                        <div id="explanation-content" style="font-size: 13px; line-height: 1.5;">Initializing...</div>
                    </div>

                    <!-- Loop and Condition Visual widgets (conditional) -->
                    <div class="card" id="loop-container" style="display: none;"></div>
                    <div class="card" id="conditional-container" style="display: none;"></div>

                    <!-- Scalar Stack Variables -->
                    <div class="card">
                        <div class="card-title">📦 MEMORY (VARIABLES)</div>
                        <div class="variables-grid" id="memory-container">
                            <!-- Populated dynamically by JS -->
                        </div>
                    </div>

                    <!-- Complex Data Structures -->
                    <div class="card">
                        <div class="card-title">🗂️ DATA STRUCTURES (HEAP)</div>
                        <div id="structures-container">
                            <!-- Populated dynamically by JS -->
                        </div>
                    </div>

                    <!-- Function Frames (Call Stack) -->
                    <div class="card">
                        <div class="card-title">🥞 CALL STACK</div>
                        <div id="stack-container">
                            <!-- Populated dynamically by JS -->
                        </div>
                    </div>

                    <!-- Console/Standard Output -->
                    <div class="card">
                        <div class="card-title">🖥️ CONSOLE OUTPUT</div>
                        <div class="console-box" id="console-box"></div>
                    </div>
                </div>
            </div>

            <!-- Bottom: Footer Control Bar -->
            <div class="control-bar">
                <div class="control-row">
                    <div class="btn-group">
                        <button class="btn" id="btn-prev" onclick="handlePrev()">⏮ Prev</button>
                        <button class="btn btn-primary" id="btn-play" onclick="handlePlay()">▶ Play</button>
                        <button class="btn btn-primary" id="btn-pause" onclick="handlePause()" style="display: none; background-color: #a37100; border-color: #b07c00;">⏸ Pause</button>
                        <button class="btn" id="btn-next" onclick="handleNext()">⏭ Next</button>
                        <button class="btn" id="btn-restart" onclick="handleRestart()">🔄 Restart</button>
                    </div>

                    <div class="slider-container">
                        <span>TIMELINE</span>
                        <input type="range" class="timeline-slider" id="timeline-slider" min="1" max="100" value="1">
                        <span id="step-indicator" style="min-width: 90px; text-align: right;">Step 1 / 1</span>
                    </div>

                    <div class="slider-container" style="max-width: 200px;">
                        <span>SPEED</span>
                        <input type="range" class="speed-slider" id="speed-slider" min="0.25" max="2.0" step="0.25" value="1.0">
                        <span id="speed-indicator" style="min-width: 40px;">1.00x</span>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Loaded JSON parameters from Python
            const codeLines = {code_lines_json};
            const steps = {steps_json};
            
            // Player state variables
            let currentStepIndex = 0;
            let isPlaying = false;
            let playbackSpeed = 1.0;
            let playbackTimeout = null;

            // HTML Emitter Helper
            function escapeHtml(text) {{
                if (text === null || text === undefined) return "";
                if (typeof text !== "string") text = String(text);
                return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
            }}

            // Initialize Page Elements
            function initializeApp() {{
                renderSourceCode();
                
                // Set Slider properties
                const slider = document.getElementById("timeline-slider");
                slider.max = steps.length;
                slider.value = 1;
                
                // Add event listeners
                slider.addEventListener("input", function() {{
                    handlePause();
                    goToStep(parseInt(slider.value) - 1);
                }});

                const speedSlider = document.getElementById("speed-slider");
                speedSlider.addEventListener("input", function() {{
                    playbackSpeed = parseFloat(speedSlider.value);
                    document.getElementById("speed-indicator").innerText = playbackSpeed.toFixed(2) + "x";
                }});

                // Go to step 0
                goToStep(0);
            }}

            // Renders static line code elements
            function renderSourceCode() {{
                const container = document.getElementById("code-container");
                container.innerHTML = "";
                
                // Create absolute line pointer
                const pointer = document.createElement("div");
                pointer.id = "execution-pointer";
                pointer.className = "execution-pointer";
                pointer.innerHTML = "▶";
                container.appendChild(pointer);

                codeLines.forEach((line, idx) => {{
                    const lineNum = idx + 1;
                    
                    const lineNode = document.createElement("div");
                    lineNode.id = "line-" + lineNum;
                    lineNode.className = "code-line";
                    
                    const numNode = document.createElement("span");
                    numNode.className = "line-number";
                    numNode.innerText = lineNum;
                    
                    const contentNode = document.createElement("span");
                    contentNode.className = "line-content";
                    contentNode.innerText = line.length > 0 ? line : " "; // Force single space to keep block height

                    lineNode.appendChild(numNode);
                    lineNode.appendChild(contentNode);
                    container.appendChild(lineNode);
                }});
            }}

            // Computes step explanation dynamically in JS
            function generateExplanation(step, prevStep) {{
                if (step.event === 'exception' && step.exception) {{
                    return `<span style="color: #f85149; font-weight: bold;">⚠️ Stopped due to error:</span> <code>${{escapeHtml(step.exception.type)}}</code>: ${{escapeHtml(step.exception.message)}}`;
                }}

                const lineText = codeLines[step.line - 1] || "";
                const stripped = lineText.trim();

                if (step.event === 'call' && step.call_stack && step.call_stack.length > 0) {{
                    const frame = step.call_stack[0];
                    return `📞 Calling function <code style="color: #58a6ff;">${{escapeHtml(frame.signature)}}</code> on line ${{step.line}}. Entering its namespace frame.`;
                }}
                if (step.event === 'return' && step.call_stack && step.call_stack.length > 0) {{
                    const frame = step.call_stack[0];
                    const retVal = step.return_value ? step.return_value.repr : 'None';
                    return `↩️ Function <code style="color: #58a6ff;">${{escapeHtml(frame.name)}}()</code> returned: <code style="color: #56d364;">${{escapeHtml(retVal)}}</code>. Exiting stack frame.`;
                }}

                if (stripped.startsWith("if ") || stripped.startsWith("elif ")) {{
                    let condExpr = stripped.replace(/^(if|elif)\\s+/, "").replace(/:$/, "").trim();
                    let isTrue = false;
                    if (currentStepIndex + 1 < steps.length) {{
                        const nextStep = steps[currentStepIndex + 1];
                        if (nextStep.line > step.line) {{
                            const nextLineText = codeLines[nextStep.line - 1] || "";
                            const nextIndent = nextLineText.length - nextLineText.trimStart().length;
                            const currIndent = lineText.length - lineText.trimStart().length;
                            if (nextIndent > currIndent) {{
                                isTrue = true;
                            }}
                        }}
                    }}
                    return `⚖️ Evaluating condition <code style="color: #bc8cff;">${{escapeHtml(condExpr)}}</code> → <span style="font-weight: bold; color: ${{isTrue ? '#56d364' : '#ff7b72'}}">${{isTrue ? '✓ TRUE' : '✗ FALSE'}}</span>. Taking appropriate branch.`;
                }}

                if (stripped.startsWith("for ") || stripped.startsWith("while ")) {{
                    let loopVar = "";
                    if (stripped.startsWith("for ")) {{
                        const match = stripped.match(/for\\s+([a-zA-Z_][a-zA-Z0-9_]*(\\s*,\\s*[a-zA-Z_][a-zA-Z0-9_]*)*)\\s+in/);
                        if (match) loopVar = match[1].trim();
                    }}
                    let loopVal = loopVar && step.locals[loopVar] ? step.locals[loopVar].repr : "";
                    return `🔄 Executing loop condition/header line. ${{loopVar ? `Target variable <code>${{loopVar}}</code> set to <code>${{loopVal}}</code>.` : ''}}`;
                }}

                // Check for scalar variable assignments/updates
                let changes = [];
                if (prevStep) {{
                    for (const [k, v] of Object.entries(step.locals)) {{
                        if (k.startsWith('__')) continue;
                        const prevVal = prevStep.locals[k];
                        if (!prevVal) {{
                            changes.push(`Variable <code style="color: #58a6ff;">${{k}}</code> created with value <code style="color: #56d364;">${{escapeHtml(v.repr)}}</code>`);
                        }} else if (prevVal.repr !== v.repr) {{
                            changes.push(`Variable <code style="color: #58a6ff;">${{k}}</code> updated from <code style="color: #8b949e;">${{escapeHtml(prevVal.repr)}}</code> ➔ <code style="color: #56d364; font-weight: bold;">${{escapeHtml(v.repr)}}</code>`);
                        }}
                    }}
                    for (const [k, v] of Object.entries(step.globals)) {{
                        if (k.startsWith('__')) continue;
                        const prevVal = prevStep.globals[k];
                        if (!prevVal) {{
                            changes.push(`Global <code style="color: #58a6ff;">${{k}}</code> created with value <code style="color: #56d364;">${{escapeHtml(v.repr)}}</code>`);
                        }} else if (prevVal.repr !== v.repr) {{
                            changes.push(`Global <code style="color: #58a6ff;">${{k}}</code> changed: <code style="color: #8b949e;">${{escapeHtml(prevVal.repr)}}</code> ➔ <code style="color: #56d364; font-weight: bold;">${{escapeHtml(v.repr)}}</code>`);
                        }}
                    }}
                }} else {{
                    for (const [k, v] of Object.entries(step.locals)) {{
                        if (k.startsWith('__')) continue;
                        changes.push(`Variable <code style="color: #58a6ff;">${{k}}</code> initialized to <code style="color: #56d364;">${{escapeHtml(v.repr)}}</code>`);
                    }}
                }}

                if (changes.length > 0) {{
                    return changes.join("<br>");
                }}

                return `⚙️ Running line ${{step.line}}: <code style="color: #c9d1d9;">${{escapeHtml(stripped)}}</code>`;
            }}

            // Computes loop variables and iterations
            function getLoopInfo(stepIndex) {{
                const step = steps[stepIndex];
                const L = step.line;
                if (L > codeLines.length) return null;
                const lineText = codeLines[L - 1];
                const stripped = lineText.trim();
                if (!stripped.startsWith("for ") && !stripped.startsWith("while ")) return null;

                const indent = lineText.length - lineText.trimStart().length;
                const callStackSig = step.call_stack.length > 0 ? step.call_stack[0].signature : "";
                
                // Count current iterations
                let currIter = 0;
                for (let i = 0; i <= stepIndex; i++) {{
                    const s = steps[i];
                    const sSig = s.call_stack.length > 0 ? s.call_stack[0].signature : "";
                    if (s.line === L && sSig === callStackSig) {{
                        currIter++;
                    }}
                }}

                // Calculate total iterations
                let totalIter = currIter;
                for (let i = stepIndex + 1; i < steps.length; i++) {{
                    const s = steps[i];
                    const sSig = s.call_stack.length > 0 ? s.call_stack[0].signature : "";
                    if (sSig !== callStackSig) {{
                        if (s.call_stack.length < step.call_stack.length) break;
                        continue;
                    }}
                    const nextL = s.line;
                    if (nextL > codeLines.length) break;
                    const nextLine = codeLines[nextL - 1];
                    if (!nextLine.trim()) continue;
                    const nextIndent = nextLine.length - nextLine.trimStart().length;

                    if (nextL === L) {{
                        totalIter++;
                    }} else if (nextIndent <= indent) {{
                        break;
                    }}
                }}

                let loopVar = "";
                if (stripped.startsWith("for ")) {{
                    const match = stripped.match(/for\\s+([a-zA-Z_][a-zA-Z0-9_]*(\\s*,\\s*[a-zA-Z_][a-zA-Z0-9_]*)*)\\s+in/);
                    if (match) loopVar = match[1].trim();
                }}

                let loopVal = "";
                if (loopVar && step.locals[loopVar]) {{
                    loopVal = step.locals[loopVar].repr;
                }}

                return {{
                    current: currIter,
                    total: totalIter,
                    var: loopVar,
                    val: loopVal
                }};
            }}

            // Computes condition path evaluation details
            function getConditionInfo(stepIndex) {{
                const step = steps[stepIndex];
                const L = step.line;
                if (L > codeLines.length) return null;
                const lineText = codeLines[L - 1];
                const stripped = lineText.trim();
                if (!stripped.startsWith("if ") && !stripped.startsWith("elif ")) return null;

                let condExpr = stripped.replace(/^(if|elif)\\s+/, "").replace(/:$/, "").trim();
                let isTrue = false;
                if (stepIndex + 1 < steps.length) {{
                    const nextStep = steps[stepIndex + 1];
                    const nextL = nextStep.line;
                    if (nextL > L && nextL <= codeLines.length) {{
                        const nextLine = codeLines[nextL - 1];
                        const nextIndent = nextLine.length - nextLine.trimStart().length;
                        const currIndent = lineText.length - lineText.trimStart().length;
                        if (nextIndent > currIndent) {{
                            isTrue = true;
                        }}
                    }}
                }}

                let varsState = {{}};
                for (const [varName, varVal] of Object.entries(step.locals)) {{
                    const regex = new RegExp("\\\\b" + varName + "\\\\b");
                    if (regex.test(condExpr)) {{
                        varsState[varName] = varVal.repr;
                    }}
                }}
                for (const [varName, varVal] of Object.entries(step.globals)) {{
                    const regex = new RegExp("\\\\b" + varName + "\\\\b");
                    if (regex.test(condExpr) && !varsState[varName]) {{
                        varsState[varName] = varVal.repr;
                    }}
                }}

                return {{
                    expr: condExpr,
                    vars: varsState,
                    result: isTrue
                }};
            }}

            // Master navigation function
            function goToStep(index) {{
                if (index < 0) index = 0;
                if (index >= steps.length) index = steps.length - 1;

                currentStepIndex = index;
                const step = steps[index];
                const prevStep = index > 0 ? steps[index - 1] : null;

                // 1. Move pointer and highlight line
                const oldActive = document.querySelector(".code-line.active-line");
                if (oldActive) oldActive.classList.remove("active-line");

                const activeLineNode = document.getElementById("line-" + step.line);
                if (activeLineNode) {{
                    activeLineNode.classList.add("active-line");
                    const pointer = document.getElementById("execution-pointer");
                    pointer.style.top = activeLineNode.offsetTop + "px";
                    
                    // Update Line indicator text
                    document.getElementById("line-indicator").innerText = "Line " + step.line;

                    // Scroll viewport to line if out of boundaries
                    const scrollParent = document.getElementById("code-panel-container");
                    const offsetTop = activeLineNode.offsetTop;
                    const containerHeight = scrollParent.clientHeight;
                    if (offsetTop < scrollParent.scrollTop || offsetTop > (scrollParent.scrollTop + containerHeight - 40)) {{
                        scrollParent.scrollTo({{
                            top: offsetTop - containerHeight / 2,
                            behavior: 'smooth'
                        }});
                    }}
                }}

                // 2. Render Text Explanation
                document.getElementById("explanation-content").innerHTML = generateExplanation(step, prevStep);

                // 3. Render Error Banner (if applicable)
                const errorDiv = document.getElementById("error-container");
                if (step.exception) {{
                    errorDiv.style.display = "block";
                    errorDiv.innerHTML = `
                        <div style="background-color: #2d191e; border: 1px solid #f85149; border-radius: 8px; padding: 12px; color: #ff7b72; font-family: 'JetBrains Mono', monospace; font-size: 13px; margin-bottom: 12px;">
                            <div style="font-weight: bold; font-size: 14.5px; margin-bottom: 4px;">⚠️ EXECUTION STOPPED (${{escapeHtml(step.exception.type)}})</div>
                            <div>${{escapeHtml(step.exception.message)}}</div>
                            <div style="margin-top: 6px; font-size: 11px; color: #8b949e;">Line ${{step.line}}: ${{escapeHtml((codeLines[step.line - 1] || '').trim())}}</div>
                        </div>
                    `;
                }} else {{
                    errorDiv.style.display = "none";
                }}

                // 4. Render Loop Box (if applicable)
                const loopDiv = document.getElementById("loop-container");
                const loopInfo = getLoopInfo(index);
                if (loopInfo) {{
                    loopDiv.style.display = "block";
                    let varText = "";
                    if (loopInfo.var) {{
                        varText = `<div style="margin-top: 5px; font-family: 'JetBrains Mono', monospace; font-size: 12px;">
                            Loop target: <code style="color: #58a6ff;">${{loopInfo.var}}</code> = <code style="color: #56d364;">${{escapeHtml(loopInfo.val || 'None')}}</code>
                        </div>`;
                    }}
                    loopDiv.innerHTML = `
                        <div class="card-title">🔄 LOOP VISUALIZATION</div>
                        <div class="loop-badge">
                            <span>↻ Loop Iteration: ${{loopInfo.current}} / ${{loopInfo.total}}</span>
                        </div>
                        ${{varText}}
                    `;
                }} else {{
                    loopDiv.style.display = "none";
                }}

                // 5. Render Conditional Box (if applicable)
                const condDiv = document.getElementById("conditional-container");
                const condInfo = getConditionInfo(index);
                if (condInfo) {{
                    condDiv.style.display = "block";
                    const statusClass = condInfo.result ? "cond-true" : "cond-false";
                    const badgeClass = condInfo.result ? "badge-true" : "badge-false";
                    const badgeText = condInfo.result ? "TRUE" : "FALSE";
                    const actionText = condInfo.result ? "Executing IF body" : "Condition failed, skipping";
                    
                    let varsHtml = "";
                    if (Object.keys(condInfo.vars).length > 0) {{
                        varsHtml = `<div style="margin-top: 6px; font-size: 11.5px; color: #8b949e;">Variables in check: `;
                        for (const [k, v] of Object.entries(condInfo.vars)) {{
                            varsHtml += `<code style="color: #f0883e;">${{k}}</code>=${{escapeHtml(v)}} &nbsp;`;
                        }}
                        varsHtml += `</div>`;
                    }}
                    
                    condDiv.innerHTML = `
                        <div class="card-title">⚖️ CONDITIONAL EVALUATION</div>
                        <div class="cond-container ${{statusClass}}">
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 12.5px;">
                                <span style="color: #ff7b72;">if</span> <span style="color: #58a6ff;">${{escapeHtml(condInfo.expr)}}</span>:
                            </div>
                            ${{varsHtml}}
                            <div style="margin-top: 8px; display: flex; align-items: center; gap: 8px; font-size: 12px;">
                                <span class="cond-badge ${{badgeClass}}">${{badgeText}}</span>
                                <span style="color: #8b949e;">&mdash; ${{actionText}}</span>
                            </div>
                        </div>
                    `;
                }} else {{
                    condDiv.style.display = "none";
                }}

                // 6. Render Memory & Complex Structures (Heap)
                const memoryDiv = document.getElementById("memory-container");
                const structuresDiv = document.getElementById("structures-container");
                memoryDiv.innerHTML = "";
                structuresDiv.innerHTML = "";

                let allVars = {{}};
                for (const [k, v] of Object.entries(step.locals)) {{
                    allVars[k] = {{ info: v, scope: "local" }};
                }}
                for (const [k, v] of Object.entries(step.globals)) {{
                    if (!allVars[k]) {{
                        allVars[k] = {{ info: v, scope: "global" }};
                    }}
                }}

                let hasScalars = false;
                let hasStructures = false;
                const sortedKeys = Object.keys(allVars).sort();

                sortedKeys.forEach(key => {{
                    const {{ info, scope }} = allVars[key];
                    const valType = info.type;
                    const currRepr = info.repr;

                    // Variable changed check
                    let changed = false;
                    let prevRepr = null;
                    if (prevStep) {{
                        const prevVars = scope === "local" ? prevStep.locals : prevStep.globals;
                        if (prevVars[key]) {{
                            prevRepr = prevVars[key].repr;
                            if (prevRepr !== currRepr) changed = true;
                        }} else {{
                            changed = true; // brand new
                        }}
                    }}

                    const flashClass = changed ? "flash-change" : "";

                    if (valType === "list" || valType === "tuple" || valType === "set") {{
                        hasStructures = true;
                        const elements = info.value || [];
                        let cellsHtml = "";
                        
                        elements.forEach((item, idx) => {{
                            let cellChanged = false;
                            if (prevStep) {{
                                const prevVars = scope === "local" ? prevStep.locals : prevStep.globals;
                                if (prevVars[key] && prevVars[key].value && prevVars[key].value[idx]) {{
                                    if (prevVars[key].value[idx].repr !== item.repr) cellChanged = true;
                                }} else {{
                                    cellChanged = true;
                                }}
                            }}
                            
                            const cellFlash = cellChanged ? "flash-change" : "";
                            cellsHtml += `
                                <div class="list-element-wrapper">
                                    <div class="list-cell ${{cellFlash}}">${{escapeHtml(item.repr)}}</div>
                                    <div class="list-index">[${{idx}}]</div>
                                </div>
                            `;
                        }});

                        if (elements.length === 0) {{
                            cellsHtml = `<div style="color: #8b949e; font-style: italic; font-size: 12px;">Empty list</div>`;
                        }}

                        structuresDiv.innerHTML += `
                            <div class="card ${{flashClass}}" style="margin-bottom: 8px; background-color: #0d1117;">
                                <div class="var-header" style="margin-bottom: 6px;">
                                    <div>
                                        <span class="var-name" style="font-size: 13.5px;">${{key}}</span>
                                        <span class="var-scope">${{scope}}</span>
                                    </div>
                                    <span class="var-type">${{valType}}</span>
                                </div>
                                <div class="list-container">
                                    ${{cellsHtml}}
                                </div>
                            </div>
                        `;
                    }} else if (valType === "dict") {{
                        hasStructures = true;
                        const items = info.value || {{}};
                        let rowsHtml = "";
                        
                        for (const [k, v] of Object.entries(items)) {{
                            let cellChanged = false;
                            if (prevStep) {{
                                const prevVars = scope === "local" ? prevStep.locals : prevStep.globals;
                                if (prevVars[key] && prevVars[key].value && prevVars[key].value[k]) {{
                                    if (prevVars[key].value[k].repr !== v.repr) cellChanged = true;
                                }} else {{
                                    cellChanged = true;
                                }}
                            }}
                            const rowClass = cellChanged ? "changed-row" : "";
                            rowsHtml += `
                                <tr class="${{rowClass}}">
                                    <td style="font-weight: 600; color: #8b949e;">${{escapeHtml(k)}}</td>
                                    <td style="color: #c9d1d9;">${{escapeHtml(v.repr)}}</td>
                                </tr>
                            `;
                        }}

                        if (Object.keys(items).length === 0) {{
                            rowsHtml = `<tr><td colspan="2" style="color: #8b949e; font-style: italic; text-align: center;">Empty dict</td></tr>`;
                        }}

                        structuresDiv.innerHTML += `
                            <div class="card ${{flashClass}}" style="margin-bottom: 8px; background-color: #0d1117;">
                                <div class="var-header" style="margin-bottom: 6px;">
                                    <div>
                                        <span class="var-name" style="font-size: 13.5px;">${{key}}</span>
                                        <span class="var-scope">${{scope}}</span>
                                    </div>
                                    <span class="var-type">${{valType}}</span>
                                </div>
                                <table class="dict-table">
                                    <thead>
                                        <tr><th>Key</th><th>Value</th></tr>
                                    </thead>
                                    <tbody>
                                        ${{rowsHtml}}
                                    </tbody>
                                </table>
                            </div>
                        `;
                    }} else {{
                        hasScalars = true;
                        let valDisplay = escapeHtml(currRepr);
                        if (changed && prevRepr !== null) {{
                            valDisplay = `<span style="color: #8b949e; text-decoration: line-through;">${{escapeHtml(prevRepr)}}</span> <span style="color: #3fb950; margin: 0 2px;">➔</span> <span style="color: #56d364; font-weight: bold;">${{escapeHtml(currRepr)}}</span>`;
                        }}
                        memoryDiv.innerHTML += `
                            <div class="var-card ${{flashClass}}">
                                <div class="var-header">
                                    <span class="var-name">${{key}}</span>
                                    <span class="var-scope">${{scope}}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 4px;">
                                    <div class="var-value">${{valDisplay}}</div>
                                    <span class="var-type">${{valType}}</span>
                                </div>
                            </div>
                        `;
                    }}
                }});

                if (!hasScalars) {{
                    memoryDiv.innerHTML = `<div style="color: #8b949e; font-style: italic; font-size: 12px; padding: 4px 0;">No scalar variables in scope.</div>`;
                }}
                if (!hasStructures) {{
                    structuresDiv.innerHTML = `<div style="color: #8b949e; font-style: italic; font-size: 12px; padding: 4px 0;">No complex data structures in scope.</div>`;
                }}

                // 7. Render Stack Frames
                const stackDiv = document.getElementById("stack-container");
                stackDiv.innerHTML = "";
                if (step.call_stack && step.call_stack.length > 0) {{
                    step.call_stack.forEach((frame, idx) => {{
                        const isActive = (idx === 0);
                        const frameClass = isActive ? "stack-frame active-frame" : "stack-frame";
                        const depthIndicator = step.call_stack.length - idx;
                        stackDiv.innerHTML += `
                            <div class="${{frameClass}}">
                                <div>
                                    <span class="stack-frame-name" style="color: ${{isActive ? '#58a6ff' : '#8b949e'}}">${{escapeHtml(frame.signature)}}</span>
                                    <div style="font-size: 9px; color: #8b949e; margin-top: 2px;">Frame depth: ${{depthIndicator}}</div>
                                </div>
                                <div style="font-size: 11px; color: #8b949e;">Line ${{frame.line}}</div>
                            </div>
                        `;
                    }});
                }} else {{
                    stackDiv.innerHTML = `<div style="color: #8b949e; font-style: italic; font-size: 12px;">Call stack is empty.</div>`;
                }}

                // 8. Render Console Output
                const consoleBox = document.getElementById("console-box");
                if (step.output) {{
                    consoleBox.innerText = step.output;
                }} else {{
                    consoleBox.innerHTML = `<span style="color: #8b949e; font-style: italic;">(No output printed yet)</span>`;
                }}
                consoleBox.scrollTop = consoleBox.scrollHeight;

                // 9. Update control statuses
                document.getElementById("btn-prev").disabled = (index === 0);
                document.getElementById("btn-next").disabled = (index === steps.length - 1);
                document.getElementById("step-indicator").innerText = "Step " + (index + 1) + " / " + steps.length;
                document.getElementById("timeline-slider").value = index + 1;
            }}

            // Playback Actions
            function handlePlay() {{
                if (isPlaying) return;
                isPlaying = true;
                document.getElementById("btn-play").style.display = "none";
                document.getElementById("btn-pause").style.display = "inline-flex";
                runPlaybackLoop();
            }}

            function handlePause() {{
                isPlaying = false;
                if (playbackTimeout) {{
                    clearTimeout(playbackTimeout);
                    playbackTimeout = null;
                }}
                document.getElementById("btn-play").style.display = "inline-flex";
                document.getElementById("btn-pause").style.display = "none";
            }}

            function runPlaybackLoop() {{
                if (!isPlaying) return;
                if (currentStepIndex < steps.length - 1) {{
                    goToStep(currentStepIndex + 1);
                    const delay = 1000 / playbackSpeed;
                    playbackTimeout = setTimeout(runPlaybackLoop, delay);
                }} else {{
                    handlePause();
                }}
            }}

            function handlePrev() {{
                handlePause();
                if (currentStepIndex > 0) {{
                    goToStep(currentStepIndex - 1);
                }}
            }}

            function handleNext() {{
                handlePause();
                if (currentStepIndex < steps.length - 1) {{
                    goToStep(currentStepIndex + 1);
                }}
            }}

            function handleRestart() {{
                handlePause();
                goToStep(0);
            }}

            // Run application initialization on load
            window.addEventListener("DOMContentLoaded", initializeApp);
        </script>
    </body>
    </html>
    """

    # 4. Render HTML element in Streamlit with proper height
    components.html(visualizer_html, height=760, scrolling=False)
