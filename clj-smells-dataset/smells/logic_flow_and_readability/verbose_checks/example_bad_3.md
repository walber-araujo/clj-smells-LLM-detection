## Metadata

* **Smell name:** verbose_checks
* **Expected smell location:** Function `handle-decrement`
* **Affected forms:** `when`, `=`
* **Short explanation:** Uses `(= n 0)` instead of `(zero? n)`.

```Clojure
(ns counter.logic)

(defn handle-decrement [current-value]
  ; VALIDATION: SMELL START - verbose_checks
  ; VALIDATION: Checking for zero using (= n 0) instead of zero?
  (when (= current-value 0)
    (trigger-alarm!))
  (dec current-value))
  ; VALIDATION: SMELL END
```
