## Metadata

* **Smell name:** conditional_build_up
* **Expected smell location:** Function `build-user-profile`
* **Affected forms:** `let`, `if`, `assoc`
* **Short explanation:** Uses a series of let bindings and if statements to incrementally build a map, which is verbose and harder to read.

```Clojure
(ns app.user-profile)

(defn build-user-profile [user options]
  ; VALIDATION: SMELL START - conditional_build_up
  ; VALIDATION: Incrementally building map with let and if instead of cond->
  (let [profile {:id (:id user) :name (:name user)}
        profile (if (:include-email? options)
                  (assoc profile :email (:email user))
                  profile)
        profile (if (:include-address? options)
                  (assoc profile :address (:address user))
                  profile)]
    profile))
  ; VALIDATION: SMELL END
```
