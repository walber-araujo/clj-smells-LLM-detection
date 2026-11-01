## Metadata

* **Smell name:** single_segment_namespace
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`
* **Short explanation:** Using a single-segment namespace (e.g., `utils` instead of `myapp.utils`) can cause collisions with other libraries or built-in Java packages.

```Clojure
; VALIDATION: SMELL START - single_segment_namespace
; VALIDATION: single segment namespace
(ns db)
; VALIDATION: SMELL END

(def conn "jdbc:postgresql://localhost/mydb")
```
