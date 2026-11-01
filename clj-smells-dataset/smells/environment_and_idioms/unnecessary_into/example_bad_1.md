## Metadata

* **Smell name:** Unnecessary into
* **Expected smell location:** Function `process`
* **Affected forms:** `into`
* **Short explanation:** Using `into` to convert a collection when a simpler, more direct function like `vec` or `set` exists.

```Clojure
(ns data.transform)

(defn get-ids [records]
  ; VALIDATION: SMELL START - Unnecessary into
  ; VALIDATION: Using (into [] ...) instead of vec
  (into [] (map :id records)))
  ; VALIDATION: SMELL END
```
