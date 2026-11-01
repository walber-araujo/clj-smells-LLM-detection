## Metadata

* **Smell name:** Unmanaged Resource IO
* **Expected smell location:** Function `process-file`, `write-log`, `handle-socket`
* **Affected forms:** `io/reader`, `io/writer`, `java.net.Socket.`
* **Short explanation:** Failing to wrap I/O resources in `with-open` can lead to resource leaks if an exception is thrown or if they are not manually closed.

```Clojure
(ns data-pipeline.csv-processor
  (:require [clojure.java.io :as io]
            [clojure.data.csv :as csv]))

(defn process-csv [file-path]
  ; VALIDATION: SMELL START - Unmanaged Resource IO
  ; VALIDATION: io/reader opened without with-open, leading to potential resource leaks
  (let [reader (io/reader file-path)
        data (csv/read-csv reader)]
    (doall (map #(assoc % :processed true) data))))
  ; VALIDATION: SMELL END
```
