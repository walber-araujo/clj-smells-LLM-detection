## Metadata

* **Smell name:** overengineering_with_core_async
* **Expected smell location:** Function `send-notification`
* **Affected forms:** `chan`, `go`, `<!`
* **Short explanation:** Using full core.async channel machinery for a simple one-shot async result is overengineering; a `future` or `promise` is simpler and more appropriate.

```Clojure
(ns app.notify.email
  (:require [clojure.core.async :as a :refer [go chan <! >!]]))

(defn dispatch-email [to subject]
  true)

(defn send-notification
  [user msg]
  ; VALIDATION: SMELL START - overengineering_with_core_async
  ; VALIDATION: Overcomplicating a single one-shot async task with core.async
  (let [c (chan)]
    (go (>! c (dispatch-email (:email user) msg)))
    (go (let [success? (<! c)]
          (println "Sent notification:" success?)))))
  ; VALIDATION: SMELL END
```
