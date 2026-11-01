## Metadata

* **Smell name:** unnecessary_laziness
* **Expected smell location:** Function `process`
* **Affected forms:** `map`, `vec`
* **Short explanation:** Using lazy `map` over a finite collection just to immediately force realization with `vec` is inefficient and hides intent; `mapv` is more direct.

```Clojure
(ns app.data.pipeline)

(defn process
  [coll]
  ; VALIDATION: SMELL START - unnecessary_laziness
  ; VALIDATION: Using lazy map then immediately forcing realization with vec
  (let [doubled (map #(* 2 %) coll)]
    (vec doubled)))
  ; VALIDATION: SMELL END
```
