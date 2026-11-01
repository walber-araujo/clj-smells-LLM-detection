## Metadata

* **Smell name:** immutability_violation
* **Expected smell location:** Function `register-user!`
* **Affected forms:** `defn`, `atom`, `swap!`
* **Short explanation:** Replacing global mutable state with an atom makes state changes explicit and thread-safe.

```Clojure
(ns app.user-registry)

(def users (atom {}))

(defn register-user!
  [username profile]
  (swap! users assoc username profile))
```
