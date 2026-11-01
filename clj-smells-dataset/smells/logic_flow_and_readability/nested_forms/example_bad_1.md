## Metadata

* **Smell name:** nested_forms
* **Expected smell location:** Function `process-user-data`
* **Affected forms:** `when-let`
* **Short explanation:** Uses deeply nested when-let forms which causes excessive indentation and cognitive load when they could be flattened.

```Clojure
(ns data.processor)

(defn process-user-data [db user-id]
  ; VALIDATION: SMELL START - nested_forms
  ; VALIDATION: Nested when-let forms should be combined into a single when-let or if-let
  (when-let [user (db/get-user db user-id)]
    (when-let [preferences (:preferences user)]
      (when-let [theme (:theme preferences)]
        (apply-theme! user theme)))))
  ; VALIDATION: SMELL END
```
