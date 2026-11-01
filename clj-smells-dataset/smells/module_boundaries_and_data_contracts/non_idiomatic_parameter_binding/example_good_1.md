## Metadata

* **Smell name:** non_idiomatic_parameter_binding
* **Expected smell location:** Function parameter list
* **Affected forms:** `defn`
* **Short explanation:** Explicit multi-arity functions make the supported signatures clear and execute faster.

```Clojure
(ns app.utils)

(defn fetch-data
  ([url] (fetch-data url 5000))
  ([url timeout]
   (println "Fetching" url "with timeout" timeout)))
```
