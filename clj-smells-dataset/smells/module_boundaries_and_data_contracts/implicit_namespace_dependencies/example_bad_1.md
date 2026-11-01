## Metadata

* **Smell name:** implicit_namespace_dependencies
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`, `:require`, `:use`, `:refer :all`
* **Short explanation:** Using `:use` or `:refer :all` imports all public vars from a namespace implicitly. This pollutes the current namespace and makes it hard to trace where functions come from.

```Clojure
(ns app.users
  (:require [app.db :refer :all]))

; VALIDATION: SMELL START - implicit_namespace_dependencies
; VALIDATION: using :refer :all imports everything implicitly, making dependencies unclear
(defn get-user [id]
  (query "SELECT * FROM users WHERE id = ?" id))
; VALIDATION: SMELL END
```
