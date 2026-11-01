## Metadata

* **Smell name:** blocking_inside_go
* **Expected smell location:** Macro `go` in `fetch-aggregate`
* **Affected forms:** `go`, `<!!`
* **Short explanation:** Using a blocking `<!!` operation inside a `go` block blocks a thread from the core.async fixed thread pool, which can lead to pool starvation.

```Clojure
(ns app.http.aggregator
  (:require [clojure.core.async :as a :refer [go chan <!! <! >!]]))

(defn fetch-user-data [user-id]
  (let [c (chan)]
    (go (>! c {:id user-id :name "Alice"}))
    c))

(defn fetch-aggregate
  [user-id]
  (go
    (let [user-chan (fetch-user-data user-id)
          ; VALIDATION: SMELL START - blocking_inside_go
          ; VALIDATION: Using <!! blocks the go block thread
          user-data (<!! user-chan)]
          ; VALIDATION: SMELL END
      {:aggregate user-data})))
```
