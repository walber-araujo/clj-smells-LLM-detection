## Metadata

* **Smell name:** Multiple Evaluation in Macros
* **Expected smell location:** Macro `unless`, `time-it`
* **Affected forms:** `defmacro`
* **Short explanation:** A macro that evaluates an argument more than once can cause unexpected side effects or performance issues if the argument expression does work.

```Clojure
(ns utils.control
  (:require [clojure.tools.logging :as log]))

(defmacro unless [pred a b]
  ; VALIDATION: SMELL START - Multiple Evaluation in Macros
  ; VALIDATION: 'pred' is evaluated twice if it is false
  `(if (not ~pred)
     (do
       (log/info "Pred was false:" '~pred)
       ~b)
     ~a))
  ; VALIDATION: SMELL END
```
