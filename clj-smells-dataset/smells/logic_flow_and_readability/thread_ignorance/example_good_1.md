## Metadata

* **Smell name:** thread_ignorance
* **Expected smell location:** Function `extract-active-usernames`
* **Affected forms:** `->>`
* **Short explanation:** Refactored to use the ->> threading macro, making the data pipeline clear and readable.

```Clojure
(ns users.analytics)

(defn extract-active-usernames [users]
  (->> users
       (filter :active?)
       (map :username)
       sort))
```
