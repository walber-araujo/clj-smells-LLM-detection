## Metadata

* **Smell name:** misuse_of_dynamic_scope
* **Expected smell location:** Top-level def `*current-request*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Using dynamic scope for ordinary application data like request data makes data flow implicit and harder to reason about.

```Clojure
(ns app.web.request)

; VALIDATION: SMELL START - misuse_of_dynamic_scope
; VALIDATION: Using dynamic scope for ordinary application data (HTTP request)
(def ^:dynamic *current-request* nil)
; VALIDATION: SMELL END

(defn get-header
  [header-name]
  (get-in *current-request* [:headers header-name]))

(defn middleware-logger
  [handler]
  (fn [req]
    (binding [*current-request* req]
      (println "User Agent:" (get-header "user-agent"))
      (handler req))))
```
