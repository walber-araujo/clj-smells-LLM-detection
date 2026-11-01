## Metadata

* **Smell name:** overengineering_with_core_async
* **Expected smell location:** Function `fetch-user-record`
* **Affected forms:** `chan`, `go`, `<!`
* **Short explanation:** Using full core.async channel machinery for a simple one-shot async result is overengineering; a `future` or `promise` is simpler and more appropriate.

```Clojure
(ns app.db.queries
  (:require [clojure.core.async :as a :refer [go chan <! >!]]))

(defn run-db-query [id]
  {:id id :name "Bob"})

(defn fetch-user-record
  [id]
  ; VALIDATION: SMELL START - overengineering_with_core_async
  ; VALIDATION: Overcomplicating a single one-shot async task with core.async
  (let [result-chan (chan)]
    (go (>! result-chan (run-db-query id)))
    result-chan))
  ; VALIDATION: SMELL END
```
