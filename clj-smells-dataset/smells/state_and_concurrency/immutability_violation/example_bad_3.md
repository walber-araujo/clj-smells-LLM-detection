## Metadata

* **Smell name:** immutability_violation
* **Expected smell location:** Function `increment-clicks`
* **Affected forms:** `defn`, `def`
* **Short explanation:** Using `def` inside a function to reassign a top-level var mutates global state and violates Clojure's immutability principles.

```Clojure
(ns app.analytics.counters)

(def click-count 0)

(defn increment-clicks
  []
  ; VALIDATION: SMELL START - immutability_violation
  ; VALIDATION: Reassigning a top-level var with def inside a function
  (def click-count (inc click-count))
  ; VALIDATION: SMELL END
  click-count)
```
