## Metadata

* **Smell name:** conditional_build_up
* **Expected smell location:** Function `create-search-query`
* **Affected forms:** `let`, `if`, `assoc`
* **Short explanation:** Builds up a database query map incrementally with manual rebinding, missing the opportunity for a cleaner cond-> pipeline.

```Clojure
(ns db.search)

(defn create-search-query [params]
  ; VALIDATION: SMELL START - conditional_build_up
  ; VALIDATION: Manual conditional updates of a map using let/if
  (let [q {:query {:match_all {}}}
        q (if (:term params)
            (assoc q :query {:match {:content (:term params)}})
            q)
        q (if (:limit params)
            (assoc q :size (:limit params))
            q)
        q (if (:offset params)
            (assoc q :from (:offset params))
            q)]
    q))
  ; VALIDATION: SMELL END
```
