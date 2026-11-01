## Metadata

* **Smell name:** Multiple Evaluation in Macros
* **Expected smell location:** Macro `unless`, `time-it`
* **Affected forms:** `defmacro`
* **Short explanation:** Macros should evaluate their arguments once by binding them to a gensym in a `let` block.

```Clojure
(ns utils.bench)

(defmacro time-it [expr]
  `(let [start# (System/nanoTime)
         res# ~expr
         end# (System/nanoTime)]
     (println "Time taken:" (- end# start#))
     res#))
```
