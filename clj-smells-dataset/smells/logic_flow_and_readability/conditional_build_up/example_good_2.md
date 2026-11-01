## Metadata

* **Smell name:** conditional_build_up
* **Expected smell location:** Function `prepare-http-request`
* **Affected forms:** `cond->`, `assoc`, `assoc-in`
* **Short explanation:** Refactored to use cond-> to apply conditional updates to the request map cleanly.

```Clojure
(ns http.client)

(defn prepare-http-request [url opts]
  (cond-> {:url url :method :get}
    (:auth-token opts) (assoc-in [:headers "Authorization"] (str "Bearer " (:auth-token opts)))
    (:timeout opts)    (assoc :timeout (:timeout opts))))
```
