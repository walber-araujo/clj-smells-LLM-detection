## Metadata

* **Smell name:** Direct Usage of clojure.lang.RT
* **Expected smell location:** Function `process`, `get-count`
* **Affected forms:** `clojure.lang.RT/iter`, `clojure.lang.RT/count`
* **Short explanation:** Calling methods on `clojure.lang.RT` directly bypasses the public Clojure API, tightly coupling the code to internal implementation details.

```Clojure
(ns utils.seq)

(defn force-seq [obj]
  ; VALIDATION: SMELL START - Direct Usage of clojure.lang.RT
  ; VALIDATION: Using RT/seq directly instead of clojure.core/seq
  (clojure.lang.RT/seq obj))
  ; VALIDATION: SMELL END
```
