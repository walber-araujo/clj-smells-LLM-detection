## Metadata

* **Smell name:** dynamically_scoped_singleton_resource
* **Expected smell location:** Top-level def `*mq-connection*`
* **Affected forms:** `def ^:dynamic`, `binding`
* **Short explanation:** Threading a critical resource like a message queue connection via dynamic bindings implicitly hides dependencies and makes the system harder to test.

```Clojure
(ns app.messaging.publisher)

; VALIDATION: SMELL START - dynamically_scoped_singleton_resource
; VALIDATION: Using dynamic scope to thread a singleton resource (Message Queue connection)
(def ^:dynamic *mq-connection* nil)
; VALIDATION: SMELL END

(defn publish-event [topic payload]
  (println "Publishing to" topic "using" *mq-connection*))

(defn handle-action
  [conn event]
  (binding [*mq-connection* conn]
    (publish-event "updates" event)))
```
