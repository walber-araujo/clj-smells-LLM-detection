## Metadata

* **Smell name:** misused_threading
* **Expected smell location:** Function `transform-and-save-data`
* **Affected forms:** `->>`
* **Short explanation:** A long threading pipeline where the type changes from a collection of maps to a single string to a file object to a boolean side-effect result.

```Clojure
(ns data.pipeline
  (:require [clojure.string :as str]
            [clojure.java.io :as io]))

(defn transform-and-save-data [records]
  ; VALIDATION: SMELL START - misused_threading
  ; VALIDATION: Collection of maps is threaded into a single string, then to a side effect
  (->> records
       (map :value)
       (filter pos?)
       (str/join ",")
       (spit (io/file "/tmp/output.csv"))))
  ; VALIDATION: SMELL END
```
