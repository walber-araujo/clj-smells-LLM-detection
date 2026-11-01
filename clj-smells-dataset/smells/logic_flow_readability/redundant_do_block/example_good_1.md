## Metadata

* **Smell name:** redundant_do_block
* **Expected smell location:** Function `fetch-and-cache`
* **Affected forms:** `when`
* **Short explanation:** Removed redundant do block from inside the when form.

```Clojure
(ns data.fetcher)

(defn fetch-and-cache [url]
  (let [response (http/get url)]
    (when (:success response)
      (cache/store! url (:body response))
      (log/info "Successfully cached" url))))
```
