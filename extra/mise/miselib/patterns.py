"""Named regex fragments and compiled patterns of the compiler."""
import re

DSL_NAME = r"[^\W\d]\w*"
LUA_NAME = r"[A-Za-z_]\w*"
CLASS_NAME = r"[A-Z]\w*"
PARAM_REF = r"(?<![\w.])%s(?![\w])"

DSL_RE = re.compile(DSL_NAME)
CLASS_RE = re.compile(CLASS_NAME)
REF_RE = re.compile(r"[#@\w]+")
NONSPACE_RE = re.compile(r"\S+")
LONG_OPEN_RE = re.compile(r"\[(=*)\[")
IN_RE = re.compile(r"\bin\b")
