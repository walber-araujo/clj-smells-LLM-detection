## Metadata

* **Smell name:** Improper Emptiness Check
* **Expected smell location:** Function `process-items`
* **Affected forms:** `empty?`
* **Short explanation:** Use `(seq coll)` or `(when (seq coll) ...)` to check if a collection is non-empty.

```Clojure
(ns data.processor)

(defn process-items [items]
  (if (seq items)
    (println "Processing" (count items) "items")
    (println "No items to process")))
```
