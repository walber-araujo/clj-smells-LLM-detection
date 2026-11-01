## Metadata

* **Smell name:** thread_ignorance
* **Expected smell location:** Function `calculate-metrics`
* **Affected forms:** Nested function calls
* **Short explanation:** Deeply nested function calls that read inside-out, which is hard to parse compared to a threading macro.

```Clojure
(ns data.metrics)

(defn calculate-metrics [data]
  ; VALIDATION: SMELL START - thread_ignorance
  ; VALIDATION: Deeply nested calls that should use ->> for readability
  (reduce + (map :score (filter :valid? (remove nil? data)))))
  ; VALIDATION: SMELL END
```
