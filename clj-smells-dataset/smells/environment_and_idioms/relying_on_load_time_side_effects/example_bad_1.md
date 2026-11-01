## Metadata

* **Smell name:** Relying on Load-Time Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `def`
* **Short explanation:** Evaluating side-effectful code (like network requests or DB connections) at load time makes the namespace hard to test, reload, or use in other contexts.

```Clojure
(ns app.db-init
  (:require [next.jdbc :as jdbc]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Establishing DB connection at load time
(def db-conn 
  (jdbc/get-connection {:dbtype "postgres" :dbname "prod"}))
; VALIDATION: SMELL END

(defn get-users []
  (jdbc/execute! db-conn ["SELECT * FROM users"]))
```
