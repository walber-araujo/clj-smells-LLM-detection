## Metadata

* **Smell name:** blocking_inside_go
* **Expected smell location:** Macro `go` in `process-pipeline`
* **Affected forms:** `go`, `>!!`
* **Short explanation:** Using a blocking `>!!` operation inside a `go` block blocks a thread from the core.async fixed thread pool, which can lead to pool starvation.

```Clojure
(ns app.pipeline.coordinator
  (:require [clojure.core.async :as a :refer [go <! >!! chan]]))

(defn process-pipeline
  [in-chan out-chan]
  (go
    (loop []
      (when-let [val (<! in-chan)]
        (let [processed (inc val)]
          ; VALIDATION: SMELL START - blocking_inside_go
          ; VALIDATION: Using >!! blocks the go block thread
          (>!! out-chan processed)
          ; VALIDATION: SMELL END
          (recur))))))
```
