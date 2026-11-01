## Metadata

* **Smell name:** Direct Usage of clojure.lang.RT
* **Expected smell location:** Function `process`, `get-count`
* **Affected forms:** `clojure.lang.RT/iter`, `clojure.lang.RT/count`
* **Short explanation:** Calling methods on `clojure.lang.RT` directly bypasses the public Clojure API, tightly coupling the code to internal implementation details.

```Clojure
(ns interop.java
  (:import [java.util ArrayList]))

(defn process-list [^ArrayList arr-list]
  ; VALIDATION: SMELL START - Direct Usage of clojure.lang.RT
  ; VALIDATION: Using RT/iter instead of iterator-seq
  (let [iter (clojure.lang.RT/iter arr-list)]
    (while (.hasNext iter)
      (println (.next iter)))))
  ; VALIDATION: SMELL END
```
