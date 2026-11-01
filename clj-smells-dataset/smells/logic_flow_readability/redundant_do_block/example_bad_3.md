## Metadata

* **Smell name:** redundant_do_block
* **Expected smell location:** Function `update-user`
* **Affected forms:** `let`, `do`
* **Short explanation:** Uses a do block inside a let form, which already has an implicit do.

```Clojure
(ns user.service)

(defn update-user [id params]
  (let [user (db/find-user id)]
    ; VALIDATION: SMELL START - redundant_do_block
    ; VALIDATION: let already provides an implicit do block for its body
    (do
      (db/update-record! id params)
      (notify-user id "Profile updated")
      {:status :ok})))
    ; VALIDATION: SMELL END
```
