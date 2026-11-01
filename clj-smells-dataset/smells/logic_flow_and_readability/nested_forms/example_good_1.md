## Metadata

* **Smell name:** nested_forms
* **Expected smell location:** Function `process-user-data`
* **Affected forms:** `let`, `when`
* **Short explanation:** Refactored to flatten nested when-let forms by using a single let block and a condition check (or multiple bindings in modern Clojure with some->).

```Clojure
(ns data.processor)

(defn process-user-data [db user-id]
  (when-let [theme (some-> (db/get-user db user-id)
                           :preferences
                           :theme)]
    (apply-theme! user-id theme))) ; assuming apply-theme! handles user-id directly for simplicity
```
