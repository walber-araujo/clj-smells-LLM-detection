## Metadata

* **Smell name:** blocking_inside_go
* **Expected smell location:** Macro `go` in `wait-for-result`
* **Affected forms:** `go`, `alts!!`
* **Short explanation:** Using a blocking `alts!!` operation inside a `go` block blocks a thread from the core.async fixed thread pool, which can lead to pool starvation.

```Clojure
(ns app.timeout.waiter
  (:require [clojure.core.async :as a :refer [go timeout alts!!]]))

(defn wait-for-result
  [result-chan]
  (go
    ; VALIDATION: SMELL START - blocking_inside_go
    ; VALIDATION: Using alts!! blocks the go block thread
    (let [[v c] (alts!! [result-chan (timeout 5000)])]
    ; VALIDATION: SMELL END
      (if (= c result-chan)
        {:status :success :data v}
        {:status :timeout}))))
```
