## Metadata

* **Smell name:** redundant_do_block
* **Expected smell location:** Macro `with-timing`
* **Affected forms:** `try`, `do`
* **Short explanation:** Uses a do block inside a try block, which already evaluates multiple expressions sequentially.

```Clojure
(ns utils.profiler)

(defn execute-with-metrics [f]
  (try
    ; VALIDATION: SMELL START - redundant_do_block
    ; VALIDATION: try already provides an implicit do block
    (do
      (log/info "Starting execution")
      (let [result (f)]
        (log/info "Execution finished")
        result))
    ; VALIDATION: SMELL END
    (catch Exception e
      (log/error "Execution failed" e))))
```
