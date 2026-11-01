## Metadata

* **Smell name:** Misuse of Channel Closing Semantics
* **Expected smell location:** Function `worker`
* **Affected forms:** `>!`, `put!`
* **Short explanation:** Using a special sentinel value to signal the end of a core.async channel is unidiomatic; you should use `close!` instead.

```Clojure
(ns async.stream
  (:require [clojure.core.async :as a]))

(defn consume-stream [ch]
  (a/go-loop []
    (let [v (a/<! ch)]
      ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
      ; VALIDATION: Using ::end as a sentinel
      (if (= v ::end)
        (println "Stream ended")
        (do
          (println "Value:" v)
          (recur))))))
      ; VALIDATION: SMELL END
```
