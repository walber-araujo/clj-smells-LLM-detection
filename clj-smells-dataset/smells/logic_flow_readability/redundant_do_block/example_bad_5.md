## Metadata

* **Smell name:** redundant_do_block
* **Expected smell location:** Function `create-handler`
* **Affected forms:** `fn`, `do`
* **Short explanation:** Uses a do block inside an anonymous fn, which already has an implicit do.

```Clojure
(ns web.handlers)

(defn create-handler []
  (fn [request]
    ; VALIDATION: SMELL START - redundant_do_block
    ; VALIDATION: fn body already has an implicit do block
    (do
      (log/debug "Handling request" (:uri request))
      {:status 200 :body "OK"})))
    ; VALIDATION: SMELL END
```
