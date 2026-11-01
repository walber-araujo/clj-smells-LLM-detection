## Metadata

* **Smell name:** Misuse of Channel Closing Semantics
* **Expected smell location:** Function `worker`
* **Affected forms:** `>!`, `put!`
* **Short explanation:** Using a special sentinel value to signal the end of a core.async channel is unidiomatic; you should use `close!` instead.

```Clojure
(ns async.producer
  (:require [clojure.core.async :as a]))

(defn produce-data [ch]
  (a/go
    (dotimes [i 10]
      (a/>! ch i))
    ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
    ; VALIDATION: Putting a sentinel :eof to close
    (a/>! ch :eof)))
    ; VALIDATION: SMELL END
```
