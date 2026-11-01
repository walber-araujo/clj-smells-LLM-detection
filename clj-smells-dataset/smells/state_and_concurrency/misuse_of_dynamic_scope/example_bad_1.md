## Metadata

* **Smell name:** misuse_of_dynamic_scope
* **Expected smell location:** Top-level def `*current-user*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Using dynamic scope for ordinary application data like the current user makes data flow implicit and harder to reason about.

```Clojure
(ns app.web.user)

; VALIDATION: SMELL START - misuse_of_dynamic_scope
; VALIDATION: Using dynamic scope for ordinary application data (current user)
(def ^:dynamic *current-user* nil)
; VALIDATION: SMELL END

(defn process-checkout
  [cart]
  (if *current-user*
    (println "Checking out for" (:name *current-user*))
    (println "Guest checkout")))

(defn handle-request
  [req]
  (binding [*current-user* (:user req)]
    (process-checkout (:cart req))))
```
