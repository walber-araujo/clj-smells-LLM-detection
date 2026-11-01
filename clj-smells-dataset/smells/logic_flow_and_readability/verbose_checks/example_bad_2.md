## Metadata

* **Smell name:** verbose_checks
* **Expected smell location:** Function `valid-balance?`
* **Affected forms:** `>`
* **Short explanation:** Uses `(> balance 0)` rather than the more concise `(pos? balance)`.

```Clojure
(ns bank.account)

(defn valid-balance? [balance]
  ; VALIDATION: SMELL START - verbose_checks
  ; VALIDATION: Checking for positive number using (> n 0) instead of pos?
  (> balance 0))
  ; VALIDATION: SMELL END
```
