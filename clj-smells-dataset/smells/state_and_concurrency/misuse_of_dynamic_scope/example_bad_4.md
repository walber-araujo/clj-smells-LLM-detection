## Metadata

* **Smell name:** misuse_of_dynamic_scope
* **Expected smell location:** Top-level def `*active-job*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Using dynamic scope for ordinary application data like an active job makes data flow implicit and harder to reason about.

```Clojure
(ns app.worker.job)

; VALIDATION: SMELL START - misuse_of_dynamic_scope
; VALIDATION: Using dynamic scope for ordinary application data (active job)
(def ^:dynamic *active-job* nil)
; VALIDATION: SMELL END

(defn execute-step
  [step]
  (println "Executing" step "for job" (:id *active-job*)))

(defn run-job
  [job]
  (binding [*active-job* job]
    (doseq [step (:steps job)]
      (execute-step step))))
```
