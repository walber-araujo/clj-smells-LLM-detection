## Metadata

* **Smell name:** Multiple Evaluation in Macros
* **Expected smell location:** Macro `unless`, `time-it`
* **Affected forms:** `defmacro`
* **Short explanation:** A macro that evaluates an argument more than once can cause unexpected side effects or performance issues if the argument expression does work.

```Clojure
(ns utils.bench)

(defmacro time-it [expr]
  ; VALIDATION: SMELL START - Multiple Evaluation in Macros
  ; VALIDATION: 'expr' is evaluated twice: once to check result, once to return
  `(let [start# (System/nanoTime)
         res# ~expr
         end# (System/nanoTime)]
     (println "Time taken:" (- end# start#))
     (if res#
       ~expr
       nil)))
  ; VALIDATION: SMELL END
```
