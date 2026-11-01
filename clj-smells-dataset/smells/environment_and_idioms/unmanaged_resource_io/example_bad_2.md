## Metadata

* **Smell name:** Unmanaged Resource IO
* **Expected smell location:** Function `process-file`, `write-log`, `handle-socket`
* **Affected forms:** `io/reader`, `io/writer`, `java.net.Socket.`
* **Short explanation:** Failing to wrap I/O resources in `with-open` can lead to resource leaks if an exception is thrown or if they are not manually closed.

```Clojure
(ns web-app.logger
  (:require [clojure.java.io :as io]))

(defn append-to-log [msg file-path]
  ; VALIDATION: SMELL START - Unmanaged Resource IO
  ; VALIDATION: io/writer opened without with-open
  (let [writer (io/writer file-path :append true)]
    (.write writer (str msg "\n"))
    (.flush writer)))
  ; VALIDATION: SMELL END
```
