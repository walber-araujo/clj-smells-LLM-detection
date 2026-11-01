## Metadata

* **Smell name:** dynamically_scoped_singleton_resource
* **Expected smell location:** Top-level def `*file-handle*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Threading a critical resource like a file handle via dynamic bindings implicitly hides dependencies and makes the system harder to test.

```Clojure
(ns app.io.logger)

; VALIDATION: SMELL START - dynamically_scoped_singleton_resource
; VALIDATION: Using dynamic scope to thread a singleton resource (File handle)
(def ^:dynamic *file-handle* nil)
; VALIDATION: SMELL END

(defn log-message [msg]
  (spit *file-handle* (str msg "\n") :append true))

(defn do-work
  [file msg]
  (binding [*file-handle* file]
    (log-message msg)))
```
