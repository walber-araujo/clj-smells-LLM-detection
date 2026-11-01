## Metadata

* **Smell name:** Unnecessary into
* **Expected smell location:** Function `process`
* **Affected forms:** `into`
* **Short explanation:** Using `into` to convert a collection when a simpler, more direct function like `vec` or `set` exists.

```Clojure
(ns config.loader)

(defn parse-config [m]
  ; VALIDATION: SMELL START - Unnecessary into
  ; VALIDATION: Using into {} map instead of update-vals or zipmap
  (into {} (map (fn [[k v]] [k (clojure.string/upper-case v)]) m)))
  ; VALIDATION: SMELL END
```
