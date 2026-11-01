## Metadata

* **Smell name:** verbose_checks
* **Expected smell location:** Function `valid-balance?`
* **Affected forms:** `pos?`
* **Short explanation:** Refactored to use the idiomatic pos? function.

```Clojure
(ns bank.account)

(defn valid-balance? [balance]
  (pos? balance))
```
