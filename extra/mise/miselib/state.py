import re

IDS = set()

KEYWORDS = {
    "return", "not", "and", "or", "if", "elseif", "while", "until", "in",
    "then", "else", "do", "local", "function", "end", "break", "repeat",
}

VARS = set()

FUNCS = set()

EVENT_NAMES = set()

SRC_DIR = ""

TYPES = {"obj", "str", "num", "bool", "any", "event"}

FN_SIGS = {}

GLOBAL_TYPES = {}

PARAM_TYPES = {
    "s": "obj", "w": "obj", "wh": "obj", "ev": "event", "to": "any",
    "f": "any", "load": "bool",
}

EXTRA_EVENTS = {}

FNS = set()

USE_RE = re.compile(r"^use\s+([\w.+-]+)$")
