## Metadata

* **Smell name:** overengineering_with_core_async
* **Expected smell location:** Function `fetch-http-result`
* **Affected forms:** `chan`, `go`, `<!`
* **Short explanation:** Using full core.async channel machinery for a simple one-shot async result is overengineering; a `future` or `promise` is simpler and more appropriate.

```Clojure
(ns app.http.client
  (:require [clojure.core.async :as a :refer [go chan <! >!]]))

(defn perform-http-request [url]
  {:status 200 :body "data"})

(defn fetch-http-result
  [url]
  ; VALIDATION: SMELL START - overengineering_with_core_async
  ; VALIDATION: Overcomplicating a single one-shot async task with core.async
  (let [c (chan)]
    (go (>! c (perform-http-request url)))
    (go (println "Got result:" (<! c)))))
  ; VALIDATION: SMELL END
```
