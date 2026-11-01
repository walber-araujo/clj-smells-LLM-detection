## Metadata

* **Smell name:** overengineering_with_core_async
* **Expected smell location:** Function `compute-heavy-value`
* **Affected forms:** `chan`, `go`, `<!`
* **Short explanation:** Using full core.async channel machinery for a simple one-shot async result is overengineering; a `future` or `promise` is simpler and more appropriate.

```Clojure
(ns app.compute.math
  (:require [clojure.core.async :as a :refer [go chan <! >!]]))

(defn expensive-calculation []
  (Thread/sleep 1000)
  42)

(defn compute-heavy-value
  []
  ; VALIDATION: SMELL START - overengineering_with_core_async
  ; VALIDATION: Overcomplicating a single one-shot async task with core.async
  (let [c (chan)]
    (go (>! c (expensive-calculation)))
    c))
  ; VALIDATION: SMELL END
```
