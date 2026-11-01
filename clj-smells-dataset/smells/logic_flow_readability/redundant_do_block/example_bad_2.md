## Metadata

* **Smell name:** redundant_do_block
* **Expected smell location:** Function `fetch-and-cache`
* **Affected forms:** `when`, `do`
* **Short explanation:** Uses a do block inside a when form, which already has an implicit do.

```Clojure
(ns data.fetcher)

(defn fetch-and-cache [url]
  (let [response (http/get url)]
    (when (:success response)
      ; VALIDATION: SMELL START - redundant_do_block
      ; VALIDATION: when already provides an implicit do block
      (do
        (cache/store! url (:body response))
        (log/info "Successfully cached" url)))))
      ; VALIDATION: SMELL END
```
