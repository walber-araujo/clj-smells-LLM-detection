## Metadata

* **Smell name:** monolithic_namespace_split
* **Expected smell location:** Top-level form
* **Affected forms:** `load`, `in-ns`
* **Short explanation:** Using `load` or `in-ns` to split a single namespace across multiple files obscures dependencies and makes the code harder to navigate. It creates a monolithic namespace that is too large to fit in a single file.

```Clojure
(ns myapp.routes)

; VALIDATION: SMELL START - monolithic_namespace_split
; VALIDATION: using load to split a namespace
(load "routes_auth")
; VALIDATION: SMELL END

(defn init-routes []
  (println "Routes initialized"))
```
