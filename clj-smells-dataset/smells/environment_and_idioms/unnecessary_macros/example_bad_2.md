## Metadata

* **Smell name:** Unnecessary Macros
* **Expected smell location:** Macro `log-info`, `validate`
* **Affected forms:** `defmacro`
* **Short explanation:** Using a macro when a function would suffice makes the code harder to compose, test, and apply to sequences.

```Clojure
(ns validation.core)

; VALIDATION: SMELL START - Unnecessary Macros
; VALIDATION: Simple validation wrapper does not require a macro
(defmacro valid-age? [age]
  `(and (>= ~age 0) (<= ~age 120)))
; VALIDATION: SMELL END
```
