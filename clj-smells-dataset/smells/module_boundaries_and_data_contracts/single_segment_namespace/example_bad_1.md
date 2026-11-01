## Metadata

* **Smell name:** single_segment_namespace
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`
* **Short explanation:** Using a single-segment namespace (e.g., `utils` instead of `myapp.utils`) can cause collisions with other libraries or built-in Java packages.

```Clojure
; VALIDATION: SMELL START - single_segment_namespace
; VALIDATION: namespace has only a single segment, which can lead to collisions
(ns utils)
; VALIDATION: SMELL END

(defn wrap-error [f]
  (try
    (f)
    (catch Exception e {:error (.getMessage e)})))
```
