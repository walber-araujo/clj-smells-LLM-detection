## Metadata

* **Smell name:** excessive_refers
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`, `:require`, `:refer`
* **Short explanation:** Using `:as` to create a namespace alias is cleaner, prevents naming collisions, and makes it clear where functions originate.

```Clojure
(ns app.handler
  (:require [ring.util.response :as resp]))

(defn ok-response [body]
  (-> (resp/response body)
      (resp/content-type "application/json")))
```
