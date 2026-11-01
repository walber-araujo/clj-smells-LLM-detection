## Metadata

* **Smell name:** conditional_build_up
* **Expected smell location:** Function `build-user-profile`
* **Affected forms:** `cond->`, `assoc`
* **Short explanation:** Refactored to use cond->, providing a concise and idiomatic way to conditionally build the map.

```Clojure
(ns app.user-profile)

(defn build-user-profile [user options]
  (cond-> {:id (:id user) :name (:name user)}
    (:include-email? options)   (assoc :email (:email user))
    (:include-address? options) (assoc :address (:address user))))
```
