## Metadata

* **Smell name:** Multiple Evaluation in Macros
* **Expected smell location:** Macro `unless`, `time-it`
* **Affected forms:** `defmacro`
* **Short explanation:** A macro that evaluates an argument more than once can cause unexpected side effects or performance issues if the argument expression does work.

```Clojure
(ns utils.assert)

(defmacro assert-pos [n]
  ; VALIDATION: SMELL START - Multiple Evaluation in Macros
  ; VALIDATION: 'n' is evaluated multiple times
  `(if (> ~n 0)
     ~n
     (throw (ex-info "Not positive" {:val ~n}))))
  ; VALIDATION: SMELL END
```
