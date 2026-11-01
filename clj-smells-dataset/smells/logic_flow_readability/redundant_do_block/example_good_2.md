## Metadata

* **Smell name:** redundant_do_block
* **Expected smell location:** Function `update-user`
* **Affected forms:** `let`
* **Short explanation:** Removed redundant do block from inside the let form.

```Clojure
(ns user.service)

(defn update-user [id params]
  (let [user (db/find-user id)]
    (db/update-record! id params)
    (notify-user id "Profile updated")
    {:status :ok}))
```
