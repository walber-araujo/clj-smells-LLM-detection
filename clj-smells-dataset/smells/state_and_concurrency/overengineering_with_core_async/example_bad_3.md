## Metadata

* **Smell name:** overengineering_with_core_async
* **Expected smell location:** Function `read-config-file`
* **Affected forms:** `chan`, `go`, `<!`
* **Short explanation:** Using full core.async channel machinery for a simple one-shot async result is overengineering; a `future` or `promise` is simpler and more appropriate.

```Clojure
(ns app.io.file
  (:require [clojure.core.async :as a :refer [go chan <! >!]]))

(defn read-file-sync [path]
  "file contents")

(defn read-config-file
  [path]
  ; VALIDATION: SMELL START - overengineering_with_core_async
  ; VALIDATION: Overcomplicating a single one-shot async task with core.async
  (let [c (chan)]
    (go (>! c (read-file-sync path)))
    (go (let [content (<! c)]
          (println "Loaded config" content)))))
  ; VALIDATION: SMELL END
```
