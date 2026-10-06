import re

KEYWORDS = {
    "return", "not", "and", "or", "if", "elseif", "while", "until", "in",
    "then", "else", "do", "local", "function", "end", "break", "repeat",
}

TYPES = {"obj", "str", "num", "bool", "any", "event", "tbl"}

PARAM_TYPES = {
    "s": "obj", "w": "obj", "wh": "obj", "ev": "event", "to": "any",
    "f": "any", "load": "bool",
}

USE_RE = re.compile(r"^use\s+([\w.+-]+)$")


class Ctx:
    """Per-transpile state: ids, signatures, vars, events, source dir."""

    def __init__(self, src_dir=""):
        self.ids = set()
        self.vars = set()
        self.funcs = set()
        self.fns = set()
        self.fn_sigs = {}
        self.global_types = {}
        self.event_names = set()
        self.extra_events = {}
        self.wrappers = {}
        self.exprs = {}
        self.types = {}
        self.field_types = {}
        self.ref_fields = {}
        self.current_class = None
        self.adapters = {}
        self.src_dir = src_dir
