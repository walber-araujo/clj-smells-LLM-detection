## Metadata

* **Smell name:** unnecessary_laziness
* **Expected smell location:** Function `process-ids`
* **Affected forms:** `mapv`
* **Short explanation:** Using `mapv` directly communicates intent and efficiently builds a vector without intermediate lazy sequences.

```Clojure
(ns app.data.processor)

(defn fetch-details [id]
  {:id id :info "details"})

(defn process-ids
  [ids]
  (mapv fetch-details ids))
```
