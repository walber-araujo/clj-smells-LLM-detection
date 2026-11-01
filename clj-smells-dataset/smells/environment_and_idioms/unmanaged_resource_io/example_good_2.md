## Metadata

* **Smell name:** Unmanaged Resource IO
* **Expected smell location:** Function `process-file`, `write-log`, `handle-socket`
* **Affected forms:** `io/reader`, `io/writer`, `java.net.Socket.`
* **Short explanation:** Wrapping I/O resources in `with-open` ensures they are closed automatically, even if an exception occurs.

```Clojure
(ns web-app.logger
  (:require [clojure.java.io :as io]))

(defn append-to-log [msg file-path]
  (with-open [writer (io/writer file-path :append true)]
    (.write writer (str msg "\n"))
    (.flush writer)))
```
