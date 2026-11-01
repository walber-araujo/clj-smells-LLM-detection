## Metadata

* **Smell name:** immutability_violation
* **Expected smell location:** Function `update-config`
* **Affected forms:** `defn`, `def`
* **Short explanation:** Using `def` inside a function to reassign a top-level var mutates global state and violates Clojure's immutability principles.

```Clojure
(ns app.config-manager)

(def app-config {:theme "light" :language "en"})

(defn update-config
  [k v]
  ; VALIDATION: SMELL START - immutability_violation
  ; VALIDATION: Reassigning a top-level var with def inside a function
  (def app-config (assoc app-config k v)))
  ; VALIDATION: SMELL END
```
