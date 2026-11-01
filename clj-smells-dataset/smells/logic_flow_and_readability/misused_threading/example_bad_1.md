## Metadata

* **Smell name:** misused_threading
* **Expected smell location:** Function `process-project-config`
* **Affected forms:** `->`
* **Short explanation:** Threads a value through operations that drastically change its type (string to file to map to string), making the pipeline hard to follow.

```Clojure
(ns project.config
  (:require [clojure.java.io :as io]
            [clojure.edn :as edn]))

(defn process-project-config [filepath]
  ; VALIDATION: SMELL START - misused_threading
  ; VALIDATION: Value type changes drastically at each step: String -> File -> String -> Map -> Vector
  (-> filepath
      io/file
      slurp
      edn/read-string
      :dependencies
      keys))
  ; VALIDATION: SMELL END
```
