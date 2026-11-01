## Metadata

* **Smell name:** Namespace Load Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `require`, `requiring-resolve`
* **Short explanation:** Using `require` as a top-level form outside the `ns` declaration breaks standard dependency tooling and makes the code harder to reason about.

```Clojure
(ns utils.math)

; VALIDATION: SMELL START - Namespace Load Side Effects
; VALIDATION: Top-level require for optional dependency
(try
  (require '[fast-math.core :as math])
  (catch Exception _
    (println "Fast math not found, using slow math")))
; VALIDATION: SMELL END
```
