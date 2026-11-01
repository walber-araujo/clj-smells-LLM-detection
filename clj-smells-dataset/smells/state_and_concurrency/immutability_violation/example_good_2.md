## Metadata

* **Smell name:** immutability_violation
* **Expected smell location:** Function `update-config`
* **Affected forms:** `defn`
* **Short explanation:** Returning the updated config without side effects promotes pure functions.

```Clojure
(ns app.config-manager)

(defn update-config
  [app-config k v]
  (assoc app-config k v))
```
