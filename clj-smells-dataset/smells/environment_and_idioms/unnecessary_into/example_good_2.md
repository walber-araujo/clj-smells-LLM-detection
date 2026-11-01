## Metadata

* **Smell name:** Unnecessary into
* **Expected smell location:** Function `process`
* **Affected forms:** `into`
* **Short explanation:** Use `vec`, `set`, or `update-vals` instead of `into` for simpler conversions.

```Clojure
(ns users.permissions)

(defn get-roles [user]
  (set (:roles user)))
```
