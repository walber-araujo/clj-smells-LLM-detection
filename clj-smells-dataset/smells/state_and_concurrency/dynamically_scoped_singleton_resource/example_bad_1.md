## Metadata

* **Smell name:** dynamically_scoped_singleton_resource
* **Expected smell location:** Top-level def `*db-connection*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Threading a critical resource like a DB connection via dynamic bindings implicitly hides dependencies and makes the system harder to test.

```Clojure
(ns app.db.core)

; VALIDATION: SMELL START - dynamically_scoped_singleton_resource
; VALIDATION: Using dynamic scope to thread a singleton resource (DB connection)
(def ^:dynamic *db-connection* nil)
; VALIDATION: SMELL END

(defn fetch-users []
  (when-not *db-connection*
    (throw (ex-info "No DB connection!" {})))
  [{:id 1 :name "Alice"}])

(defn handle-request
  [req pool]
  (binding [*db-connection* pool]
    (fetch-users)))
```
