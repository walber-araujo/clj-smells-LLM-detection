## Metadata

* **Smell name:** Unmanaged Resource IO
* **Expected smell location:** Function `process-file`, `write-log`, `handle-socket`
* **Affected forms:** `io/reader`, `io/writer`, `java.net.Socket.`
* **Short explanation:** Failing to wrap I/O resources in `with-open` can lead to resource leaks if an exception is thrown or if they are not manually closed.

```Clojure
(ns network.client
  (:import [java.net Socket]
           [java.io InputStreamReader BufferedReader]))

(defn fetch-status [host port]
  ; VALIDATION: SMELL START - Unmanaged Resource IO
  ; VALIDATION: Socket opened without with-open
  (let [socket (Socket. host port)
        in (BufferedReader. (InputStreamReader. (.getInputStream socket)))
        response (.readLine in)]
    response))
  ; VALIDATION: SMELL END
```
