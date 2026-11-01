## Metadata

* **Smell name:** blocking_inside_go
* **Expected smell location:** Macro `go` in `handle-event`
* **Affected forms:** `go`, `<!!`
* **Short explanation:** Using a blocking `<!!` operation inside a `go` block blocks a thread from the core.async fixed thread pool, which can lead to pool starvation.

```Clojure
(ns app.events.handler
  (:require [clojure.core.async :as a :refer [go <!! <! chan >!]]))

(defn process-event-async [evt]
  (let [c (chan)]
    (go (>! c {:processed evt}))
    c))

(defn handle-event
  [event]
  (go
    (println "Received event:" event)
    ; VALIDATION: SMELL START - blocking_inside_go
    ; VALIDATION: Using <!! blocks the go block thread
    (let [result (<!! (process-event-async event))]
    ; VALIDATION: SMELL END
      (println "Result:" result))))
```
