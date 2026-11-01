## Metadata

* **Smell name:** unnecessary_laziness
* **Expected smell location:** Function `get-active-users`
* **Affected forms:** `filter`, `vec`
* **Short explanation:** Using lazy `filter` over a finite collection just to immediately force realization with `vec` is inefficient and hides intent; `filterv` is more direct.

```Clojure
(ns app.users.filter)

(defn get-active-users
  [users]
  ; VALIDATION: SMELL START - unnecessary_laziness
  ; VALIDATION: Using lazy filter then immediately forcing realization with vec
  (vec (filter :active users)))
  ; VALIDATION: SMELL END
```
