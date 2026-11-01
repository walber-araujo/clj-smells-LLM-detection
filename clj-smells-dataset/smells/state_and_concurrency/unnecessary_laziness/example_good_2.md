## Metadata

* **Smell name:** unnecessary_laziness
* **Expected smell location:** Function `get-active-users`
* **Affected forms:** `filterv`
* **Short explanation:** Using `filterv` directly communicates intent and efficiently builds a vector without intermediate lazy sequences.

```Clojure
(ns app.users.filter)

(defn get-active-users
  [users]
  (filterv :active users))
```
