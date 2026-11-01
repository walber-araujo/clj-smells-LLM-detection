## Metadata

* **Smell name:** Misuse of Channel Closing Semantics
* **Expected smell location:** Function `worker`
* **Affected forms:** `>!`, `put!`
* **Short explanation:** Using a special sentinel value to signal the end of a core.async channel is unidiomatic; you should use `close!` instead.

```Clojure
(ns async.manual
  (:require [clojure.core.async :as a]))

(defn feed [ch]
  (a/go
    (a/>! ch 1)
    (a/>! ch 2)
    ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
    ; VALIDATION: Manually putting nil is an error in core.async, but sometimes attempted as sentinel
    (a/put! ch nil)))
    ; VALIDATION: SMELL END
```
