## Metadata

* **Smell name:** dynamically_scoped_singleton_resource
* **Expected smell location:** Top-level def `*http-client*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Threading a critical resource like an HTTP client via dynamic bindings implicitly hides dependencies and makes the system harder to test.

```Clojure
(ns app.http.services)

; VALIDATION: SMELL START - dynamically_scoped_singleton_resource
; VALIDATION: Using dynamic scope to thread a singleton resource (HTTP client)
(def ^:dynamic *http-client* nil)
; VALIDATION: SMELL END

(defn get-external-data [url]
  ;; Uses *http-client* implicitly
  (println "Fetching" url "with" *http-client*)
  {:status 200})

(defn process-task
  [client url]
  (binding [*http-client* client]
    (get-external-data url)))
```
