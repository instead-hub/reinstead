;;; mise-mode.el --- Major mode for the mise DSL  -*- lexical-binding: t; -*-

;; Author: opencode
;; Keywords: languages
;; Package-Requires: ((emacs "25.1"))
;; Version: 0.1

;;; Commentary:

;; Font-lock support for mise, the DSL of extra/mise (mise.py).
;; It mirrors extra/mise/vim/syntax/mise.vim.  Install:
;;
;;   (add-to-list 'load-path "/path/to/rein/extra/mise/emacs")
;;   (require 'mise-mode)
;;
;; or with use-package:
;;
;;   (use-package mise-mode
;;     :load-path "/path/to/rein/extra/mise/emacs")

;;; Code:

(require 'font-lock)

(defgroup mise nil
  "Major mode for the mise DSL."
  :group 'languages)

(defun mise--words (words)
  "A symbol-bounded regexp for WORDS, without capturing groups."
  (concat "\\_<\\(?:" (mapconcat #'regexp-quote words "\\|") "\\)\\_>"))

(defconst mise--declarations
  (mise--words '("obj" "scenery" "room" "door" "story" "ending" "class"
                 "mixin" "verb" "talk" "setup" "impl" "props" "refs"
                 "const" "global" "event" "type" "extend" "fn" "lua"))
  "The section declarations of the mise language.")

(defconst mise--logic
  (mise--words '("if" "elseif" "else" "when" "default" "for" "local"
                 "return" "break" "stop" "pass"))
  "The keywords of the mise logic blocks.")

(defconst mise--special
  (mise--words '("words" "word" "attrs" "dict" "disabled" "with"
                 "inside" "text" "found_in"))
  "The mise field keys with a meaning of their own.")

(defconst mise--phases
  (mise--words '("on" "life" "before" "after" "post"))
  "The phases of the mise event handlers.")

(defconst mise--types
  (mise--words '("obj" "str" "num" "bool" "any" "event" "tbl" "ref"
                 "fn"))
  "The value types of the mise language.")

(defconst mise--directives
  (mise--words '("name" "version" "author" "info" "lang" "fmt"
                 "include" "require"))
  "The top-level directives of a mise file.")

(defconst mise--operators (mise--words '("and" "or" "not" "in"))
  "The logic operators of the mise language.")

(defconst mise--constants (mise--words '("true" "false" "nil"))
  "The literals of the mise language.")

(defconst mise--todos (mise--words '("TODO" "FIXME" "XXX"))
  "The markers of things to do.")

(defconst mise--name "[[:word:]_]+"
  "The regexp of a mise identifier.")

(defvar mise-font-lock-keywords
  `(;; the section declarations of the line start
    (,(concat "^[ \t]*\\(" mise--declarations "\\)")
     (1 font-lock-keyword-face))
    ;; the top-level directives
    (,(concat "^[ \t]*\\(" mise--directives "\\)[ \t]*:")
     (1 font-lock-preprocessor-face))
    ;; the logic keywords
    (,(concat "^[ \t]*\\(" mise--logic "\\)")
     (1 font-lock-keyword-face))
    ;; the special field keys
    (,(concat "^[ \t]*\\(" mise--special "\\)[ \t]*[:(]")
     (1 font-lock-type-face))
    ;; the phases
    (,(concat "^[ \t]*\\(" mise--phases "\\)[ \t]+[A-Z]")
     (1 font-lock-keyword-face))
    ;; the event names of a phase, the whole comma list at once
    (,(concat "^[ \t]*" mise--phases "[ \t]+"
              "\\([A-Z][[:word:]_]*\\(?:[ \t]*,[ \t]*[A-Z][[:word:]_]*\\)*\\)")
     (1 font-lock-function-name-face))
    ;; the name of an event, an implementation or a "use" reference
    (,(concat "^[ \t]*event[ \t]+\\([A-Z][[:word:]_]*\\)")
     (1 font-lock-function-name-face))
    (,(concat "^[ \t]*impl[ \t]+\\([^ \t:\n]+\\)")
     (1 font-lock-function-name-face))
    (,(concat "^[ \t]*extend[ \t]+\\(refs\\|type\\)\\_>")
     (1 font-lock-keyword-face))
    (,(concat "\\_<use[ \t]+\\(" mise--name "\\)")
     (1 font-lock-function-name-face))
    ;; a function value "&name"
    (,(concat "&" mise--name) . font-lock-function-name-face)
    ;; a type after ":" "," "(" "|" "[" "]" or "->"
    (,(concat "\\(?:[:,(|]\\|\\[\\|\\]\\|->\\)[ \t]*\\(" mise--types "\\)")
     (1 font-lock-type-face))
    ;; the arrows and the block markers
    ("->" . font-lock-builtin-face)
    ("|\\(?:lua\\)?[ \t]*$" . font-lock-builtin-face)
    (,mise--operators . font-lock-builtin-face)
    ;; the references and the literals
    ("\\(?:^\\|[ \t]\\)\\(#[^][ \t:,()|{}.#]+\\)"
     (1 font-lock-constant-face))
    (,mise--constants . font-lock-constant-face)
    ("\\(?:^\\|[^[:alnum:]_]\\)\\([-+]?[0-9]+\\(?:\\.[0-9]+\\)?\\)\\_>"
     (1 font-lock-constant-face))
    (,mise--todos . font-lock-warning-face)
    ;; a field key: at the line start, a word followed by ":" or "("
    (,(concat "^[ \t]*\\(" mise--name "\\)[ \t]*[:(]")
     (1 font-lock-variable-name-face)))
  "Font-lock expressions of `mise-mode'.")

(defvar mise-mode-syntax-table
  (let ((st (make-syntax-table prog-mode-syntax-table)))
    (modify-syntax-entry ?\" "\"" st)
    (modify-syntax-entry ?\' "\"" st)
    (modify-syntax-entry ?` "\"" st)
    (modify-syntax-entry ?\\ "\\" st)
    (modify-syntax-entry ?\n ">" st)
    (modify-syntax-entry ?# "." st)
    st)
  "Syntax table of `mise-mode'.")

(defun mise-syntax-propertize (start end)
  "Mark the comments and the long strings of mise between START and END.

A comment is a \"#\" at the line start or a separate word, to the
end of the line; a long string is [[...]], [=[...]=] or
[==[...]==]."
  (save-excursion
    (goto-char start)
    (while (re-search-forward "\\(?:^\\|[ \t]\\)\\(#\\)\\(?:[ \t]\\|$\\)"
                              end t)
      (put-text-property (match-beginning 1) (match-end 1)
                         'syntax-table (string-to-syntax "<")))
    (goto-char start)
    (while (re-search-forward "\\[\\(=\\{0,2\\}\\)\\[" end t)
      (put-text-property (match-beginning 0) (1+ (match-beginning 0))
                         'syntax-table (string-to-syntax "|"))
      (let ((close (concat "]" (match-string-no-properties 1) "]")))
        (when (search-forward close end t)
          (put-text-property (1- (match-end 0)) (match-end 0)
                             'syntax-table (string-to-syntax "|")))))))

;;;###autoload
(define-derived-mode mise-mode prog-mode "mise"
  "Major mode for editing mise files.

The mise DSL is compiled by extra/mise/mise.py; see SPEC.md."
  :group 'mise
  :syntax-table mise-mode-syntax-table
  (setq-local font-lock-defaults '(mise-font-lock-keywords))
  (setq-local syntax-propertize-function #'mise-syntax-propertize)
  (setq-local parse-sexp-lookup-properties t)
  (setq-local comment-start "# ")
  (setq-local comment-end "")
  (setq-local comment-start-skip "\\(?:^\\|[ \t]\\)#+[ \t]*")
  (setq-local comment-use-syntax t)
  (setq-local indent-tabs-mode nil)
  (setq-local tab-width 2))

;;;###autoload
(add-to-list 'auto-mode-alist '("\\.mise\\'" . mise-mode))

(provide 'mise-mode)

;;; mise-mode.el ends here
