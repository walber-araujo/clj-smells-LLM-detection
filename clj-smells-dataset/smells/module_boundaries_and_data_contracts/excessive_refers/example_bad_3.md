## Metadata

* **Smell name:** excessive_refers
* **Expected smell location:** Namespace declaration
* **Affected forms:** `ns`, `:require`, `:refer`
* **Short explanation:** Using `:refer` with a very long list of symbols clutters the namespace declaration and makes it hard to maintain. It also pollutes the current namespace.

```Clojure
(ns app.db
; VALIDATION: SMELL START - excessive_refers
; VALIDATION: excessively long list of referred symbols
  (:require [honey.sql.helpers :refer [select from where order-by limit offset join left-join insert-into values update set delete-from returning]]))
; VALIDATION: SMELL END

(defn get-users-query []
  (-> (select :*)
      (from :users)
      (where [:= :active true])))
```
