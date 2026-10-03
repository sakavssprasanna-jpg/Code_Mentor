import sys
import time
import traceback
import ast

class ExecutionTracer:
    def __init__(self, code: str, stdin_data: str = ""):
        self.code = code
        self.stdin_data = stdin_data
        self.steps = []
        self.output_buffer = []
        self.start_time = 0.0
        self.limit_steps = 1000
        self.limit_time = 3.0
        self.limit_output = 10000
        self.error = None
        self.error_line = None
        self.error_type = None
        self.stdin_lines = stdin_data.splitlines()
        self.stdin_idx = 0
        self.source_lines = code.splitlines()

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

    def trace_callback(self, frame, event, arg):
        # 1. Timeout protection
        if time.time() - self.start_time > self.limit_time:
            raise TimeoutError(f"Execution exceeded the time limit of {self.limit_time} seconds.")
        
        # 2. Infinite loop / step limit protection
        if len(self.steps) >= self.limit_steps:
            raise RuntimeError(f"Execution exceeded the limit of {self.limit_steps} trace steps.")

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
                        # Reconstruct function signature arguments
                        args = []
                        # Number of arguments
                        arg_count = curr_frame.f_code.co_argcount
                        arg_names = curr_frame.f_code.co_varnames[:arg_count]
                        for name in arg_names:
                            if name in curr_frame.f_locals:
                                val_repr = self.value_repr(curr_frame.f_locals[name])
                                args.append(f"{name}={val_repr}")
                        func_sig = f"{func_name}({', '.join(args)})"
                    else:
                        func_sig = "<module>"
                        
                    call_stack.append({
                        "name": func_name,
                        "signature": func_sig,
                        "line": line_no
                    })
                curr_frame = curr_frame.f_back

            # Safely capture locals
            local_vars = {}
            for k, v in frame.f_locals.items():
                if k.startswith('__') or k == 'custom_input':
                    continue
                local_vars[k] = self.serialize_value(v)

            # Safely capture globals
            global_vars = {}
            for k, v in frame.f_globals.items():
                if k.startswith('__') or k in ('custom_input', 'input'):
                    continue
                # Skip modules, classes, and functions to keep variables list clean
                if type(v).__name__ not in ('module', 'function', 'classobj', 'type'):
                    global_vars[k] = self.serialize_value(v)

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

            output_so_far = "".join(self.output_buffer)
            if len(output_so_far) > self.limit_output:
                raise RuntimeError(f"Execution exceeded the limit of {self.limit_output} output characters.")

            # Record step state
            self.steps.append({
                "step": len(self.steps) + 1,
                "line": frame.f_lineno,
                "event": event,
                "locals": local_vars,
                "globals": global_vars,
                "call_stack": call_stack,
                "output": output_so_far,
                "exception": exception_info,
                "return_value": return_value
            })

        return self.trace_callback

    def serialize_value(self, val, depth=0):
        """Helper to create a deep-copy safe representation of any value."""
        if depth > 3:
            return {
                "type": "truncated",
                "value": "...",
                "repr": "..."
            }
            
        type_name = type(val).__name__
        try:
            if isinstance(val, (int, float, str, bool)) or val is None:
                return {
                    "type": type_name,
                    "value": val,
                    "repr": repr(val)
                }
            elif isinstance(val, list):
                elements = [self.serialize_value(item, depth + 1) for item in val[:100]]
                return {
                    "type": "list",
                    "value": elements,
                    "repr": repr(val)
                }
            elif isinstance(val, dict):
                items = {}
                for k, v in list(val.items())[:100]:
                    items[str(k)] = self.serialize_value(v, depth + 1)
                return {
                    "type": "dict",
                    "value": items,
                    "repr": repr(val)
                }
            elif isinstance(val, set):
                elements = [self.serialize_value(item, depth + 1) for item in list(val)[:100]]
                return {
                    "type": "set",
                    "value": elements,
                    "repr": repr(val)
                }
            elif isinstance(val, tuple):
                elements = [self.serialize_value(item, depth + 1) for item in val[:100]]
                return {
                    "type": "tuple",
                    "value": elements,
                    "repr": repr(val)
                }
            elif hasattr(val, "__dict__"):
                attrs = {}
                for k, v in list(val.__dict__.items())[:50]:
                    if not k.startswith('_'):
                        attrs[k] = self.serialize_value(v, depth + 1)
                return {
                    "type": f"object:{type_name}",
                    "value": attrs,
                    "repr": repr(val)
                }
            else:
                return {
                    "type": type_name,
                    "value": str(val),
                    "repr": repr(val)
                }
        except Exception as e:
            return {
                "type": type_name,
                "value": f"<unserializable: {str(e)}>",
                "repr": "<unserializable>"
            }

    def value_repr(self, val):
        try:
            if isinstance(val, str):
                if len(val) > 20:
                    return repr(val[:17] + "...")
                return repr(val)
            return repr(val)
        except Exception:
            return "<unrepresentable>"

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

            # Add an error step to the trace
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
