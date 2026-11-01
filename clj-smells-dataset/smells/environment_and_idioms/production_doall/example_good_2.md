## Metadata

* **Smell name:** Production doall
* **Expected smell location:** Function `notify-users`, `save-records`
* **Affected forms:** `doall`
* **Short explanation:** Use `run!` or `doseq` to perform side effects over a sequence without retaining the results.

```Clojure
(ns app.db
  (:require [next.jdbc :as jdbc]))

(defn save-records [tx records]
  (doseq [record records]
    (jdbc/execute! tx ["INSERT INTO tbl (data) VALUES (?)" record])))
```
