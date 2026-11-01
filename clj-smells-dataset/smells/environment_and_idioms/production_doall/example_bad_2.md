## Metadata

* **Smell name:** Production doall
* **Expected smell location:** Function `notify-users`, `save-records`
* **Affected forms:** `doall`
* **Short explanation:** Using `doall` with `map` just to force side effects is non-idiomatic and creates an unnecessary intermediate sequence in memory.

```Clojure
(ns app.db
  (:require [next.jdbc :as jdbc]))

(defn save-records [tx records]
  ; VALIDATION: SMELL START - Production doall
  ; VALIDATION: doall wrapping map for side effects
  (doall (map #(jdbc/execute! tx ["INSERT INTO tbl (data) VALUES (?)" %]) records)))
  ; VALIDATION: SMELL END
```
