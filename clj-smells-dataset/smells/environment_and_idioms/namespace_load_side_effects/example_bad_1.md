## Metadata

* **Smell name:** Namespace Load Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `require`, `requiring-resolve`
* **Short explanation:** Using `require` as a top-level form outside the `ns` declaration breaks standard dependency tooling and makes the code harder to reason about.

```Clojure
(ns reporting.core)

; VALIDATION: SMELL START - Namespace Load Side Effects
; VALIDATION: Calling require outside the ns form
(require '[clojure.string :as str])
; VALIDATION: SMELL END

(defn generate-report [data]
  (str/join "," data))
```
