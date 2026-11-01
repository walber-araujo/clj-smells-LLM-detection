## Metadata

* **Smell name:** Improper Emptiness Check
* **Expected smell location:** Function `process-items`
* **Affected forms:** `empty?`
* **Short explanation:** Using `(not (empty? coll))` or `(when-not (empty? coll) ...)` is unidiomatic and slower than using `seq`.

```Clojure
(ns api.handler)

(defn handle-request [req]
  (let [params (:params req)]
    ; VALIDATION: SMELL START - Improper Emptiness Check
    ; VALIDATION: when-not (empty? ...) is better expressed as when (seq ...)
    (when-not (empty? params)
      (println "Has params:" params))))
    ; VALIDATION: SMELL END
```
