## Metadata

* **Smell name:** misused_threading
* **Expected smell location:** Function `build-and-send-request`
* **Affected forms:** `->`
* **Short explanation:** Uses threading macro for a pipeline where the fundamental type shifts between domain entities, strings, and HTTP responses, obscuring the data flow.

```Clojure
(ns api.client
  (:require [clj-http.client :as client]))

(defn build-and-send-request [user-id]
  ; VALIDATION: SMELL START - misused_threading
  ; VALIDATION: Drastic type changes: Number -> Map -> String -> Map (Response) -> Boolean
  (-> user-id
      fetch-user-record
      :endpoint-url
      (client/get {:accept :json})
      :status
      (= 200)))
  ; VALIDATION: SMELL END
```
