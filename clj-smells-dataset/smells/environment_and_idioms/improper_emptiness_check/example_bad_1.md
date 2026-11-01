## Metadata

* **Smell name:** Improper Emptiness Check
* **Expected smell location:** Function `process-items`
* **Affected forms:** `empty?`
* **Short explanation:** Using `(not (empty? coll))` or `(when-not (empty? coll) ...)` is unidiomatic and slower than using `seq`.

```Clojure
(ns data.processor)

(defn process-items [items]
  ; VALIDATION: SMELL START - Improper Emptiness Check
  ; VALIDATION: Using (not (empty? ...)) instead of (seq ...)
  (if (not (empty? items))
    (println "Processing" (count items) "items")
    (println "No items to process")))
  ; VALIDATION: SMELL END
```
