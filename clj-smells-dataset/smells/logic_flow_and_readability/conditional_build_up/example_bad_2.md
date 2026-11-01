## Metadata

* **Smell name:** conditional_build_up
* **Expected smell location:** Function `prepare-http-request`
* **Affected forms:** `let`, `if`, `assoc`
* **Short explanation:** Repeatedly rebinds a map in a let block based on conditions instead of using a threading macro designed for conditional updates.

```Clojure
(ns http.client)

(defn prepare-http-request [url opts]
  ; VALIDATION: SMELL START - conditional_build_up
  ; VALIDATION: Verbose conditional map building using let rebinding
  (let [req {:url url :method :get}
        req (if (:auth-token opts)
              (assoc-in req [:headers "Authorization"] (str "Bearer " (:auth-token opts)))
              req)
        req (if (:timeout opts)
              (assoc req :timeout (:timeout opts))
              req)]
    req))
  ; VALIDATION: SMELL END
```
