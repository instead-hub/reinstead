KEYWORDS = {
    "return", "not", "and", "or", "if", "elseif", "while", "until", "in",
    "then", "else", "do", "local", "function", "end", "break", "repeat",
    "when", "default",
}

TYPES = {"obj", "str", "num", "bool", "any", "event", "tbl", "list", "fn"}

PARAM_TYPES = {
    "s": "obj", "w": "obj", "wh": "obj", "ev": "event", "to": "any",
    "f": "any", "load": "bool",
}

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
        self.ref_fields = set()
        self.props = {}
        self.scoped = {}
        self.prop_params = {}
        self.inline = {}
        self.types = {}
        self.enum_values = {}
        self.classes = set()
        self.class_parents = {}
        self.id_kind = {}
        self.fields = {}
        self.current_owner = None
        self.src_dir = src_dir
