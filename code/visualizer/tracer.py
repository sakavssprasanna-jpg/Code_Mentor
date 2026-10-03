import sys
import time
import traceback
import ast

class StepLimitReached(Exception):
    """Raised to gracefully halt execution when trace limit is reached."""
    pass

class ExecutionTracer:
    """Memory-safe, resource-bounded execution tracer for Python code visualization."""

    def __init__(self, code: str, stdin_data: str = "", limit_steps: int = 2500):
        self.code = code
        self.stdin_data = stdin_data
        self.steps = []
        self.output_buffer = []
        self.start_time = 0.0
        self.limit_steps = limit_steps
        self.limit_time = 3.0
        self.limit_output = 10000
        self.error = None
        self.error_line = None
        self.error_type = None
        self.stdin_lines = stdin_data.splitlines()
        self.stdin_idx = 0
        self.source_lines = code.splitlines()

        # Caching & deduplication trackers to prevent memory explosion
        self._scalar_cache = {}
        self._last_output_len = 0
        self._last_output_str = ""
        self._last_globals = {}
        self._last_globals_fp = {}
        self._last_locals = {}
        self._last_locals_fp = {}
        self._step_limit_hit = False

    def custom_input(self, prompt=""):
        if prompt:
            self.output_buffer.append(str(prompt))
        if self.stdin_idx < len(self.stdin_lines):
            val = self.stdin_lines[self.stdin_idx]
            self.stdin_idx += 1
            self.output_buffer.append(val + "\n")
            return val
        else:
            raise EOFError("EOF when reading a line (no more input provided)")

    def serialize_scalar(self, val):
        """Serialize a primitive/scalar value with bounded memoization."""
        val_type = type(val)
        if val is None or val_type in (int, float, bool, str):
            cache_key = (val_type, val)
            cached = self._scalar_cache.get(cache_key)
            if cached is not None:
                return cached

            t = val_type.__name__
            r = repr(val)
            if len(r) > 50:
                r = r[:47] + "..."
            v = val if val_type in (int, float, bool) or val is None else str(val)[:60]
            entry = {"type": t, "value": v, "repr": r}

            if len(self._scalar_cache) < 600:
                self._scalar_cache[cache_key] = entry
            return entry

        t = val_type.__name__
        r = repr(val)
        if len(r) > 50:
            r = r[:47] + "..."
        return {"type": t, "value": str(val)[:50], "repr": r}

    def serialize_value(self, val, depth=0):
        """Creates a memory-safe, bounded representation of any variable."""
        if depth > 2:
            return {"type": "truncated", "value": "...", "repr": "..."}

        t = type(val).__name__
        if isinstance(val, (int, float, str, bool)) or val is None:
            return self.serialize_scalar(val)

        try:
            if isinstance(val, (list, tuple, set)):
                # Bounded to 50 items for UI responsiveness & memory safety
                raw_items = list(val)
                elements = [self.serialize_scalar(item) for item in raw_items[:50]]
                r = repr(val)
                if len(r) > 60:
                    r = r[:57] + "..."
                return {
                    "type": t,
                    "value": elements,
                    "repr": r
                }
            elif isinstance(val, dict):
                # Bounded to 30 keys
                items = {}
                for k, v in list(val.items())[:30]:
                    items[str(k)] = self.serialize_scalar(v)
                r = repr(val)
                if len(r) > 60:
                    r = r[:57] + "..."
                return {
                    "type": "dict",
                    "value": items,
                    "repr": r
                }
            elif hasattr(val, "__dict__"):
                attrs = {}
                for k, v in list(val.__dict__.items())[:20]:
                    if not k.startswith('_'):
                        attrs[k] = self.serialize_scalar(v)
                return {
                    "type": f"object:{t}",
                    "value": attrs,
                    "repr": repr(val)[:50]
                }
            else:
                r = repr(val)
                if len(r) > 50:
                    r = r[:47] + "..."
                return {
                    "type": t,
                    "value": str(val)[:50],
                    "repr": r
                }
        except Exception:
            return {"type": t, "value": "<unserializable>", "repr": "<unserializable>"}

    def _get_fingerprint(self, val):
        """Computes a lightweight fingerprint to detect variable mutations without deep copying."""
        if isinstance(val, (int, float, bool, str)) or val is None:
            return val
        if isinstance(val, (list, tuple, set)):
            # Fast structural fingerprint: length + repr of boundary items
            l = len(val)
            if l == 0:
                return (l, "")
            raw = list(val)
            return (l, repr(raw[0]), repr(raw[-1]))
        if isinstance(val, dict):
            l = len(val)
            return (l, tuple(list(val.keys())[:5]))
        return id(val)

    def capture_vars(self, current_dict, last_dict, last_fp):
        """Diff-based variable capture: reuses unchanged variable references to minimize allocations."""
        result = dict(last_dict)
        fp_cache = dict(last_fp)

        # Remove deleted variables
        for k in list(result.keys()):
            if k not in current_dict:
                del result[k]
                del fp_cache[k]

        for k, v in current_dict.items():
            if k.startswith('__') or k in ('custom_input', 'input'):
                continue
            if type(v).__name__ in ('module', 'function', 'classobj', 'type'):
                continue

            current_fp = self._get_fingerprint(v)
            prev_fp = fp_cache.get(k)

            # If unchanged, retain existing reference
            if prev_fp is not None and prev_fp == current_fp:
                continue

            # Variable changed or newly introduced
            result[k] = self.serialize_value(v)
            fp_cache[k] = current_fp

        return result, fp_cache

    def trace_callback(self, frame, event, arg):
        # 1. Timeout protection
        if time.time() - self.start_time > self.limit_time:
            raise TimeoutError(f"Execution exceeded the time limit of {self.limit_time} seconds.")

        # 2. Graceful step limit protection (halts execution cleanly to prevent infinite loops)
        if len(self.steps) >= self.limit_steps:
            raise StepLimitReached(f"Execution reached safe trace limit ({self.limit_steps} steps). Trace gracefully stopped.")

        # 3. Only trace frames from "<user_code>"
        if frame.f_code.co_filename != "<user_code>":
            return self.trace_callback

        if event in ('line', 'call', 'return', 'exception'):
            # Reconstruct call stack
            call_stack = []
            curr_frame = frame
            while curr_frame:
                if curr_frame.f_code.co_filename == "<user_code>":
                    func_name = curr_frame.f_code.co_name
                    line_no = curr_frame.f_lineno

                    if func_name != "<module>":
                        arg_count = curr_frame.f_code.co_argcount
                        arg_names = curr_frame.f_code.co_varnames[:arg_count]
                        args = []
                        for name in arg_names:
                            if name in curr_frame.f_locals:
                                r = repr(curr_frame.f_locals[name])
                                if len(r) > 20:
                                    r = r[:17] + "..."
                                args.append(f"{name}={r}")
                        func_sig = f"{func_name}({', '.join(args)})"
                    else:
                        func_sig = "<module>"

                    call_stack.append({
                        "name": func_name,
                        "signature": func_sig,
                        "line": line_no
                    })
                curr_frame = curr_frame.f_back

            # Diff-based variable capture: local namespace
            local_vars, self._last_locals_fp = self.capture_vars(
                frame.f_locals, self._last_locals, self._last_locals_fp
            )
            self._last_locals = local_vars

            # Global namespace: only re-evaluate at module frame or when modified
            if frame.f_code.co_name == "<module>":
                global_vars, self._last_globals_fp = self.capture_vars(
                    frame.f_globals, self._last_globals, self._last_globals_fp
                )
                self._last_globals = global_vars
            else:
                global_vars = self._last_globals

            # Exception info
            exception_info = None
            if event == 'exception' and arg:
                exc_type, exc_val, exc_tb = arg
                exception_info = {
                    "type": exc_type.__name__ if hasattr(exc_type, '__name__') else str(exc_type),
                    "message": str(exc_val)
                }

            # Return value
            return_value = None
            if event == 'return':
                return_value = self.serialize_value(arg)

            # Re-use output string buffer when unchanged
            if len(self.output_buffer) != self._last_output_len:
                self._last_output_str = "".join(self.output_buffer)
                self._last_output_len = len(self.output_buffer)
                if len(self._last_output_str) > self.limit_output:
                    raise RuntimeError(f"Execution exceeded the limit of {self.limit_output} output characters.")

            self.steps.append({
                "step": len(self.steps) + 1,
                "line": frame.f_lineno,
                "event": event,
                "locals": local_vars,
                "globals": global_vars,
                "call_stack": call_stack,
                "output": self._last_output_str,
                "exception": exception_info,
                "return_value": return_value
            })

        return self.trace_callback

    def run(self):
        old_stdout = sys.stdout

        class StdoutInterceptor:
            def __init__(self, tracer):
                self.tracer = tracer
            def write(self, data):
                self.tracer.output_buffer.append(data)
            def flush(self):
                pass

        sys.stdout = StdoutInterceptor(self)
        self.start_time = time.time()

        exec_globals = {
            "__builtins__": __builtins__,
            "input": self.custom_input,
        }

        try:
            compiled_code = compile(self.code, "<user_code>", "exec")
            sys.settrace(self.trace_callback)
            try:
                exec(compiled_code, exec_globals)
            finally:
                sys.settrace(None)
        except StepLimitReached as e:
            sys.settrace(None)
            self._step_limit_hit = True
            self.error = str(e)
            self.error_type = "StepLimitReached"
            last_output = "".join(self.output_buffer)
            self.steps.append({
                "step": len(self.steps) + 1,
                "line": self.steps[-1]["line"] if self.steps else 1,
                "event": "exception",
                "locals": self.steps[-1]["locals"] if self.steps else {},
                "globals": self.steps[-1]["globals"] if self.steps else {},
                "call_stack": self.steps[-1]["call_stack"] if self.steps else [],
                "output": last_output,
                "exception": {
                    "type": "StepLimitReached",
                    "message": str(e)
                },
                "return_value": None
            })
        except Exception as e:
            sys.settrace(None)
            exc_type, exc_val, exc_tb = sys.exc_info()
            tb = traceback.extract_tb(exc_tb)
            for frame in reversed(tb):
                if frame.filename == "<user_code>":
                    self.error_line = frame.lineno
                    break
            self.error = str(e)
            self.error_type = exc_type.__name__

            last_output = "".join(self.output_buffer)
            self.steps.append({
                "step": len(self.steps) + 1,
                "line": self.error_line or (self.steps[-1]["line"] if self.steps else 1),
                "event": "exception",
                "locals": self.steps[-1]["locals"] if self.steps else {},
                "globals": self.steps[-1]["globals"] if self.steps else {},
                "call_stack": self.steps[-1]["call_stack"] if self.steps else [],
                "output": last_output,
                "exception": {
                    "type": self.error_type,
                    "message": self.error
                },
                "return_value": None
            })
        finally:
            # Guarantees that sys.settrace is ALWAYS removed regardless of execution outcome
            sys.settrace(None)
            sys.stdout = old_stdout

        return self.steps


def validate_syntax(code: str):
    """Statically checks Python code for syntax errors. Returns (is_valid, error_msg, line_no)"""
    try:
        ast.parse(code)
        return True, None, None
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg}", e.lineno
    except Exception as e:
        return False, f"Error: {str(e)}", None
