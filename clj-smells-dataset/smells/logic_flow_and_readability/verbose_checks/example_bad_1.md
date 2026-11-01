## Metadata

* **Smell name:** verbose_checks
* **Expected smell location:** Function `process-batch`
* **Affected forms:** `if`, `=`, `count`
* **Short explanation:** Uses `(= (count coll) 0)` instead of the idiomatic `(empty? coll)`.

```Clojure
(ns batch.processor)

(defn process-batch [items]
  ; VALIDATION: SMELL START - verbose_checks
  ; VALIDATION: Checking for empty collection using (= (count coll) 0) instead of empty?
  (if (= (count items) 0)
    (log/info "No items to process")
    (do-process items)))
  ; VALIDATION: SMELL END
```
