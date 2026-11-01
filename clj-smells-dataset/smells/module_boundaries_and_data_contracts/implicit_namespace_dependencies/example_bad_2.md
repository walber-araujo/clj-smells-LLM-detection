## Metadata

* **Smell name:** implicit_namespace_dependencies
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`, `:require`, `:use`, `:refer :all`
* **Short explanation:** Using `:use` or `:refer :all` imports all public vars from a namespace implicitly. This pollutes the current namespace and makes it hard to trace where functions come from.

```Clojure
(ns app.billing
; VALIDATION: SMELL START - implicit_namespace_dependencies
; VALIDATION: using :use imports all symbols implicitly
  (:use [clojure.string]))
; VALIDATION: SMELL END

(defn format-invoice [id]
  (upper-case (str "inv-" id)))
```
