## Metadata

* **Smell name:** Misuse of Channel Closing Semantics
* **Expected smell location:** Function `worker`
* **Affected forms:** `>!`, `put!`
* **Short explanation:** Using a special sentinel value to signal the end of a core.async channel is unidiomatic; you should use `close!` instead.

```Clojure
(ns async.tasks
  (:require [clojure.core.async :as a]))

(defn start-tasks [ch]
  (a/go
    (a/>! ch {:task "A"})
    (a/>! ch {:task "B"})
    ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
    ; VALIDATION: Passing :stop explicitly
    (a/>! ch :stop)))
    ; VALIDATION: SMELL END
```
