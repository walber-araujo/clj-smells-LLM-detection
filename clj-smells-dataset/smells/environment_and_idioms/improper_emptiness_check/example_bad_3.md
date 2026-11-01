## Metadata

* **Smell name:** Improper Emptiness Check
* **Expected smell location:** Function `process-items`
* **Affected forms:** `empty?`
* **Short explanation:** Using `(not (empty? coll))` or `(when-not (empty? coll) ...)` is unidiomatic and slower than using `seq`.

```Clojure
(ns report.generator)

(defn generate [data]
  ; VALIDATION: SMELL START - Improper Emptiness Check
  ; VALIDATION: not empty? check
  (cond
    (not (empty? data)) (println "Generating...")
    :else (println "Done")))
  ; VALIDATION: SMELL END
```
