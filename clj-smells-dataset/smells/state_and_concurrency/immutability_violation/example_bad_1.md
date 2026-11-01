## Metadata

* **Smell name:** immutability_violation
* **Expected smell location:** Function `update-user!`
* **Affected forms:** `defn`, `def`
* **Short explanation:** Using `def` inside a function to reassign a top-level var mutates global state and violates Clojure's immutability principles.

```Clojure
(ns app.user-registry)

(def users {})

(defn update-user!
  [user]
  ; VALIDATION: SMELL START - immutability_violation
  ; VALIDATION: Reassigning a top-level var with def inside a function
  (def users (assoc users (:id user) user)))
  ; VALIDATION: SMELL END
```
