## Metadata

* **Smell name:** Unnecessary Macros
* **Expected smell location:** Macro `log-info`, `validate`
* **Affected forms:** `defmacro`
* **Short explanation:** Using a macro when a function would suffice makes the code harder to compose, test, and apply to sequences.

```Clojure
(ns math.utils)

; VALIDATION: SMELL START - Unnecessary Macros
; VALIDATION: Macro used for a simple arithmetic wrapper
(defmacro add-ten [x]
  `(+ ~x 10))
; VALIDATION: SMELL END
```
