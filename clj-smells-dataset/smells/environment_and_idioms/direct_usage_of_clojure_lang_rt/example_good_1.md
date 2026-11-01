## Metadata

* **Smell name:** Direct Usage of clojure.lang.RT
* **Expected smell location:** Function `process`, `get-count`
* **Affected forms:** `clojure.lang.RT/iter`, `clojure.lang.RT/count`
* **Short explanation:** Use the standard Clojure functions like `iterator-seq` or `count` instead of internal Java methods.

```Clojure
(ns interop.java
  (:import [java.util ArrayList]))

(defn process-list [^ArrayList arr-list]
  (doseq [item (iterator-seq (.iterator arr-list))]
    (println item)))
```
