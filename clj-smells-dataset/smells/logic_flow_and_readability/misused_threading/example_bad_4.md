## Metadata

* **Smell name:** misused_threading
* **Expected smell location:** Function `analyze-log-file`
* **Affected forms:** `->`
* **Short explanation:** Threads through fundamentally different contexts (File I/O, string parsing, statistical calculation).

```Clojure
(ns ops.logs
  (:require [clojure.string :as str]))

(defn analyze-log-file [log-path]
  ; VALIDATION: SMELL START - misused_threading
  ; VALIDATION: Type changes from String (path) to String (content) to Collection (lines) to Number (average)
  (-> log-path
      slurp
      str/split-lines
      count
      (/ 100.0)))
  ; VALIDATION: SMELL END
```
