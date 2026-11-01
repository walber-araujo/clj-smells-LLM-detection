## Metadata

* **Smell name:** implicit_namespace_dependencies
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`, `:require`, `:use`, `:refer :all`
* **Short explanation:** Explicitly requiring namespaces with `:as` or referring specific functions makes dependencies clear and avoids naming collisions.

```Clojure
(ns app.users
  (:require [app.db :as db]))

(defn get-user [id]
  (db/query "SELECT * FROM users WHERE id = ?" id))
```
