## Metadata

* **Smell name:** Direct Usage of clojure.lang.RT
* **Expected smell location:** Function `process`, `get-count`
* **Affected forms:** `clojure.lang.RT/iter`, `clojure.lang.RT/count`
* **Short explanation:** Use the standard Clojure functions like `iterator-seq` or `count` instead of internal Java methods.

```Clojure
(ns data.utils)

(defn get-item-count [coll]
  (count coll))
```
