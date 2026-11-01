
## Metadata

* **Smell name:** Redundant Do Block
* **Expected smell location:** Function `create-user`
* **Affected forms:** `defn`
* **Short explanation:** `defn` already evaluates its body using an implicit `do`. Wrapping the entire function body in an explicit `do` is unnecessary.

```Clojure
(ns example.user-service
  (:require
   [clojure.string :as str]))

(defn normalize-email [email]
  (-> email
      str/trim
      str/lower-case))

(defn valid-email? [email]
  (str/includes? email "@"))

(defn create-user [user]
  ;; VALIDATION: SMELL START - Redundant Do
  ;; VALIDATION: defn already has an implicit do around its body.
  (do
    (println "Creating user:" (:email user))
    (assoc user
           :email (normalize-email (:email user))
           :active true))
  ;; VALIDATION: SMELL END
  )

(defn deactivate-user [user]
  (assoc user :active false))
```