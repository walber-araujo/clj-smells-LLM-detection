## Metadata

* **Smell name:** verbose_checks
* **Expected smell location:** Function `process-batch`
* **Affected forms:** `empty?`
* **Short explanation:** Refactored to use the idiomatic empty? function.

```Clojure
(ns batch.processor)

(defn process-batch [items]
  (if (empty? items)
    (log/info "No items to process")
    (do-process items)))
```
