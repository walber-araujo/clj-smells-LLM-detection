## Metadata

* **Smell name:** Misuse of Channel Closing Semantics
* **Expected smell location:** Function `worker`
* **Affected forms:** `>!`, `put!`
* **Short explanation:** Using a special sentinel value to signal the end of a core.async channel is unidiomatic; you should use `close!` instead.

```Clojure
(ns async.worker
  (:require [clojure.core.async :as a]))

(defn process-jobs [jobs-ch]
  (a/go-loop []
    (let [job (a/<! jobs-ch)]
      ; VALIDATION: SMELL START - Misuse of Channel Closing Semantics
      ; VALIDATION: Using :done sentinel value instead of checking if channel is closed
      (when-not (= job :done)
        (println "Processing" job)
        (recur)))))
      ; VALIDATION: SMELL END
```
