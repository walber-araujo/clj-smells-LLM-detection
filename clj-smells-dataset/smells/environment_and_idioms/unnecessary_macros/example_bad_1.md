## Metadata

* **Smell name:** Unnecessary Macros
* **Expected smell location:** Macro `log-info`, `validate`
* **Affected forms:** `defmacro`
* **Short explanation:** Using a macro when a function would suffice makes the code harder to compose, test, and apply to sequences.

```Clojure
(ns logging.core)

; VALIDATION: SMELL START - Unnecessary Macros
; VALIDATION: This macro does not need to control evaluation and can just be a function
(defmacro log-info [msg]
  `(println "[INFO]" ~msg))
; VALIDATION: SMELL END

(defn process []
  (log-info "Starting process"))
```
