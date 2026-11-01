## Metadata

* **Smell name:** Improper Emptiness Check
* **Expected smell location:** Function `process-items`
* **Affected forms:** `empty?`
* **Short explanation:** Use `(seq coll)` or `(when (seq coll) ...)` to check if a collection is non-empty.

```Clojure
(ns api.handler)

(defn handle-request [req]
  (let [params (:params req)]
    (when (seq params)
      (println "Has params:" params))))
```
