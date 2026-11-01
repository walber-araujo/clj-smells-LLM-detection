## Metadata

* **Smell name:** dynamically_scoped_singleton_resource
* **Expected smell location:** Top-level def `*redis-client*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Threading a critical resource like a Redis client via dynamic bindings implicitly hides dependencies and makes the system harder to test.

```Clojure
(ns app.cache.redis)

; VALIDATION: SMELL START - dynamically_scoped_singleton_resource
; VALIDATION: Using dynamic scope to thread a singleton resource (Redis client)
(def ^:dynamic *redis-client* nil)
; VALIDATION: SMELL END

(defn cache-set [k v]
  (println "Setting" k "to" v "in Redis using" *redis-client*))

(defn update-profile
  [redis-conn id profile]
  (binding [*redis-client* redis-conn]
    (cache-set (str "user:" id) profile)))
```
