## Metadata

* **Smell name:** Unmanaged Resource IO
* **Expected smell location:** Function `process-file`, `write-log`, `handle-socket`
* **Affected forms:** `io/reader`, `io/writer`, `java.net.Socket.`
* **Short explanation:** Wrapping I/O resources in `with-open` ensures they are closed automatically, even if an exception occurs.

```Clojure
(ns data-pipeline.csv-processor
  (:require [clojure.java.io :as io]
            [clojure.data.csv :as csv]))

(defn process-csv [file-path]
  (with-open [reader (io/reader file-path)]
    (let [data (csv/read-csv reader)]
      (doall (map #(assoc % :processed true) data)))))
```
